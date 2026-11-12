import requests
import json
import time
import src.config as config
import src.triage_redis as triage_redis

def api_hospital(ruta_api:str):
    try:
        response = requests.get(ruta_api, timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.exceptions.HTTPError as http_error:
        raise(f"Error http{http_error}")
    except requests.exceptions.ConnectTimeout as timeout:
        raise(f"Tiempo de espera demasiado largo{timeout}")
    except requests.exceptions.ConnectionError as conection:
        raise(f"Ocurrion un error con la conexion{conection}")
    except requests.exceptions.RequestException as exception:
        raise(f"Ocurrio un error inesperado{exception}")

def worker_urgencias(r):
    print("Iniciando el worker de urgencias...")
    while True:
        try:
            datos = api_hospital(config.RUTA_API)
            nuevos_ingresos = datos["nuevos_ingresos"]
            altas = datos["pacientes_alta"]
            print(altas)
            if not altas:
                print("No hay pacientes dados de alta en este momento.")

            for alta in altas:
                triage_redis.alta_paciente(r, alta)

            if not nuevos_ingresos:
                print("No hay nuevos ingresos en este momento.")

            for ingreso in nuevos_ingresos:
                triage_redis.añadir_paciente_cola_espera(r, ingreso)

            triage_redis.añadir_paciente_box(r)

            for box in triage_redis.obtener_boxes(r):
                print(f"Box {box} está libre.")

        except requests.exceptions.RequestException as request_error:
            print(f"Error en la solicitud HTTP: {request_error}")
        
        except Exception as error:
            print(f"Error en el worker: {error}")
        time.sleep(5)  # Espera 5 segundos antes de la siguiente iteración



def urgencias(r):
    worker_urgencias(r)

if __name__ == "__main__":
    urgencias()