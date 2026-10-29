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

def limpieza_csv(df_admisiones):
        df_admisiones = quitar_nulo_duplicados_csv(df_admisiones) # Borra los nulos y duplicados

        # Convierte los errores numéricos a nulos 
        df_admisiones['frecuencia_cardiaca'] = pd.to_numeric(df_admisiones['frecuencia_cardiaca'], errors='coerce') 

        # Convierte los valores extremos a nulos temporalmente
        df_admisiones['frecuencia_cardiaca'] = df_admisiones['frecuencia_cardiaca'].where((df_admisiones['frecuencia_cardiaca'] > 35) & (df_admisiones['frecuencia_cardiaca'] < 200))

        # Rellena todos los nulos (los que eran ERROR y los extremos) con la mediana
        df_admisiones['frecuencia_cardiaca'] = df_admisiones['frecuencia_cardiaca'].fillna(df_admisiones['frecuencia_cardiaca'].median())

        # Limpieza de Tensión Arterial y Destino Alta
        df_admisiones['tension_arterial'] = df_admisiones['tension_arterial'].astype(str).str.replace('_', '/', regex=False)
        df_admisiones['tension_arterial'] = df_admisiones['tension_arterial'].replace(['nan', 'PENDIENTE', 'NaN'], 'Desconocido')
        df_admisiones['destino_alta'] = df_admisiones['destino_alta'].fillna('Desconocido')

        print(df_admisiones["frecuencia_cardiaca"].describe())

        return df_admisiones

def limpieza_json(df_partes):
        return df_partes
        
def quitar_nulo_duplicados_csv(df):
        df = df.drop_duplicates()
        # Borrar solo las filas donde falten las fechas de llegada o alta (no todos los nulos)
        df = df.dropna(subset=['timestamp_llegada', 'timestamp_alta'])
        return df
