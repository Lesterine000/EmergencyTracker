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

# ─── DEMO: ROTACIÓN DE BOXES ────────────────────────────────────────────────
# Minutos máximos que un paciente puede ocupar un box antes de forzar su alta.
# 0 desactiva la rotación automática (se espera el alta real de la API).
try:
    MAX_STAY_MIN = int(os.getenv("MAX_STAY_MIN", "3"))
except ValueError:
    MAX_STAY_MIN = 3

# 1 = vaciar cola y boxes al arrancar (demo limpia); 0 = conservar y sincronizar.
RESET_REDIS = os.getenv("RESET_REDIS", "0") == "1"

# Endpoints de apoyo del simulador
RUTA_API_ESTADO = "http://10.201.59.248:28000/api/v1/simulador/estado"
RUTA_API_FORZAR_ALTA = "http://10.201.59.248:28000/api/v1/profesor/forzar-alta"