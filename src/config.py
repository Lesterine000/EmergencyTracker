from pathlib import Path
import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

RUTA_CSV = BASE_DIR / "data" / "admisiones_historico.csv"
RUTA_JSON = BASE_DIR / "data" / "partes_clinicos.json"

RUTA_API = "http://10.201.59.248:28000/api/v1/urgencias/novedades"

# Hosts de Redis y MongoDB
# Se leen de variables de entorno para que el mismo código funcione en local y en Docker:
#   - En local (python main.py) no hace falta definirlas: se usa "localhost".
#   - En Docker, docker-compose.yml las define con el nombre del servicio ("redis" y "mongodb").
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))

# MongoDB
MONGO_URI        = f"mongodb://{MONGO_HOST}:{MONGO_PORT}"
MONGO_DB         = "hospital"
MONGO_COLLECTION = "episodios_urgencias"


# Clave secreta para anonimizar los SIP
HMAC_SECRET = os.getenv("HMAC_SECRET")

if not HMAC_SECRET:
    raise ValueError("No se ha encontrado HMAC_SECRET en el archivo .env")