from datetime import datetime

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


def añadir_paciente_cola_espera(r, paciente):
    id_episodio = paciente["id_episodio"]
    deadline = calcular_deadline(paciente)
    for box in obtener_boxes(r):
        if box["id_episodio"] == id_episodio:
            print(f"El episodio {id_episodio} ya ocupa un box.")
            return False
        
    añadido = r.zadd(
        "urgencias:cola_espera",
        {id_episodio: deadline},
        nx=True
    )

    if añadido:
        print(f"Episodio {id_episodio} añadido a la cola.")
        return True

    print(f"El episodio {id_episodio} ya está en la cola.")
    return False

def siguiente_paciente(r):
    id_episodio = r.zrange("urgencias:cola_espera", 0, 0)
    if id_episodio:
        return id_episodio[0].decode("utf-8")
    return None

def añadir_paciente_box(r):

    box_id = obtener_box_libre(r)

    if box_id is None:
        print("No hay boxes libres disponibles.")
        return False

    paciente = siguiente_paciente(r)

    if paciente is None:
        print("No hay pacientes en la cola de espera.")
        return False

    if ocupar_box(r, box_id, paciente):

        r.zrem("urgencias:cola_espera", paciente)

        print(f"Paciente {paciente} asignado al box {box_id}")
        return True

    return False

def alta_paciente(r, alta):
    id_episodio = alta["id_episodio"]

    for box in obtener_boxes(r):
        if box['id_episodio'] == id_episodio:

            box_id = box["box_id"]

            if liberar_box(r, box_id):
                print(
                    f"Alta del episodio {id_episodio}. "
                    f"Box {box_id} liberado."
                )

                return True
            return False
        if r.zrem("urgencias:cola_espera", id_episodio):
            print(f"Episodio {id_episodio} retirado de la cola por alta.")
            return True

    print(f"El episodio {id_episodio} no está registrado en Redis.")
    return False


def calcular_deadline(paciente):
    hora_entrada = paciente["datos_admision"]["timestamp_llegada"]
    tiempo_maximo = paciente["datos_triaje"]["tiempo_max_espera_min"]

    return hora_entrada + tiempo_maximo * 60

def inicializar_redis(r):
    inicializar_boxes(r)
