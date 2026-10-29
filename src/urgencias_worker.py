import requests
import json
def api_hospital(ruta_api:str):
    response = requests.get(ruta_api)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4))
