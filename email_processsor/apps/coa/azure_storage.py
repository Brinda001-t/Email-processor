from azure.storage.blob import BlobServiceClient
from pathlib import Path
import os


def upload_to_azure(file_path):

    conn_str = os.getenv("AZURE_STORAGE_CONTAINER_STRING")
    container = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

    blob_service = BlobServiceClient.from_connection_string(conn_str)

    blob_name = Path(file_path).name

    blob_client = blob_service.get_blob_client(
        container=container,
        blob=blob_name
    )

    with open(file_path, "rb") as data:
        blob_client.upload_blob(data)

    return blob_client.url