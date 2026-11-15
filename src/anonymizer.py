import hashlib
import hmac
import pandas as pd

def anonimizar_sip(sip: str, clave: str) -> str:
    # Convierte el sip en bytes
    sip_bytes = sip.strip().encode("utf-8") 

    # Convierte la clave secreta a bytes
    clave_bytes = clave.encode("utf-8")

    # Generacion de el hmac con sha256
    hash_completo = hmac.new(
        clave_bytes,
        sip_bytes,
        hashlib.sha256
    ).hexdigest()

    # Devuelve el hash truncado
    return hash_completo[:24]

def anonimizar_sip_dataframe(df, clave):

    # Se crea una copia para no modificar el DataFrame original
    df = df.copy()

    df["sip_paciente"] = df["sip_paciente_x"]

    # Aplica el hash a todos los SIP
    df["sip_paciente"] = df["sip_paciente"].apply(
        lambda sip: anonimizar_sip(sip, clave)
    )

    # Elimina las columnas originales
    df = df.drop(
        columns=["sip_paciente_x", "sip_paciente_y"]
    )

    return df

def agrupar_edad(edad):

    # Comprobación de que la edad no es nula
    if pd.isna(edad):
        return "desconocido"

    # Inicio del intervalo
    inicio = (int(edad) // 10) * 10

    # Final del intervalo
    fin = inicio + 9

    return f"{inicio}-{fin}"

def anonimizar_edad_dataframe(df):

    df = df.copy() # Copia del DataFrame

    # Agrupa las edades
    df["edad"] = df["edad"].apply(agrupar_edad)

    return df

def eliminar_nombres(valor):

    if isinstance(valor, dict):
        return {
            clave: eliminar_nombres(contenido)
            for clave, contenido in valor.items()
            if str(clave).lower() != "nombre"
        }

    elif isinstance(valor, list):
        return [
            eliminar_nombres(elemento)
            for elemento in valor
        ]

    return valor

def eliminar_nombres_dataframe(df):

    df = df.copy()

    columnas_nombre = [
        columna for columna in df.columns
        if str(columna).lower() == "nombre"
    ]

    df = df.drop(columns=columnas_nombre)

    for columna in df.columns:
        df[columna] = df[columna].apply(eliminar_nombres)

    return df

def anonimizar_dataframe(df, clave):

    print("\nIniciando anonimización...")

    # SIP
    df_anonimizado = anonimizar_sip_dataframe(df, clave)

    # Agrupa las edades
    df_anonimizado = anonimizar_edad_dataframe(df_anonimizado)

    # Elimina los nombres de los datos
    df_anonimizado = eliminar_nombres_dataframe(df_anonimizado)

    print("Anonimización completada correctamente")
    print(f"Total de episodios anonimizados: {len(df_anonimizado)}")

    return df_anonimizado

