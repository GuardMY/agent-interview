"""File storage utilities for uploads."""

import uuid
from pathlib import Path

from fastapi import UploadFile


class FileStorage:
    """Simple local file storage for resume uploads."""

    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = Path(upload_dir).resolve()
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        (self._upload_dir / "temp").mkdir(exist_ok=True)

    async def save(self, file: UploadFile, subdir: str = "temp") -> tuple[str, int]:
        """Save an uploaded file. Returns (relative_path, file_size_bytes)."""
        ext = Path(file.filename or "upload").suffix or ".pdf"
        stored_name = f"{uuid.uuid4()}{ext}"
        target_dir = self._upload_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / stored_name

        size = 0
        with open(target_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                f.write(chunk)
                size += len(chunk)

        return str(target_path.relative_to(self._upload_dir.parent)), size

    def get_absolute_path(self, relative_path: str) -> Path:
        """Resolve a stored relative path to an absolute path."""
        base = self._upload_dir.parent
        return (base / relative_path).resolve()

    def delete(self, relative_path: str) -> None:
        """Delete a stored file."""
        path = self.get_absolute_path(relative_path)
        if path.exists():
            path.unlink()

    def move_to_session(self, relative_path: str, session_id: str) -> str:
        """Move a temp file to a session-specific subdirectory. Returns new relative path."""
        src = self.get_absolute_path(relative_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")

        dest_dir = self._upload_dir / session_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        src.rename(dest)
        return str(dest.relative_to(self._upload_dir.parent))
