"""Vercel serverless entrypoint.

Decodes the GCP service-account credentials from the base-64 env var,
writes them to /tmp, then mounts the FastAPI app at /api so Vercel can
route /api/* requests here while the inner routes stay prefix-free.
"""
import base64
import os

# Decode GCP credentials before any google-genai import happens.
_gcp_b64 = os.environ.get("GCP_SERVICE_ACCOUNT_B64", "")
if _gcp_b64:
    _creds_path = "/tmp/gcp_service_account.json"
    with open(_creds_path, "w") as _f:
        _f.write(base64.b64decode(_gcp_b64).decode("utf-8"))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _creds_path

from fastapi import FastAPI  # noqa: E402

from src.main import create_app  # noqa: E402

_inner = create_app()

# Mount the inner app at /api so that /api/cases → inner /cases, etc.
app = FastAPI()
app.mount("/api", _inner)
