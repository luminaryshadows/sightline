"""
Local document storage with privacy-first deletion semantics.

Documents are held in memory by default. Optional temporary files are
written to a session directory that can be fully wiped.

Nothing is ever written outside the local session directory, and nothing
is persisted unless explicitly requested.

Used by both the local testing UI and the Android app's storage layer.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StoredDocument:
    """A document held in the local session."""
    document_id: str
    created_at: float
    image_path: Optional[str] = None      # Path to temp image file, if persisted
    analysis: Optional[dict[str, Any]] = None  # Serialized analysis result
    original_filename: str = ""

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class DocumentStore:
    """
    In-memory document store with explicit deletion.

    Guarantees:
    - Documents live only in this process (plus an optional temp dir)
    - delete() removes image files, analysis data, and any temp artifacts
    - delete_all() wipes the entire session
    - No document is written to a durable, user-visible location

    Privacy: this class never performs network I/O.
    """

    def __init__(self, temp_dir: Optional[str] = None, persist_images: bool = False):
        """
        Args:
            temp_dir: Directory for temporary image files. Defaults to a
                      system temp dir scoped to this process.
            persist_images: If False (default), images are never written to
                            disk at all — they are processed from memory.
        """
        self.persist_images = persist_images
        self._documents: dict[str, StoredDocument] = {}
        self._counter = 0
        self._session_dir: Optional[str] = None

        if persist_images:
            self._session_dir = temp_dir or tempfile.mkdtemp(prefix="private-sight-")
            os.makedirs(self._session_dir, exist_ok=True)

    def add(
        self,
        image_bytes: Optional[bytes] = None,
        analysis: Optional[dict[str, Any]] = None,
        original_filename: str = "",
    ) -> str:
        """
        Store a document. Returns the document_id.

        If persist_images is True and image_bytes are provided, the image is
        written to the session temp directory.
        """
        self._counter += 1
        document_id = f"doc-{int(time.time())}-{self._counter}"

        image_path = None
        if self.persist_images and image_bytes is not None and self._session_dir:
            image_path = os.path.join(self._session_dir, f"{document_id}.img")
            with open(image_path, "wb") as f:
                f.write(image_bytes)

        self._documents[document_id] = StoredDocument(
            document_id=document_id,
            created_at=time.time(),
            image_path=image_path,
            analysis=analysis,
            original_filename=original_filename,
        )
        return document_id

    def get(self, document_id: str) -> Optional[StoredDocument]:
        """Retrieve a stored document by ID."""
        return self._documents.get(document_id)

    def get_image_path(self, document_id: str) -> Optional[str]:
        """Get the path to a stored image, if persisted."""
        doc = self._documents.get(document_id)
        if doc and doc.image_path and os.path.exists(doc.image_path):
            return doc.image_path
        return None

    def delete(self, document_id: str) -> dict[str, Any]:
        """
        Delete a single document and all its artifacts.

        Removes:
        - Captured image file
        - OCR text
        - Extracted information
        - Any temporary files

        Returns a report of what was deleted.
        """
        doc = self._documents.pop(document_id, None)
        report = {
            "document_id": document_id,
            "found": doc is not None,
            "image_deleted": False,
            "analysis_deleted": False,
        }

        if doc is None:
            return report

        if doc.image_path and os.path.exists(doc.image_path):
            try:
                os.remove(doc.image_path)
                report["image_deleted"] = True
            except OSError:
                pass

        if doc.analysis is not None:
            doc.analysis = None
            report["analysis_deleted"] = True

        return report

    def delete_all(self) -> dict[str, Any]:
        """
        Delete every document in the session and wipe temp storage.

        This is the 'DELETE CURRENT DOCUMENT' / factory-reset action.
        """
        count = len(self._documents)
        self._documents.clear()

        temp_wiped = False
        if self._session_dir and os.path.exists(self._session_dir):
            try:
                shutil.rmtree(self._session_dir)
                temp_wiped = True
            except OSError:
                pass
            # Recreate an empty session dir for continued use
            os.makedirs(self._session_dir, exist_ok=True)

        return {
            "deleted_count": count,
            "temp_files_wiped": temp_wiped,
        }

    def list_ids(self) -> list[str]:
        """List document IDs currently held."""
        return list(self._documents.keys())

    @property
    def count(self) -> int:
        return len(self._documents)

    def cleanup(self):
        """Release all resources. Call on shutdown."""
        self.delete_all()
        self._session_dir = None


def create_store(persist_images: bool = False) -> DocumentStore:
    """Factory function for creating a document store."""
    return DocumentStore(persist_images=persist_images)
