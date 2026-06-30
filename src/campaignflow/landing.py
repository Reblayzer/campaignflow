"""Blob landing zone client for the bronze layer.

Wraps the Azure Blob SDK (Azurite locally, real Azure in production) behind a
small interface: ensure the container exists, then upload a raw campaign file
and hand back an ``az://`` URL that DuckDB's azure extension can read directly.
"""

import os
from pathlib import Path

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from campaignflow.config import AZURITE_CONNECTION_STRING, LANDING_CONTAINER


def resolve_connection_string(connection_string: str | None = None) -> str:
    """Explicit string wins, then the environment, then the Azurite default."""
    return (
        connection_string
        or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        or AZURITE_CONNECTION_STRING
    )


class LandingZone:
    """Provision a blob container and land raw files into it."""

    def __init__(
        self, connection_string: str | None = None, container: str = LANDING_CONTAINER
    ) -> None:
        self.connection_string = resolve_connection_string(connection_string)
        self.container = container
        self._service = BlobServiceClient.from_connection_string(self.connection_string)

    def ensure_container(self) -> None:
        """Create the container if it does not already exist (idempotent)."""
        try:
            self._service.create_container(self.container)
        except ResourceExistsError:
            pass

    def upload(self, local_path: Path, blob_name: str | None = None) -> str:
        """Upload a local file to the container; return its ``az://`` URL."""
        blob_name = blob_name or Path(local_path).name
        with open(local_path, "rb") as handle:
            self._service.get_blob_client(self.container, blob_name).upload_blob(
                handle, overwrite=True
            )
        return f"az://{self.container}/{blob_name}"
