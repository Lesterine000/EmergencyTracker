import requests
import json
def api_hospital():
    url = "http://10.201.59.248:28000/api/v1/urgencias/novedades"
    response = requests.get(url)
    print(response.status_code)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4))

api_hospital()