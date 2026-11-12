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
def inicializar_boxes(r):
   
    for numero in range(1, 6):
        clave = f"box:{numero}"
        if not r.exists(clave):
            r.hset(clave, mapping={
                "box_id": str(numero),
                "estado": "LIBRE",
                "id_episodio": "",
                "hora_entrada": ""
            })
 
# Obtenemos los boxes
def obtener_boxes(r):
    boxes = []
 
    for numero in range(1, 6):
        clave = f"box:{numero}"
        box_data = r.hgetall(clave)
 
        if box_data:
            boxes.append({
                "box_id": numero,
                "estado": box_data[b"estado"].decode("utf-8"),
                "id_episodio": box_data[b"id_episodio"].decode("utf-8"),
                "hora_entrada": box_data[b"hora_entrada"].decode("utf-8")
            })
 
    return boxes
 
# Obtenemos el primer box libre
def obtener_box_libre(r):
    boxes = obtener_boxes(r)
    for box in boxes:
        if box["estado"] == "LIBRE":
            return box["box_id"]
   
    return None
 
# Ocupamos un box
def ocupar_box(r, box_id, id_episodio):
   
    clave = f"box:{box_id}"
   
    if not r.exists(clave):
        print(f"El box {box_id} no existe.")
        return False
   
    if r.hget(clave, b'estado').decode('utf-8') == "OCUPADO":
        print(f"El box {box_id} ya está ocupado.")
        return False
 
    r.hset(clave, mapping={
        "estado": "OCUPADO",
        "id_episodio": id_episodio,
        "hora_entrada": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return True
# Liberamos un box
def liberar_box(r, box_id):
    r.hset(f"box:{box_id}", mapping={
        "estado": "LIBRE",
        "id_episodio": "",
        "hora_entrada": ""
    })

def initialize_redis():
    redis_connection = redisConecction()
    boxes(redis_connection)

