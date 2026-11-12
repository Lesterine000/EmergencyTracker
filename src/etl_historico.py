import pandas as pd
import re
from src.config import RUTA_CSV, RUTA_JSON

import pandas as pd

def funcion_lectura(ruta_csv: str, ruta_json: str):
        print("Iniciando la lectura de ficheros locales...")
        df_admisiones = pd.read_csv(ruta_csv, sep=',')
        print("'admisiones_historico.csv' cargado correctamente.")
        df_partes = pd.read_json(ruta_json)
        print("'partes_clinicos.json' cargado correctamente.")

        return df_admisiones, df_partes

def limpieza_datos(ruta_csv: str, ruta_json: str):
        df_admisiones, df_partes = funcion_lectura(ruta_csv, ruta_json)

        df_admisiones_limpio = limpieza_csv(df_admisiones)
        df_partes_limpio = limpieza_json(df_partes)

        return df_admisiones_limpio, df_partes_limpio


# --- CSV ---
def limpieza_csv(df_admisiones):

    # Elimina nulos y duplicados
    df_admisiones = quitar_nulo_duplicados_csv(df_admisiones)

    # Normaliza los textos
    df_admisiones = normalizar_textos_csv(df_admisiones)

    # Limpia la frecuencia cardíaca
    df_admisiones = limpiar_frecuencia_cardiaca(df_admisiones)

    # Limpia la tensión arterial
    df_admisiones['tension_arterial'] = (
        df_admisiones['tension_arterial']
        .astype(str)
        .str.replace('_', '/', regex=False)
    )

    df_admisiones['tension_arterial'] = (
        df_admisiones['tension_arterial']
        .replace(['nan', 'pendiente'], 'desconocido')
    )

    # Limpia el destino de alta
    df_admisiones['destino_alta'] = (
        df_admisiones['destino_alta']
        .replace(['nan', 'pendiente'], 'desconocido')
        .fillna('desconocido')
    )

    return df_admisiones

def quitar_nulo_duplicados_csv(df):

    df = df.dropna(subset=['id_episodio']).copy()

    # Elimina duplicados por episodio
    df = df.drop_duplicates(
        subset=['id_episodio'],
        keep='first'
    ).copy()

    # Convierte la fecha de llegada a datetime
    df['timestamp_llegada'] = pd.to_datetime(
        df['timestamp_llegada'],
        format='mixed',
        dayfirst=True,
        errors='coerce',
        utc=True
    )

    # Convierte la fecha de alta a datetime
    df['timestamp_alta'] = pd.to_datetime(
        df['timestamp_alta'],
        format='mixed',
        dayfirst=True,
        errors='coerce',
        utc=True
    )

    return df

def normalizar_textos_csv(df):
    columnas_texto = df.select_dtypes(include="object").columns
    for col in columnas_texto:
        df[col] = df[col].str.strip().str.lower()

    return df


def limpieza_json(df_partes):
    # Elimina registros sin identificador
    df_partes = df_partes.dropna(
        subset=['id_episodio']
    ).copy()

    # Elimina duplicados por episodio
    df_partes = df_partes.drop_duplicates(
        subset=['id_episodio'],
        keep='first'
    ).copy()

    # Normaliza los textos (También las listas y diccionarios) 
    df_partes = normalizar_columnas_texto(df_partes)

    # Limpia las constantes
    df_partes['constantes'] = (
        df_partes['constantes'].apply(limpiar_constantes)
    )
    
    return df_partes
        
def limpiar_frecuencia_cardiaca(df):

    # Convierte los valores a números
    df['frecuencia_cardiaca'] = pd.to_numeric(
        df['frecuencia_cardiaca'],
        errors='coerce'
    )

    # Elimina valores claramente inválidos
    df.loc[
        (df['frecuencia_cardiaca'] <= 0) |
        (df['frecuencia_cardiaca'] > 250),
        'frecuencia_cardiaca'
    ] = pd.NA

    # Calcula los cuartiles
    Q1 = df['frecuencia_cardiaca'].quantile(0.25)
    Q3 = df['frecuencia_cardiaca'].quantile(0.75)

    # Calcula el rango intercuartílico
    IQR = Q3 - Q1

    # Define los límites
    limite_inferior = Q1 - 1.5 * IQR
    limite_superior = Q3 + 1.5 * IQR

    # Detecta los valores atípicos
    valores_atipicos = (
        (df['frecuencia_cardiaca'] < limite_inferior) |
        (df['frecuencia_cardiaca'] > limite_superior)
    )

    # Convierte los valores atípicos en nulos
    df.loc[valores_atipicos, 'frecuencia_cardiaca'] = pd.NA

    # Calcula la mediana de los valores válidos
    mediana = df['frecuencia_cardiaca'].median()

    # Imputa los valores nulos
    if pd.isna(mediana):
        print("No hay valores válidos para calcular la mediana.")
    else:
        df['frecuencia_cardiaca'] = (
            df['frecuencia_cardiaca'].fillna(mediana)
        )

    print("Límite inferior IQR:", limite_inferior)
    print("Límite superior IQR:", limite_superior)

    print("Total de registros:", len(df))
    print("Frecuencias cardíacas nulas:", df['frecuencia_cardiaca'].isna().sum())
    return df
    


# --- JSON ---
def normalizar_valores_json(valor):

    # Si es una cadena de texto
    if isinstance(valor, str):
        return valor.strip().lower()

    # Si es un diccionario
    elif isinstance(valor, dict):

        return {
            clave: normalizar_valores_json(contenido)
            for clave, contenido in valor.items()
        }

    # Si es una lista
    elif isinstance(valor, list):

        return [
            normalizar_valores_json(elemento)
            for elemento in valor
        ]

    # Si es un número, booleano o nulo
    else:
        return valor


def normalizar_columnas_texto(df_partes):

    for columna in df_partes.columns:

        df_partes[columna] = df_partes[columna].apply(
            normalizar_valores_json
        )

    return df_partes


def limpiar_constantes(constantes):

    if not isinstance(constantes, dict):
        return constantes

    # Temperatura
    temperatura = pd.to_numeric(
        constantes.get('temperatura_c'),
        errors='coerce'
    )

    if pd.isna(temperatura) or temperatura < 30 or temperatura > 45:
        constantes['temperatura_c'] = None
    else:
        constantes['temperatura_c'] = temperatura

    # Frecuencia cardíaca
    frecuencia = pd.to_numeric(
        constantes.get('frecuencia_cardiaca_triaje'),
        errors='coerce'
    )

    if pd.isna(frecuencia) or frecuencia < 30 or frecuencia > 250:
        constantes['frecuencia_cardiaca_triaje'] = None
    else:
        constantes['frecuencia_cardiaca_triaje'] = frecuencia

    # Saturación de oxígeno
    saturacion = pd.to_numeric(
        constantes.get('saturacion_o2'),
        errors='coerce'
    )

    if pd.isna(saturacion) or saturacion < 0 or saturacion > 100:
        constantes['saturacion_o2'] = None
    else:
        constantes['saturacion_o2'] = saturacion

    return constantes



# Combina ambos datasets mediante la clave 'id_episodio'
def cruzar_datos(df_admisiones, df_partes):
    df_admisiones["id_episodio"] = (
        df_admisiones["id_episodio"].astype(str).str.strip().str.lower()
    )
    df_partes["id_episodio"] = (
        df_partes["id_episodio"].astype(str).str.strip().str.lower()
    )

    df_completo = pd.merge(
        df_admisiones, df_partes, on="id_episodio", how="inner"
    )

    print(
            "Duplicados en el resultado:",
            df_completo['id_episodio'].duplicated().sum()
        )

    print(f"Cruce completado. Total de registros cruzados: {len(df_completo)}")
    return df_completo

def etl_historico(ruta_csv: str, ruta_json: str):
    # Extracción
    df_admisiones, df_partes = funcion_lectura(ruta_csv, ruta_json)

    # Limpieza
    df_admisiones_limpio = limpieza_csv(df_admisiones)
    df_partes_limpio = limpieza_json(df_partes)

    # Cruce de datos
    df_final = cruzar_datos(df_admisiones_limpio, df_partes_limpio)

    return df_final