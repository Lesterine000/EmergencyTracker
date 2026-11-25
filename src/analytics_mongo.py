from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError, PyMongoError
from src.config import MONGO_URI, MONGO_DB, MONGO_COLLECTION

# ─── CONEXIÓN ────────────────────────────────────────────────────────────────
# Fix #1: Cliente global para reutilizar el pool de conexiones y evitar fugas.
# Fix #6: pandas eliminado del nivel de módulo; se importa solo cuando hace falta.

_client = None

def _get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client

def get_collection():
    return _get_client()[MONGO_DB][MONGO_COLLECTION]


# ─── INICIALIZACIÓN DEL ÍNDICE ───────────────────────────────────────────────
# Fix #2: El índice único se crea una sola vez al arrancar, no en cada carga.

def init_index():
    """Llama a esta función UNA VEZ al iniciar la aplicación."""
    try:
        col = get_collection()
        col.create_index([("id_episodio", ASCENDING)], unique=True)
    except PyMongoError as e:
        print(f"[ERROR] No se pudo crear el índice: {e}")


# ─── CARGA ───────────────────────────────────────────────────────────────────

def cargar_episodios(documentos: list[dict]) -> dict:
    """
    Inserta documentos en MongoDB ignorando duplicados por id_episodio.
    Los timestamps (timestamp_llegada, timestamp_alta) deben llegar como
    epoch float (segundos desde 1970-01-01) para que las agregaciones funcionen.
    """
    # Fix #4: try/except para errores de conexión
    try:
        col = get_collection()
        insertados, duplicados = 0, 0
        try:
            result = col.insert_many(documentos, ordered=False)
            insertados = len(result.inserted_ids)
        except BulkWriteError as bwe:
            insertados = bwe.details.get("nInserted", 0)
            duplicados = len(bwe.details.get("writeErrors", []))
            print(f"{duplicados} duplicados ignorados (ya existían en BD).")

        print(f"Insertados: {insertados} | Omitidos: {duplicados}")
        return {"insertados": insertados, "duplicados": duplicados}

    except PyMongoError as e:
        print(f"[ERROR] Fallo de conexión en cargar_episodios: {e}")
        return {"insertados": 0, "duplicados": 0}


def cargar_historico(df_anonimizado) -> dict:
    """
    Carga en MongoDB el histórico YA ANONIMIZADO.

    Convierte timestamp_llegada y timestamp_alta a epoch (segundos), que es el
    formato que necesitan las agregaciones para restar las fechas, y garantiza
    que el índice único existe antes de insertar.

    El DataFrame debe venir de anonymizer.anonimizar_dataframe(), es decir:
    SIP con HMAC, edad en rangos decenales ("30-39") y sin nombres.
    """
    import pandas as pd

    df = df_anonimizado.copy()

    for campo in ("timestamp_llegada", "timestamp_alta"):
        if campo in df.columns:
            df[campo] = df[campo].apply(
                lambda x: (
                    None if pd.isna(x)
                    else (x.timestamp() if hasattr(x, "timestamp") else x)
                )
            )

    init_index()
    return cargar_episodios(df.to_dict(orient="records"))


# ─── CONSULTA 1: Estancia media por categoría patológica ────────────────────

def estancia_media_por_patologia() -> list[dict]:
    """
    Tiempo medio de estancia (minutos) por categoria_patologia.
    Solo episodios cerrados (timestamp_alta no nulo).

    REQUISITO: timestamp_llegada y timestamp_alta deben ser epoch en segundos
    (float/int). El operador $subtract entre dos números da la diferencia en
    la misma unidad; dividir por 60 convierte segundos → minutos.
    Compatible con los datos históricos y los ingresos de la API.
    """
    try:
        col = get_collection()

        pipeline = [
            # Normalizar los campos del histórico y de la API
            {
                "$addFields": {
                    "timestamp_llegada": {
                        "$ifNull": [
                            "$timestamp_llegada",
                            "$datos_admision.timestamp_llegada"
                        ]
                    },
                    "categoria_patologia": {
                        "$ifNull": [
                            "$triaje_manchester.categoria_patologia",
                            "$datos_triaje.categoria_patologia"
                        ]
                    }
                }
            },

            # Comprobar que existen los campos y son válidos
            {
                "$match": {
                    "timestamp_alta": {"$type": "number"},
                    "timestamp_llegada": {"$type": "number"},
                    "categoria_patologia": {"$type": "string"}
                }
            },

            # Calcular la estancia y normalizar la categoría
            {
                "$addFields": {
                    "categoria_patologia": {
                        "$toLower": "$categoria_patologia"
                    },
                    "estancia_min": {
                        "$divide": [
                            {
                                "$subtract": [
                                    "$timestamp_alta",
                                    "$timestamp_llegada"
                                ]
                            },
                            60
                        ]
                    }
                }
            },

            # Descartar duraciones imposibles
            {
                "$match": {
                    "estancia_min": {"$gt": 0, "$lt": 10080}
                }
            },

            # Agrupar por categoría patológica
            {
                "$group": {
                    "_id": "$categoria_patologia",
                    "estancia_media_min": {"$avg": "$estancia_min"},
                    "total_episodios": {"$sum": 1}
                }
            },

            {"$sort": {"estancia_media_min": -1}},

            # Formatear el resultado
            {
                "$project": {
                    "_id": 0,
                    "categoria_patologia": "$_id",
                    "estancia_media_min": {
                        "$round": ["$estancia_media_min", 2]
                    },
                    "total_episodios": 1
                }
            }
        ]

        return list(col.aggregate(pipeline))

    except PyMongoError as e:
        print(f"[ERROR] Fallo en estancia_media_por_patologia: {e}")
        return []


# ─── CONSULTA 2: Destino al alta por grupo de edad decenal ──────────────────

def destino_alta_por_grupo_edad() -> list[dict]:
    """
    Distribución porcentual de destino_alta agrupada por rangos decenales
    de edad.

    Acepta dos formatos de edad:
      - numérica (histórico antiguo): 23 → "20-29"
      - rango ya anonimizado (anonymizer): "20-29" se usa tal cual

    Así la consulta funciona antes y después de anonimizar el histórico, sin
    tener que recargar los documentos ya existentes.
    """
    # Fix #4: try/except para errores de conexión
    try:
        col = get_collection()

        pipeline = [
            {
                "$match": {
                    "destino_alta": {
                        "$exists": True,
                        "$nin": [None, "desconocido"]
                    },
                    "edad": {
                        "$exists": True,
                        "$nin": [None, "desconocido"]
                    }
                }
            },
            # Normalizar la edad:
            #   - histórico anonimizado → ya viene como "20-29"
            #   - histórico numérico     → 23 se convierte en "20-29"
            {
                "$addFields": {
                    "grupo_edad": {
                        "$cond": [
                            {"$eq": [{"$type": "$edad"}, "string"]},
                            "$edad",
                            {
                                "$concat": [
                                    {"$toString": {"$multiply": [{"$floor": {"$divide": ["$edad", 10]}}, 10]}},
                                    "-",
                                    {"$toString": {"$subtract": [{"$multiply": [{"$add": [{"$floor": {"$divide": ["$edad", 10]}}, 1]}, 10]}, 1]}}
                                ]
                            }
                        ]
                    }
                }
            },
            # Orden numérico del grupo: "20-29" → 20
            {
                "$addFields": {
                    "limite_inferior": {
                        "$toInt": {
                            "$arrayElemAt": [{"$split": ["$grupo_edad", "-"]}, 0]
                        }
                    }
                }
            },
            # Contar por grupo + destino
            {
                "$group": {
                    "_id": {"grupo_edad": "$grupo_edad", "destino_alta": "$destino_alta", "limite_inferior": "$limite_inferior"},
                    "count": {"$sum": 1}
                }
            },
            # Reagrupar por grupo_edad para calcular totales y porcentajes
            {
                "$group": {
                    "_id": "$_id.grupo_edad",
                    "limite_inferior": {"$first": "$_id.limite_inferior"},
                    "destinos": {
                        "$push": {"destino": "$_id.destino_alta", "count": "$count"}
                    },
                    "total": {"$sum": "$count"}
                }
            },
            {
                "$addFields": {
                    "distribucion": {
                        "$map": {
                            "input": "$destinos",
                            "as": "d",
                            "in": {
                                "destino": "$$d.destino",
                                "count":   "$$d.count",
                                "porcentaje": {
                                    "$round": [
                                        {"$multiply": [
                                            {"$divide": ["$$d.count", "$total"]}, 100
                                        ]},
                                        1
                                    ]
                                }
                            }
                        }
                    }
                }
            },
            {"$sort": {"limite_inferior": 1}},
            {
                "$project": {
                    "_id": 0,
                    "grupo_edad":      "$_id",
                    "total_episodios": "$total",
                    "distribucion":    1
                }
            }
        ]
        return list(col.aggregate(pipeline))

    except PyMongoError as e:
        print(f"[ERROR] Fallo en destino_alta_por_grupo_edad: {e}")
        return []


# ─── ALTA DE PACIENTE ────────────────────────────────────────────────────────

def alta_paciente_mongo(paciente: dict) -> bool:
    """
    Registra el alta de un episodio en MongoDB.

    Usa upsert: si el ingreso no se vio (paciente anterior al arranque del
    worker), el alta se crea igualmente para poder liberar el box en Redis.
    """
    try:
        col = get_collection()
        id_episodio = paciente["id_episodio"]

        ts_alta = paciente["timestamp_alta"]
        if hasattr(ts_alta, "timestamp"):        # datetime de Python
            ts_alta = ts_alta.timestamp()
        elif not isinstance(ts_alta, (int, float)):
            raise ValueError(
                f"timestamp_alta tiene tipo inesperado: {type(ts_alta)}"
            )

        resultado = col.update_one(
            {"id_episodio": id_episodio},
            {
                "$set": {
                    "timestamp_alta": ts_alta,
                    "destino_alta": paciente["destino_alta"],
                },
                "$setOnInsert": {"id_episodio": id_episodio},
            },
            upsert=True,
        )

        if resultado.matched_count > 0 or resultado.upserted_id is not None:
            print(f"Alta del episodio {id_episodio} registrada en mongo")
            return True

        print(f"No se pudo registrar el alta del episodio {id_episodio}")
        return False

    except PyMongoError as e:
        print(f"[ERROR] Fallo de conexión en alta_paciente_mongo: {e}")
        return False
    except ValueError as e:
        print(f"[ERROR] Dato inválido en alta_paciente_mongo: {e}")
        return False


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.etl_historico import etl_historico
    from src.anonymizer import anonimizar_dataframe
    from src.config import RUTA_CSV, RUTA_JSON, HMAC_SECRET

    print("Ejecutando ETL...")
    df = etl_historico(RUTA_CSV, RUTA_JSON)

    print("Anonimizando histórico...")
    df = anonimizar_dataframe(df, HMAC_SECRET)

    print("Cargando en MongoDB...")
    cargar_historico(df)

    print("\n──────────────────────────────────────────")
    print("  Estancia media (min) por categoría patológica")
    print("──────────────────────────────────────────")
    for r in estancia_media_por_patologia():
        print(f"  {r['categoria_patologia']:<25} {r['estancia_media_min']:>8.2f} min"
              f"   (n={r['total_episodios']})")

    print("\n──────────────────────────────────────────")
    print("  Destino al alta (%) por grupo de edad")
    print("──────────────────────────────────────────")
    for r in destino_alta_por_grupo_edad():
        print(f"\n  Grupo {r['grupo_edad']}  (total: {r['total_episodios']})")
        for d in sorted(r["distribucion"], key=lambda x: x["destino"]):
            print(f"    {d['destino']:<20} {d['count']:>4} eps  ({d['porcentaje']}%)")