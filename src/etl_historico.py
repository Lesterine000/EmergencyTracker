
import pandas as pd
RUTA_CSV = r"C:\Users\victor.gonsua.3\Desktop\BIGDATA\Docker\EmergencyTracker-main\data\admisiones_historico.csv"
RUTA_JSON = r"C:\Users\victor.gonsua.3\Desktop\BIGDATA\Docker\EmergencyTracker-main\data\partes_clinicos.json"
def FuncionLectura(ruta_csv: str, ruta_json: str):
        print("Iniciando la lectura de ficheros locales...")
        df_admisiones = pd.read_csv(ruta_csv, sep=',')
        print("'admisiones_historico.csv' cargado correctamente.")
        df_partes = pd.read_json(ruta_json)
        print("'partes_clinicos.json' cargado correctamente.")
        
        return df_admisiones, df_partes

print(FuncionLectura(RUTA_CSV, RUTA_JSON))