from src import etl_historico
from src import config
from src import urgencias_worker
def main():
    print('Iniciando emergency tracker')
    print("\n")
    print('Realizamos la limpieza de datos')
    # rellenar con la funcion con la que se iniciara etl_historico
    etl_historico.limpieza_datos(config.RUTA_CVS, config.RUTA_JSON)
    # Consulta a la API
    # urgencias_worker.api_hospital(config.RUTA_API)

if __name__ == "__main__":
    main()