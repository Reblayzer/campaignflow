"""Create the bronze landing container in Azurite (idempotent).

Invoked by Terraform's local-exec for `target = "local"`. Kept standalone (no
campaignflow imports) so Terraform can run it without the package installed.
"""

import os
import sys

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient


def main() -> int:
    connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = os.environ["CONTAINER_NAME"]

    client = BlobServiceClient.from_connection_string(connection_string)
    try:
        client.create_container(container_name)
        print(f"created container '{container_name}'")
    except ResourceExistsError:
        print(f"container '{container_name}' already exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
