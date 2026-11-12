from pathlib import Path
import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

RUTA_CSV = BASE_DIR / "data" / "admisiones_historico.csv"
RUTA_JSON = BASE_DIR / "data" / "partes_clinicos.json"

RUTA_API = "http://10.201.59.248:28000/api/v1/urgencias/novedades"

# MongoDB — host "mongodb" es el nombre del servicio en docker-compose
MONGO_URI        = "mongodb://localhost:27017"
MONGO_DB         = "hospital"
MONGO_COLLECTION = "episodios_urgencias"


# Clave secreta para anonimizar los SIP
HMAC_SECRET = os.getenv("HMAC_SECRET")

if not HMAC_SECRET:
    raise ValueError("No se ha encontrado HMAC_SECRET en el archivo .env")