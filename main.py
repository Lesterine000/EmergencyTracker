import redis
from src import etl_historico
from src import config
from src import urgencias_worker
from src import triage_redis
from src import anonymizer
from src import analytics_mongo as mongo

def main():
    print('Iniciando emergency tracker')
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

    # Histórico anonimizado → MongoDB
    mongo.cargar_historico(df_anonimizado)

    # Realiza la conexion con Redis y ejecutamos el worker de urgencias
    r = redisConecction()

    mongo.init_index()
    triage_redis.inicializar_redis(r)

    urgencias_worker.urgencias(r)

def redisConecction():
    try:
        r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)
        r.ping()

        return r
    
    except redis.exceptions.ConnectionError as connection_error:
        raise ConnectionError(
            f"Error de conexión con Redis en {config.REDIS_HOST}:{config.REDIS_PORT}: {connection_error}"
        ) from connection_error
    
    except redis.exceptions.TimeoutError as timeout_error:
        raise TimeoutError(
            f"Tiempo de espera agotado para Redis en {config.REDIS_HOST}:{config.REDIS_PORT}: {timeout_error}"
        ) from timeout_error
    
    except redis.exceptions.RedisError as redis_error:
        raise redis.RedisError(
            f"Ocurrió un error con Redis: {redis_error}"
        ) from redis_error
    
if __name__ == "__main__":
    main()