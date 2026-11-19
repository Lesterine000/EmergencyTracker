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
    if r.hset(f"box:{box_id}", mapping={
        "estado": "LIBRE",
        "id_episodio": "",
        "hora_entrada": ""
    }):
        return True
    return False

def valor_para_redis(valor):
    # Redis solo admite texto y números: se convierten el resto de tipos
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return str(valor).lower()
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return valor

def recuperar_datos_paciente(ingreso):
    # Recupera los datos del paciente del JSON de la API y los deja en un
    # diccionario plano (campo -> valor) listo para guardarlo en Redis.
    # Los bloques anidados (datos_admision, datos_triaje...) se aplanan y,
    # si un campo se repite en dos bloques, se le añade el nombre del bloque.
    datos = {}

    for clave, valor in ingreso.items():
        if isinstance(valor, dict):
            for subclave, subvalor in valor.items():
                nombre = subclave if subclave not in datos else f"{clave}_{subclave}"
                datos[nombre] = valor_para_redis(subvalor)
        else:
            datos[clave] = valor_para_redis(valor)

    # Datos de control del triaje
    datos["deadline"] = calcular_deadline(ingreso)
    datos["estado"] = "EN_ESPERA"
    datos["box_id"] = ""

    return datos

def almacenar_paciente(r, datos_paciente):
    # Guarda los datos del paciente en el hash "paciente:<id_episodio>"
    id_episodio = datos_paciente["id_episodio"]
    r.hset(f"paciente:{id_episodio}", mapping=datos_paciente)
    print(f"Datos del paciente {id_episodio} guardados en Redis.")
    return True

def consultar_paciente(r, id_episodio):
    # Devuelve los datos guardados de un paciente (diccionario vacío si no existe)
    datos = r.hgetall(f"paciente:{id_episodio}")
    return {
        clave.decode("utf-8"): valor.decode("utf-8")
        for clave, valor in datos.items()
    }

def actualizar_estado_paciente(r, id_episodio, **campos):
    # Actualiza el estado del paciente (EN_ESPERA, EN_BOX, ALTA) si está guardado
    clave = f"paciente:{id_episodio}"
    if r.exists(clave):
        r.hset(clave, mapping=campos)
        
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
