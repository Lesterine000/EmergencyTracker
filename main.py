from src import etl_historico
from src import config
from src import urgencias_worker
from src import anonymizer

def main():
    print('Iniciando emergency tracker')
    print()

    print('Realizamos la limpieza y el cruce de datos')

    # Ejecuta el ETL completo
    df_final = etl_historico.etl_historico(
        config.RUTA_CSV,
        config.RUTA_JSON
    )

    print("\nETL completado correctamente")
    print(f"Total de episodios cruzados: {len(df_final)}")

    # --- ANONIMIZADOR ---

    if not config.HMAC_SECRET:
        raise ValueError("No se ha configurado HMAC_SECRET en el archivo .env")

    df_anonimizado = anonymizer.anonimizar_dataframe(
        df_final,
        config.HMAC_SECRET
    )

if __name__ == "__main__":
    main()