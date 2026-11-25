from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError, PyMongoError
from config import MONGO_URI, MONGO_DB, MONGO_COLLECTION

# ─── CONEXIÓN ────────────────────────────────────────────────────────────────
# Fix #1: Cliente global para reutilizar el pool de conexiones y evitar fugas.
# Fix #6: pandas eliminado del nivel de módulo; se importa solo en __main__.

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
    de edad. La conversión de edad numérica a rango (ej: 23 → "20-29") se
    hace directamente en el pipeline, sin depender del ETL ni del anonymizer.
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
            # Convertir edad numérica a rango decenal: 23 → "20-29", 0 → "0-9"
            # Se guarda también limite_inferior (numérico) para ordenar correctamente.
            {
                "$addFields": {
                    "limite_inferior": {"$multiply": [{"$floor": {"$divide": ["$edad", 10]}}, 10]},
                    "grupo_edad": {
                        "$concat": [
                            {"$toString": {"$multiply": [{"$floor": {"$divide": ["$edad", 10]}}, 10]}},
                            "-",
                            {"$toString": {"$subtract": [{"$multiply": [{"$add": [{"$floor": {"$divide": ["$edad", 10]}}, 1]}, 10]}, 1]}}
                        ]
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

    Fix #3 + #4: convierte timestamp_alta a epoch float antes de escribir,
    para mantener coherencia con el formato que espera el pipeline de agregación.
    Captura errores de conexión.
    """
    try:
        col = get_collection()
        id_episodio = paciente["id_episodio"]

        # Fix #3: garantizar que timestamp_alta sea epoch float
        ts_alta = paciente["timestamp_alta"]
        if hasattr(ts_alta, "timestamp"):        # es un datetime de Python
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
                    "destino_alta":   paciente["destino_alta"]
                }
            }
        )

        if resultado.matched_count > 0:
            print(f"Alta del episodio {id_episodio} registrada en mongo")
            return True

        print(f"El episodio {id_episodio} no existe en mongo")
        return False

    except PyMongoError as e:
        print(f"[ERROR] Fallo de conexión en alta_paciente_mongo: {e}")
        return False
    except ValueError as e:
        print(f"[ERROR] Dato inválido en alta_paciente_mongo: {e}")
        return False


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Fix #6: pandas importado solo cuando se ejecuta este script directamente
    import pandas as pd
    from etl_historico import etl_historico
    from config import RUTA_CSV, RUTA_JSON

    # Fix #2: índice creado una sola vez al arrancar
    init_index()

    print("Ejecutando ETL...")
    df = etl_historico(RUTA_CSV, RUTA_JSON)

    # Convertir timestamps a epoch float para que $subtract funcione en Mongo
    for campo in ["timestamp_llegada", "timestamp_alta"]:
        if campo in df.columns:
            df[campo] = df[campo].apply(
                lambda x: x.timestamp() if pd.notna(x) else None
            )

    documentos = df.to_dict(orient="records")

    print("Cargando en MongoDB...")
    cargar_episodios(documentos)

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