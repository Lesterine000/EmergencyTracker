from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

RUTA_CSV = BASE_DIR / "data" / "admisiones_historico.csv"
RUTA_JSON = BASE_DIR / "data" / "partes_clinicos.json"

RUTA_API = "http://10.201.59.248:28000/api/v1/urgencias/novedades"

# MongoDB — host "mongodb" es el nombre del servicio en docker-compose
MONGO_URI        = "mongodb://localhost:27017"
MONGO_DB         = "hospital"
MONGO_COLLECTION = "episodios_urgencias"