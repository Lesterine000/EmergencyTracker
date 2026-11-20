import requests
import json
import time
import copy
import src.config as config
import src.triage_redis as triage_redis
import src.anonymizer as anonymizer
import src.analytics_mongo as mongo

def api_hospital(ruta_api:str):
    try:
        response = requests.get(ruta_api, timeout=5)

        response.raise_for_status()

        return response.json()

    except requests.exceptions.HTTPError as http_error:
        raise ConnectionError(f"Error HTTP: {http_error}") from http_error

    except requests.exceptions.ConnectTimeout as timeout:
        raise ConnectionError(f"Tiempo de espera demasiado largo: {timeout}") from timeout

    except requests.exceptions.ConnectionError as conection:
        raise ConnectionError(f"Ocurrió un error con la conexión: {conection}") from conection

    except requests.exceptions.RequestException as exception:
        raise ConnectionError(f"Ocurrió un error inesperado: {exception}") from exception

def worker_urgencias(r):
    print("Iniciando el worker de urgencias...")
    # Bucle para que este ejecutandose el worker de urgencias
    while True:
        try:
            datos = api_hospital(config.RUTA_API)
            nuevos_ingresos = datos["nuevos_ingresos"]
            altas = datos["pacientes_alta"]

            print(f"Pacientes nuevos: {len(nuevos_ingresos)}")
            print(f"Pacientes dados de alta: {len(altas)}")

            # Comprobar si hay pacientes dados de alta y procesarlos
            if not altas:
                print("No hay pacientes dados de alta en este momento.")
            else:
                for alta in altas:
                    # Dar de alta al paciente enviando los datos a mongo, una vez confirmado que se ha almacenado en mongo se da de alta en redis
                    if actualizar_alta_mongo(alta):
                        triage_redis.alta_paciente(r, alta)
                        print(f"Paciente {alta['id_episodio']} dado de alta.")

            # Comprobar si hay nuevos ingresos y procesarlos
            if not nuevos_ingresos:
                print("No hay nuevos ingresos en este momento.")
            else:

                for ingreso in nuevos_ingresos:
                    # Anonimizar los datos del paciente antes de enviarlos a Mongo
                    paciente_anonimo = copy.deepcopy(ingreso)

                    paciente_anonimo['datos_admision']['sip_paciente'] = anonymizer.anonimizar_sip(ingreso['datos_admision']['sip_paciente'], config.HMAC_SECRET)
                    paciente_anonimo['datos_admision']['edad'] = anonymizer.agrupar_edad(ingreso['datos_admision']['edad'])
                    paciente_anonimo['datos_admision'].pop('nombre', None)

                    print(f"Paciente anonimizado sip:{paciente_anonimo['datos_admision']['sip_paciente']}, rango de edad:{paciente_anonimo['datos_admision']['edad']} ")
                    
                    if añadir_paciente_mongo(paciente_anonimo):
                        triage_redis.añadir_paciente_cola_espera(r, ingreso)
                        print(f"Paciente {ingreso['id_episodio']} añadido a la cola de espera.")
                    else:
                        print(f"El episodio {ingreso['id_episodio']} esta repetido y no se ha procesado")   

            # Añadir pacientes mientras haya boxes libres por si se libera mas de uno
            while triage_redis.obtener_box_libre(r) is not None:
                if not triage_redis.añadir_paciente_box(r):
                    break

            # printear el estado de los boxes
            for box in triage_redis.obtener_boxes(r):
                print(f"Box {box} está {box['estado']}.")

        except requests.exceptions.RequestException as request_error:
            print(f"Error en la solicitud HTTP: {request_error}")
        
        except Exception as error:
            print(f"Error en el worker: {error}")
        time.sleep(5)  # Espera 5 segundos antes de la siguiente iteración

def añadir_paciente_mongo(paciente):
    resultado = mongo.cargar_episodios([paciente])
    return resultado["insertados"] > 0

def actualizar_alta_mongo(alta):
    return mongo.alta_paciente_mongo(alta)

def urgencias(r):
    worker_urgencias(r)

if __name__ == "__main__":
    urgencias()