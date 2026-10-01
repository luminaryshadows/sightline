"""
Local testing UI server for Private Sight.

A zero-dependency HTTP server (Python stdlib only) that provides a browser UI
for the document analysis pipeline. Fully offline:

- No CDN assets (all CSS/JS served locally)
- No external fonts
- No analytics
- Binds to 127.0.0.1 only

Usage:
    python -m app.server
    python -m app.server --port 8765
    python -m app.server --tts          # enable spoken announcements

API:
    GET  /                  → UI
    GET  /static/<file>     → static assets
    GET  /api/status        → privacy + developer status
    POST /api/scan          → {image_base64, filename} → analysis
    POST /api/ask           → {document_id, question} → answer
    POST /api/speak         → {text} → speak via local TTS
    POST /api/delete        → {document_id} → delete one document
    POST /api/delete-all    → wipe the session
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Ensure project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.pipeline import DocumentPipeline, create_pipeline  # noqa: E402
from ml.storage import DocumentStore  # noqa: E402
from ml.tts import LocalTTS  # noqa: E402

STATIC_DIR = Path(__file__).parent / "static"
DEMO_DIR = Path(__file__).parent.parent / "demo_documents"

# Global pipeline state (single-process, local-only)
_pipeline: DocumentPipeline | None = None
_store: DocumentStore | None = None
_tts: LocalTTS | None = None
_lock = threading.Lock()

# Developer/privacy counters
_stats = {
    "network_requests": 0,   # incremented if we ever attempted one (we don't)
    "documents_processed": 0,
    "processing_location": "device",
    "model_source": "local",
    "privacy_status": "protected",
}


def get_pipeline() -> DocumentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = create_pipeline()
    return _pipeline


def get_store() -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore(persist_images=False)  # in-memory only
    return _store


def get_tts() -> LocalTTS:
    global _tts
    if _tts is None:
        _tts = LocalTTS()
    return _tts


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "PrivateSight/0.1"

    # ── helpers ────────────────────────────────────────────────

    def _send_json(self, payload: dict[str, Any], status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    # ── routing ────────────────────────────────────────────────

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            return self._serve_static("index.html")
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        if path == "/api/status":
            return self._handle_status()
        if path == "/favicon.ico":
            return self._send_bytes(b"", "image/x-icon", 204)

        return self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/scan":
            return self._handle_scan()
        if path == "/api/ask":
            return self._handle_ask()
        if path == "/api/speak":
            return self._handle_speak()
        if path == "/api/delete":
            return self._handle_delete()
        if path == "/api/delete-all":
            return self._handle_delete_all()

        return self._send_json({"error": "not found", "path": path}, 404)

    # ── static ─────────────────────────────────────────────────

    def _serve_static(self, rel_path: str):
        # Prevent path traversal
        rel_path = rel_path.lstrip("/")

        # Serve demo documents from demo_documents/ without duplicating them
        if rel_path.startswith("demo/"):
            demo_name = rel_path[len("demo/"):]
            target = (DEMO_DIR / demo_name).resolve()
            try:
                target.relative_to(DEMO_DIR.resolve())
            except ValueError:
                return self._send_json({"error": "forbidden"}, 403)
            if not target.is_file():
                return self._send_json({"error": "not found", "file": demo_name}, 404)
            return self._send_bytes(target.read_bytes(), "image/png")

        target = (STATIC_DIR / rel_path).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            return self._send_json({"error": "forbidden"}, 403)

        if not target.is_file():
            return self._send_json({"error": "not found", "file": rel_path}, 404)

        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        return self._send_bytes(target.read_bytes(), ctype)

    # ── API handlers ───────────────────────────────────────────

    def _handle_status(self):
        return self._send_json({
            "privacy": {
                "network_requests": _stats["network_requests"],
                "processing_location": _stats["processing_location"],
                "model_source": _stats["model_source"],
                "privacy_status": _stats["privacy_status"],
                "documents_processed": _stats["documents_processed"],
                "documents_in_session": get_store().count,
            },
            "tts_available": get_tts().available,
            "tts_engine": get_tts().engine,
        })

    def _handle_scan(self):
        payload = self._read_json()
        image_b64 = payload.get("image_base64", "")
        filename = payload.get("filename", "upload.png")

        if not image_b64:
            return self._send_json({"error": "missing image_base64"}, 400)

        # Strip data URL prefix if present
        if "," in image_b64 and image_b64.strip().startswith("data:"):
            image_b64 = image_b64.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:  # noqa: BLE001
            return self._send_json({"error": "invalid base64 image"}, 400)

        if len(image_bytes) > 25 * 1024 * 1024:
            return self._send_json({"error": "image too large (max 25MB)"}, 413)

        # Write to a temp file ONLY for the duration of analysis, then remove it.
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            with _lock:
                analysis = get_pipeline().analyze(tmp_path)
                result = analysis.to_dict()
                _stats["documents_processed"] += 1

            document_id = get_store().add(
                image_bytes=None,  # do not persist
                analysis=result,
                original_filename=filename,
            )
            result["document_id"] = document_id
            return self._send_json({"ok": True, "document_id": document_id, "analysis": result})
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            return self._send_json({"error": f"analysis failed: {e}"}, 500)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _handle_ask(self):
        payload = self._read_json()
        document_id = payload.get("document_id", "")
        question = payload.get("question", "").strip()

        if not question:
            return self._send_json({"error": "missing question"}, 400)

        doc = get_store().get(document_id)
        if doc is None or doc.analysis is None:
            return self._send_json({"error": "document not found"}, 404)

        text = doc.analysis.get("ocr", {}).get("full_text", "")

        # Reconstruct minimal objects for the QA engine
        from ml.classifier.engine import DocumentType
        from ml.extraction.extractor import ExtractedField, ExtractionResult

        doc_type_value = doc.analysis.get("document_type", "unknown")
        try:
            doc_type = DocumentType(doc_type_value)
        except ValueError:
            doc_type = DocumentType.UNKNOWN

        extraction = _rebuild_extraction(doc.analysis.get("extraction", {}), doc_type)

        answer = get_pipeline().qa_engine.answer(question, text, extraction, doc_type)
        return self._send_json({
            "ok": True,
            "question": answer.question,
            "answer": answer.answer,
            "confidence": answer.confidence,
            "is_medical": answer.is_medical,
            "medical_disclaimer": answer.medical_disclaimer,
        })

    def _handle_speak(self):
        payload = self._read_json()
        text = payload.get("text", "").strip()
        if not text:
            return self._send_json({"error": "missing text"}, 400)
        result = get_tts().speak(text)
        return self._send_json({
            "ok": result.spoken,
            "engine": result.engine,
            "error": result.error,
            "text": result.text,
        })

    def _handle_delete(self):
        payload = self._read_json()
        document_id = payload.get("document_id", "")
        report = get_store().delete(document_id)
        return self._send_json({"ok": True, "report": report})

    def _handle_delete_all(self):
        report = get_store().delete_all()
        return self._send_json({"ok": True, "report": report})

    # ── logging ────────────────────────────────────────────────

    def log_message(self, fmt, *args):  # noqa: A003
        # Minimal, local-only logging
        sys.stderr.write(f"[private-sight] {self.address_string()} {fmt % args}\n")


def _rebuild_extraction(data: dict, doc_type) -> Any:
    """Rebuild an ExtractionResult-compatible object from serialized data."""
    from ml.extraction.extractor import ExtractionResult, ExtractedField

    fields = [ExtractedField(label=f["label"], value=f["value"]) for f in data.get("fields", [])]
    monetary_values = [(m["description"], m["amount"]) for m in data.get("monetary_values", [])]
    deadlines = [(d["description"], d["date"]) for d in data.get("deadlines", [])]
    contacts = [(c["type"], c["value"]) for c in data.get("contacts", [])]

    return ExtractionResult(
        document_type=doc_type,
        fields=fields,
        action_required=data.get("action_required", ""),
        deadlines=deadlines,
        monetary_values=monetary_values,
        contacts=contacts,
        summary_lines=data.get("summary", []),
        medical_disclaimer=data.get("medical_disclaimer", ""),
    )


def main():
    parser = argparse.ArgumentParser(description="Private Sight local testing UI")
    parser.add_argument("--port", type=int, default=8765, help="Port (default 8765)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Private Sight — Local Testing UI")
    print("=" * 60)
    print()
    print(f"  Open:  http://{args.host}:{args.port}")
    print("  Bind:  loopback only (not reachable from the network)")
    print("  Data:  in-memory only; nothing written or uploaded")
    print()
    print("  ⏳ Warming up the pipeline (first load may take a few seconds)...")

    try:
        get_pipeline()
        print("  ✅ Pipeline ready.")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ Pipeline warmup failed: {e}")
        print("    (The server will still start; scans may fail.)")

    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()
        if _store is not None:
            _store.cleanup()
        print("All session data deleted. Goodbye.")


if __name__ == "__main__":
    main()
