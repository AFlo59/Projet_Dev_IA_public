# azure_blob_setup.py

import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

load_dotenv()  # lit automatiquement .env

AZ_CONN_STR     = os.getenv('AZURE__Blob__ConnectionString')
JSON_CONTAINER  = os.getenv('AZURE__Blob__JsonContainer', 'jsons')
IMAGE_CONTAINER = os.getenv('AZURE__Blob__ImageContainer', 'images')

if not AZ_CONN_STR:
    raise RuntimeError("❌ AZURE__Blob__ConnectionString non défini dans .env")

_blob_service = BlobServiceClient.from_connection_string(AZ_CONN_STR)

json_container_client  = _blob_service.get_container_client(JSON_CONTAINER)
image_container_client = _blob_service.get_container_client(IMAGE_CONTAINER)

# Création des containers si nécessaire
from azure.core.exceptions import ResourceExistsError

# … after you’ve built your json_container_client and image_container_client …

# ensure JSON container exists
try:
    json_container_client.create_container()
except ResourceExistsError:
    pass

# ensure Images container exists
try:
    image_container_client.create_container()
except ResourceExistsError:
    pass

