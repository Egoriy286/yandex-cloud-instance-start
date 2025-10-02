import time
import jwt
import json

import requests

key_path = 'authorized_key.json'

# Чтение закрытого ключа из JSON-файла
with open(key_path, 'r') as f:
  obj = f.read() 
  obj = json.loads(obj)
  private_key = obj['private_key']
  key_id = obj['id']
  service_account_id = obj['service_account_id']

sa_key = {
    "id": key_id,
    "service_account_id": service_account_id,
    "private_key": private_key
}

def create_jwt():
    now = int(time.time())
    payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': service_account_id,
            'iat': now,
            'exp': now + 3600
        }

    # Формирование JWT.
    encoded_token = jwt.encode(
        payload,
        private_key,
        algorithm='PS256',
        headers={'kid': key_id}
    )

    #print(encoded_token)

    return encoded_token

def get_iam_token():
    jwt_token = create_jwt()

    url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
    headers = {"Content-Type": "application/json"}
    payload = {"jwt": jwt_token}

    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    iam_token = data["iamToken"]
    expires_at = data["expiresAt"]

    return iam_token, expires_at
