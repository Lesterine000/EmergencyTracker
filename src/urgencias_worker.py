import requests
import json
import redis
import time
import src.config as config

def api_hospital(ruta_api:str):
    try:
        response = requests.get(ruta_api, timeout=5)
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=4))
    except requests.exceptions.HTTPError as http_error:
        raise(f"Error http{http_error}")
    except requests.exceptions.ConnectTimeout as timeout:
        raise(f"Tiempo de espera demasiado largo{timeout}")
    except requests.exceptions.ConnectionError as conection:
        raise(f"Ocurrion un error con la conexion{conection}")
    except requests.exceptions.RequestException as exception:
        raise(f"Ocurrio un error inesperado{exception}")

def redisConecction():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
    except redis.exceptions.ConnectionError as connection_error:
        raise ConnectionError(
            f"Error de conexión con Redis: {connection_error}"
        ) from connection_error
    except redis.exceptions.TimeoutError as timeout_error:
        raise TimeoutError(
            f"Tiempo de espera agotado para Redis: {timeout_error}"
        ) from timeout_error
    except redis.exceptions.RedisError as redis_error:
        raise redis.RedisError(
            f"Ocurrió un error con Redis: {redis_error}"
        ) from redis_error

def worker_urgencias():
    print("Iniciando el worker de urgencias...")
    while True:
        try:
            api_hospital(config.RUTA_API)
        except Exception as error:
            print(f"Error en el worker: {error}")
        time.sleep(5)  # Espera 5 segundos antes de la siguiente iteración


def boxes():
    pass

def urgencias():
    worker_urgencias()
    redisConecction()
