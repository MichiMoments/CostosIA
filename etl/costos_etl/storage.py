"""Lectura y escritura de los archivos del ETL: carpeta local o Azure Blob Storage."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Protocol

from .config import Config


class Storage(Protocol):
    def read_json(self, name: str) -> Any: ...
    def write_json(self, name: str, data: Any, *, compact: bool = False) -> str: ...
    def write_raw(self, name: str, text: str) -> str: ...


def _dumps(data: Any, compact: bool) -> str:
    if compact:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=2)


class LocalStorage:
    def __init__(self, data_dir: Path, raw_dir: Path):
        self.data_dir = Path(data_dir)
        self.raw_dir = Path(raw_dir)

    def read_json(self, name: str) -> Any:
        with open(self.data_dir / name, encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, name: str, data: Any, *, compact: bool = False) -> str:
        return self._write_atomic(self.data_dir / name, _dumps(data, compact))

    def write_raw(self, name: str, text: str) -> str:
        return self._write_atomic(self.raw_dir / name, text, encoding="utf-8-sig")

    @staticmethod
    def _write_atomic(path: Path, text: str, encoding: str = "utf-8") -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
                f.write(text)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        return str(path)


class BlobStorage:
    def __init__(self, account: str, container: str, raw_container: str):
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        service = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=DefaultAzureCredential())
        self.data = service.get_container_client(container)
        self.raw = service.get_container_client(raw_container)

    def read_json(self, name: str) -> Any:
        return json.loads(self.data.download_blob(name).readall().decode("utf-8"))

    def write_json(self, name: str, data: Any, *, compact: bool = False) -> str:
        from azure.storage.blob import ContentSettings

        blob = self.data.upload_blob(
            name, _dumps(data, compact).encode("utf-8"), overwrite=True,
            content_settings=ContentSettings(content_type="application/json; charset=utf-8"),
        )
        return blob.url

    def write_raw(self, name: str, text: str) -> str:
        from azure.storage.blob import ContentSettings

        blob = self.raw.upload_blob(
            name, text.encode("utf-8-sig"), overwrite=True,
            content_settings=ContentSettings(content_type="text/csv; charset=utf-8"),
        )
        return blob.url


def get_storage(cfg: Config) -> Storage:
    if cfg.use_blob:
        return BlobStorage(cfg.storage_account, cfg.storage_container, cfg.storage_raw_container)
    return LocalStorage(cfg.output_dir, cfg.raw_dir)
