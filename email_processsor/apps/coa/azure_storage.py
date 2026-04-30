from azure.storage.blob import BlobServiceClient
import os
import uuid


def upload_to_azure(file_path):

    conn_str = os.getenv("AZURE_STORAGE_CONTAINER_STRING")
    container = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

    blob_service = BlobServiceClient.from_connection_string(conn_str)

    original_name = file_path.split("/")[-1]
    blob_name = f"{uuid.uuid4()}_{original_name}"

    blob_client = blob_service.get_blob_client(
        container=container,
        blob=blob_name
    )

    with open(file_path, "rb") as data:
        blob_client.upload_blob(data)

    return blob_client.url