"""
MODULE: azure_storage
WHAT: Azure Blob Storage integration for reading campaign briefs and uploading
generated outputs. Both directions use the same connection string and container.
DECISION: Symmetric read/write against Azure Blob satisfies the assignment's
storage requirement and mirrors how enterprise clients actually manage assets --
briefs and product assets live in Blob, generated creatives are written back.
PRODUCTION ALTERNATIVE: Managed identity instead of connection string, separate
containers for inputs and outputs with RBAC, CDN in front of output container.
"""

import json
import os
from pathlib import Path


def _client():
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        raise ImportError(
            "azure-storage-blob is required for Azure integration. "
            "Run: pip install azure-storage-blob"
        )
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    if not conn_str:
        raise EnvironmentError(
            "AZURE_STORAGE_CONNECTION_STRING is not set. Add it to your .env file."
        )
    return BlobServiceClient.from_connection_string(conn_str)


def _container():
    return os.getenv("AZURE_STORAGE_CONTAINER", "creative-pipeline")


def download_brief(blob_name):
    """
    Download a campaign brief JSON from Azure Blob and return as a parsed dict.
    blob_name is the path within the container, e.g. 'briefs/viva_summer.json'.
    """
    client = _client()
    blob = client.get_blob_client(container=_container(), blob=blob_name)
    data = blob.download_blob().readall()
    return json.loads(data)


def upload_outputs(result, campaign_id):
    """
    Upload all generated creatives to Azure Blob after a successful pipeline run.
    Blob path: {campaign_id}/{product_id}/{format}.png
    Returns list of uploaded blob names.
    """
    client = _client()
    container = _container()
    uploaded = []

    for product_id, paths in result.get("outputs_by_product", {}).items():
        for path in paths:
            blob_name = "{}/{}/{}".format(campaign_id, product_id, Path(path).name)
            blob_client = client.get_blob_client(container=container, blob=blob_name)
            with open(path, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)
            uploaded.append(blob_name)

    return uploaded
