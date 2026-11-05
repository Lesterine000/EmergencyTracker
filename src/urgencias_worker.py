import requests
import json
import time
import src.config as config

def api_hospital(ruta_api:str):
    try:
        response = requests.get(ruta_api, timeout=5)
        if response.status_code == 200:
            pass
        #print(json.dumps(response.json(), indent=4))
    except requests.exceptions.HTTPError as http_error:
        raise(f"Error http{http_error}")
    except requests.exceptions.ConnectTimeout as timeout:
        raise(f"Tiempo de espera demasiado largo{timeout}")
    except requests.exceptions.ConnectionError as conection:
        raise(f"Ocurrion un error con la conexion{conection}")
    except requests.exceptions.RequestException as exception:
        raise(f"Ocurrio un error inesperado{exception}")

def worker_urgencias():
    print("Iniciando el worker de urgencias...")
    while True:
        try:
            api_hospital(config.RUTA_API)
        except Exception as error:
            print(f"Error en el worker: {error}")
        time.sleep(5)  # Espera 5 segundos antes de la siguiente iteración



def urgencias():
    worker_urgencias()
