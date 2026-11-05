import pandas as pd
import re
from config import RUTA_CSV, RUTA_JSON

# Lectura de los datasets CSV y JSON
def funcion_lectura(ruta_csv, ruta_json):
    print("Iniciando la lectura de ficheros locales...")
    df_admisiones = pd.read_csv(ruta_csv, sep=',')
    print(f"  CSV cargado: {len(df_admisiones)} filas")
    df_partes = pd.read_json(ruta_json)
    print(f"  JSON cargado: {len(df_partes)} registros")
    return df_admisiones, df_partes

# LIMPIEZA CSV
FORMATOS_FECHA = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %I:%M %p",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M",
]

def parsear_fecha(valor) -> float | None:
    """Intenta parsear una fecha con múltiples formatos; retorna epoch o None."""
    if pd.isna(valor) or str(valor).strip().upper() in ("NULL", "NAN", ""):
        return None
    s = str(valor).strip()
    for fmt in FORMATOS_FECHA:
        try:
            return pd.Timestamp(s, tz=None).timestamp() if fmt == "__auto__" \
                   else pd.to_datetime(s, format=fmt).timestamp()
        except (ValueError, TypeError):
            continue
    # Último recurso: inferencia automática de pandas
    try:
        return pd.to_datetime(s, dayfirst=True).timestamp()
    except Exception:
        return None


def limpiar_destino_alta(valor: str) -> str:
    """Normaliza los valores de destino_alta a dos categorías + Desconocido."""
    if pd.isna(valor):
        return "Desconocido"
    v = str(valor).strip().lower()
    if v in ("domicilio", "alta_domicilio"):
        return "domicilio"
    if "ingreso" in v or "planta" in v or "pediatria" in v or "uci" in v:
        return "ingreso_planta"
    return "Desconocido"


def limpieza_csv(df: pd.DataFrame) -> pd.DataFrame:
    # Duplicados y nulos en campos obligatorios
    df = df.drop_duplicates()
    df = df.dropna(subset=["id_episodio"])

    # Parsear fechas heterogéneas → epoch float (None si inválido)
    df["timestamp_llegada"] = df["timestamp_llegada"].apply(parsear_fecha)
    df["timestamp_alta"]    = df["timestamp_alta"].apply(parsear_fecha)

    # Eliminar filas sin timestamp_llegada (imprescindible para EDF)
    df = df.dropna(subset=["timestamp_llegada"])

    # Frecuencia cardiaca
    df["frecuencia_cardiaca"] = pd.to_numeric(df["frecuencia_cardiaca"], errors="coerce")
    df["frecuencia_cardiaca"] = df["frecuencia_cardiaca"].where(
        (df["frecuencia_cardiaca"] > 35) & (df["frecuencia_cardiaca"] < 200)
    )
    df["frecuencia_cardiaca"] = df["frecuencia_cardiaca"].fillna(
        df["frecuencia_cardiaca"].median()
    ).round(0).astype(int)

    # Tensión arterial
    df["tension_arterial"] = (
        df["tension_arterial"]
        .astype(str)
        .str.replace("_", "/", regex=False)
        .replace(["nan", "PENDIENTE", "NaN"], "Desconocido")
    )

    # Normalizar destino_alta
    df["destino_alta"] = df["destino_alta"].apply(limpiar_destino_alta)

    # Normalizar motivo_consulta a minúsculas sin espacios extra
    df["motivo_consulta"] = df["motivo_consulta"].astype(str).str.strip().str.lower()

    print(f"  CSV limpio: {len(df)} filas válidas")
    return df

# Limpieza JSON
def limpieza_json(df: pd.DataFrame) -> pd.DataFrame:
    # Eliminar duplicados por id_episodio
    df = df.drop_duplicates(subset=["id_episodio"])

    # Aplanar campos anidados relevantes para las consultas
    df["nivel_manchester"]      = df["triaje_manchester"].apply(lambda x: x.get("nivel") if isinstance(x, dict) else None)
    df["color_manchester"]      = df["triaje_manchester"].apply(lambda x: x.get("color") if isinstance(x, dict) else None)
    df["categoria_patologia"]   = df["triaje_manchester"].apply(lambda x: x.get("categoria_patologia") if isinstance(x, dict) else None)
    df["tiempo_max_espera_min"] = df["triaje_manchester"].apply(lambda x: x.get("tiempo_max_espera_min") if isinstance(x, dict) else None)

    # Edad: asegurar int positivo
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
    df = df[df["edad"].notna() & (df["edad"] > 0) & (df["edad"] < 130)]
    df["edad"] = df["edad"].astype(int)

    # Normalizar categoria_patologia
    df["categoria_patologia"] = df["categoria_patologia"].astype(str).str.strip().str.title()

    print(f"  JSON limpio: {len(df)} registros válidos")
    return df



# Merge y construccion de documentos
def construir_documentos(df_csv: pd.DataFrame, df_json: pd.DataFrame) -> list[dict]:
    """
    Cruza CSV y JSON por id_episodio (inner join) y construye
    la lista de documentos listos para insertar en MongoDB.
    """
    df = pd.merge(df_csv, df_json, on="id_episodio", how="inner")
    print(f"  Merge completado: {len(df)} episodios cruzados")

    documentos = []
    for _, row in df.iterrows():
        doc = {
            "id_episodio":          row["id_episodio"],
            "sip_paciente":         row.get("sip_paciente_x") or row.get("sip_paciente_y"),
            "edad":                 int(row["edad"]),
            "motivo_consulta":      row.get("motivo_consulta"),
            "timestamp_llegada":    row["timestamp_llegada"],
            "timestamp_alta":       row.get("timestamp_alta"),   # None si aún sin alta
            "destino_alta":         row.get("destino_alta"),
            "frecuencia_cardiaca":  int(row["frecuencia_cardiaca"]),
            "tension_arterial":     row.get("tension_arterial"),
            # Triaje
            "nivel_manchester":     row.get("nivel_manchester"),
            "color_manchester":     row.get("color_manchester"),
            "categoria_patologia":  row.get("categoria_patologia"),
            "tiempo_max_espera_min": row.get("tiempo_max_espera_min"),
            # Bloque original del JSON por si se quiere trazabilidad completa
            "triaje_manchester":    row.get("triaje_manchester"),
            "constantes":           row.get("constantes"),
            "antecedentes":         row.get("antecedentes"),
            "alergias":             row.get("alergias"),
        }
        documentos.append(doc)

    return documentos

# Punto de entrada
def run_etl() -> list[dict]:
    df_csv, df_json = funcion_lectura(RUTA_CSV, RUTA_JSON)
    df_csv_limpio  = limpieza_csv(df_csv)
    df_json_limpio = limpieza_json(df_json)
    documentos     = construir_documentos(df_csv_limpio, df_json_limpio)
    print(f"\n  ETL finalizado → {len(documentos)} documentos listos\n")
    return documentos


if __name__ == "__main__":
    docs = run_etl()
    print(docs[0])  # Muestra el primer documento como verificación