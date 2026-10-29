
import pandas as pd

RUTA_CSV = "./data/admisiones_historico.csv"
RUTA_JSON = "./data/partes_clinicos.json"

def FuncionLectura(ruta_csv: str, ruta_json: str):
        print("Iniciando la lectura de ficheros locales...")
        df_admisiones = pd.read_csv(ruta_csv, sep=',')
        print("'admisiones_historico.csv' cargado correctamente.")
        df_partes = pd.read_json(ruta_json)
        print("'partes_clinicos.json' cargado correctamente.")
        
        return df_admisiones, df_partes

def limpiezaDatos(ruta: str, ruta_json: str):
        limpieza_csv(ruta)
        limpieza_json(ruta_json)

def limpieza_csv(csv: str):
        df_admisiones = FuncionLectura(csv)
        df_admisiones = quitar_nulo_duplicados_csv(df_admisiones)
        df_admisiones['frecuencia_cardiaca'] = pd.to_numeric(df_admisiones['frecuencia_cardiaca'], errors='coerce')  # Convertir a numérico
        df_admisiones = df_admisiones[(df_admisiones['frecuencia_cardiaca'] < 200) & (df_admisiones['frecuencia_cardiaca'] > 40)]  # Filtrar valores extremos
        print(df_admisiones["frecuencia_cardiaca"].describe())

def limpieza_json(json: str):
        df_partes = FuncionLectura(json)
        ...
        
def quitar_nulo_duplicados_csv(df):
        df.dropna(inplace=True)
        df.drop_duplicates(inplace=True)

limpiezaDatos(RUTA_CSV, RUTA_JSON)