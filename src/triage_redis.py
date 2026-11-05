import redis
import src.config as config
def redisConecction():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        return r
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

def boxes(r):
    print("Los 5 boxes están inicializados.")
    for numero in range(1, 6):
        clave = f"box:{numero}"
        if not r.exists(clave):
            r.hset(clave, mapping={
                "box_id": str(numero),
                "paciente_id": "",
                "hora_entrada": ""
            })

def initialize_redis():
    redis_connection = redisConecction()
    boxes(redis_connection)