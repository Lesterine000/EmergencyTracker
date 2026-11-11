import pandas as pd
from pymongo import MongoClient, ASCENDING
from pymongo.errors import BulkWriteError
from config import MONGO_URI, MONGO_DB, MONGO_COLLECTION

# CONEXIÓN
def get_collection():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB][MONGO_COLLECTION]

# CARGA
def cargar_episodios(documentos: list[dict]) -> dict:
    col = get_collection()
    col.create_index([("id_episodio", ASCENDING)], unique=True)

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


# CONSULTA 1: Estancia media por categoría patológica
def estancia_media_por_patologia() -> list[dict]:
    """
    Tiempo medio de estancia (minutos) por categoria_patologia.
    Solo episodios cerrados (timestamp_alta no nulo).
    """
    col = get_collection()

    pipeline = [
        {
            "$match": {
                "timestamp_alta":       {"$exists": True, "$ne": None},
                "timestamp_llegada":    {"$exists": True, "$ne": None},
                "categoria_patologia":  {"$exists": True, "$ne": None}
            }
        },
        {
            "$addFields": {
                "estancia_min": {
                    "$divide": [
                        {"$subtract": ["$timestamp_alta", "$timestamp_llegada"]},
                        60
                    ]
                }
            }
        },
        # Descartar duraciones imposibles (negativas o más de 7 días)
        {
            "$match": {
                "estancia_min": {"$gt": 0, "$lt": 10080}
            }
        },
        {
            "$group": {
                "_id": "$categoria_patologia",
                "estancia_media_min": {"$avg": "$estancia_min"},
                "total_episodios":    {"$sum": 1}
            }
        },
        {"$sort": {"estancia_media_min": -1}},
        {
            "$project": {
                "_id": 0,
                "categoria_patologia": "$_id",
                "estancia_media_min":  {"$round": ["$estancia_media_min", 2]},
                "total_episodios":     1
            }
        }
    ]
    return list(col.aggregate(pipeline))

# CONSULTA 2: Destino al alta por grupo de edad decenal
def destino_alta_por_grupo_edad() -> list[dict]:

    #Distribución porcentual de destino_alta (domicilio / ingreso_planta)
    #agrupada por rangos decenales de edad.
    col = get_collection()

    pipeline = [
        {
            "$match": {
                "destino_alta": {"$exists": True, "$nin": [None, "Desconocido"]},
                "edad":         {"$exists": True, "$gt": 0, "$lt": 130}
            }
        },
        # Rango decenal: "60-69", "70-79", etc.
        {
            "$addFields": {
                "grupo_edad": {
                    "$concat": [
                        {"$toString": {
                            "$multiply": [{"$floor": {"$divide": ["$edad", 10]}}, 10]
                        }},
                        "-",
                        {"$toString": {
                            "$subtract": [
                                {"$multiply": [
                                    {"$add": [{"$floor": {"$divide": ["$edad", 10]}}, 1]},
                                    10
                                ]},
                                1
                            ]
                        }}
                    ]
                }
            }
        },
        # Contar por grupo + destino
        {
            "$group": {
                "_id": {"grupo_edad": "$grupo_edad", "destino_alta": "$destino_alta"},
                "count": {"$sum": 1}
            }
        },
        # Reagrupar por grupo_edad para calcular totales y porcentajes
        {
            "$group": {
                "_id": "$_id.grupo_edad",
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
        {"$sort": {"_id": 1}},
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

# MAIN
if __name__ == "__main__":
    from etl_historico import etl_historico
    from config import RUTA_CSV, RUTA_JSON

    print("Ejecutando ETL...")
    df = etl_historico(RUTA_CSV, RUTA_JSON)

    # Convertir timestamps a epoch float para que $subtract funcione en Mongo
    for col in ["timestamp_llegada", "timestamp_alta"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x.timestamp() if pd.notna(x) else None
            )

    import pandas as pd
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