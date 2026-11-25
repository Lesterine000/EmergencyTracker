import requests
import json
import time
import copy
import src.config as config
import src.triage_redis as triage_redis
import src.anonymizer as anonymizer
import src.analytics_mongo as mongo


def api_hospital(ruta_api: str):
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

    except ValueError as value_error:
        raise ConnectionError(f"Respuesta inválida de la API: {value_error}") from value_error


_altas_forzadas = {}  # id_episodio -> epoch en que se forzó el alta


def api_post(ruta_api: str, params: dict | None = None):
    try:
        response = requests.post(ruta_api, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        print(f"Error en POST {ruta_api}: {error}")
        return None


def sincronizar_censo(r):
    """Cierra en Mongo y libera en Redis los episodios ya no activos."""
    try:
        estado = api_hospital(config.RUTA_API_ESTADO)
        if not estado or "ids_activos" not in estado:
            return

        boxes_huerfanos, cola_huerfana = triage_redis.obtener_huerfanos(
            r, estado["ids_activos"]
        )

        for box_id, id_episodio in boxes_huerfanos:
            alta_guardada = mongo.alta_paciente_mongo({
                "id_episodio": id_episodio,
                "timestamp_alta": time.time(),
                "destino_alta": "alta_administrativa_demo",
            })

            if alta_guardada:
                triage_redis.liberar_box(r, box_id)
                _altas_forzadas.pop(id_episodio, None)
                print(
                    f"Box {box_id}: {id_episodio} ya no está activo; "
                    "cerrado administrativamente."
                )
            else:
                print(
                    f"No se pudo guardar el cierre de {id_episodio}; "
                    "el box se mantiene y se reintentará."
                )

        for episodio in cola_huerfana:
            r.zrem("urgencias:cola_espera", episodio)
            print(f"Episodio {episodio} ya no está activo; se retira de la cola.")

    except Exception as error:
        print(f"No se pudo sincronizar el censo: {error}")


def forzar_alta(id_episodio):
    resultado = api_post(
        config.RUTA_API_FORZAR_ALTA,
        {"id_episodio": id_episodio},
    )
    if resultado is not None:
        print(f"Alta forzada en el simulador para {id_episodio}.")
        return True
    return False


def cerrar_box_administrativamente(r, id_episodio, box_id):
    print(
        f"El alta de {id_episodio} no llegó a tiempo; "
        f"se intenta cerrar el box {box_id} administrativamente."
    )

    alta_guardada = mongo.alta_paciente_mongo({
        "id_episodio": id_episodio,
        "timestamp_alta": time.time(),
        "destino_alta": "alta_administrativa_demo",
    })

    if alta_guardada:
        triage_redis.alta_paciente(r, {"id_episodio": id_episodio})
        _altas_forzadas.pop(id_episodio, None)
    else:
        print(
            f"No se pudo guardar el alta de {id_episodio}; "
            "el box se mantiene y se reintentará."
        )


def liberar_boxes_expirados(r):
    if config.MAX_STAY_MIN <= 0:
        return

    ahora = time.time()

    for box in triage_redis.obtener_boxes(r):
        if box["estado"] != "OCUPADO":
            continue

        entrada = box["hora_entrada_ts"]
        if not entrada:
            continue

        minutos = (ahora - entrada) / 60
        if minutos < config.MAX_STAY_MIN:
            continue

        id_episodio = box["id_episodio"]
        forzada_en = _altas_forzadas.get(id_episodio)

        if forzada_en is None:
            print(
                f"Box {box['box_id']} ocupado {minutos:.1f} min "
                f"(máximo {config.MAX_STAY_MIN}); forzando alta de {id_episodio}."
            )
            if forzar_alta(id_episodio):
                _altas_forzadas[id_episodio] = ahora
            else:
                print(
                    f"No se pudo forzar el alta de {id_episodio}; "
                    "se reintentará en el próximo ciclo."
                )

        elif ahora - forzada_en >= 30:
            cerrar_box_administrativamente(r, id_episodio, box["box_id"])


def worker_urgencias(r):
    print("Iniciando el worker de urgencias...")
    ciclo = 0

    while True:
        try:
            # 1) Forzar altas de boxes que superan el tiempo máximo de demo
            liberar_boxes_expirados(r)

            # 2) Consultar novedades de la API
            datos = api_hospital(config.RUTA_API)
            nuevos_ingresos = datos["nuevos_ingresos"]
            altas = datos["pacientes_alta"]

            print(f"Pacientes nuevos: {len(nuevos_ingresos)}")
            print(f"Pacientes dados de alta: {len(altas)}")

            if not altas:
                print("No hay pacientes dados de alta en este momento.")
            else:
                for alta in altas:
                    if actualizar_alta_mongo(alta):
                        triage_redis.alta_paciente(r, alta)
                        _altas_forzadas.pop(alta["id_episodio"], None)
                        print(f"Paciente {alta['id_episodio']} dado de alta.")

            if not nuevos_ingresos:
                print("No hay nuevos ingresos en este momento.")
            else:
                for ingreso in nuevos_ingresos:
                    paciente_anonimo = copy.deepcopy(ingreso)

                    paciente_anonimo['datos_admision']['sip_paciente'] = anonymizer.anonimizar_sip(
                        ingreso['datos_admision']['sip_paciente'],
                        config.HMAC_SECRET
                    )
                    paciente_anonimo['datos_admision']['edad'] = anonymizer.agrupar_edad(
                        ingreso['datos_admision']['edad']
                    )
                    paciente_anonimo['datos_admision'].pop('nombre', None)

                    print(
                        f"Paciente anonimizado sip:{paciente_anonimo['datos_admision']['sip_paciente']}, "
                        f"rango de edad:{paciente_anonimo['datos_admision']['edad']} "
                    )

                    if añadir_paciente_mongo(paciente_anonimo):
                        triage_redis.añadir_paciente_cola_espera(r, ingreso)
                        print(f"Paciente {ingreso['id_episodio']} añadido a la cola de espera.")
                    else:
                        print(f"El episodio {ingreso['id_episodio']} esta repetido y no se ha procesado")

            while triage_redis.obtener_box_libre(r) is not None:
                if not triage_redis.añadir_paciente_box(r):
                    break

            for box in triage_redis.obtener_boxes(r):
                print(f"Box {box} está {box['estado']}.")

            # 3) Reconciliar con el censo del simulador cada 5 minutos aprox.
            ciclo += 1
            if ciclo % 60 == 0:
                sincronizar_censo(r)

        except requests.exceptions.RequestException as request_error:
            print(f"Error en la solicitud HTTP: {request_error}")

        except Exception as error:
            print(f"Error en el worker: {error}")

        time.sleep(5)


def añadir_paciente_mongo(paciente):
    resultado = mongo.cargar_episodios([paciente])
    return resultado["insertados"] > 0


def actualizar_alta_mongo(alta):
    return mongo.alta_paciente_mongo(alta)


def urgencias(r):
    triage_redis.inicializar_redis(r)

    if config.RESET_REDIS:
        triage_redis.reiniciar_estado(r)
    else:
        sincronizar_censo(r)

    worker_urgencias(r)


if __name__ == "__main__":
    import redis
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)
    urgencias(r)