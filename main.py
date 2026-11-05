from src import etl_historico
from src import config
from src import urgencias_worker

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

if __name__ == "__main__":
    main()