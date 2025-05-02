"""HTTP log-ingest endpoint that stores each received log blob as an S3 object
with Object Lock (WORM).  Intended to run on Fly.io as a lightweight, always-on
service (can still scale-to-zero thanks to Fly Machines' autostart/stop).

Request format:
POST /ingest  Content-Type: application/json  Body: {"logs": [...]} or single obj

Each log is uploaded immediately to reduce data-at-rest in the ingest machine
and guarantee immutability.  The S3 bucket **must** be created with
`--object-lock-enabled-for-bucket` and versioning before you run this.

Environment variables required:

S3_ENDPOINT        – optional (for Wasabi, MinIO, etc.)
S3_REGION          – e.g., "eu-central-1"
S3_BUCKET          – name of bucket with Object Lock enabled
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY

OBJECT_LOCK_DAYS   – integer retention period; default 365
LOG_PREFIX         – key prefix, default "logs"
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import boto3
from botocore.config import Config
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()

# -----------------------------------------------------------------------------
# S3 client setup
# -----------------------------------------------------------------------------


def new_s3_client():
    cfg = Config(s3={"addressing_style": "virtual"})
    endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("S3_REGION", "us-east-1")

    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        config=cfg,
    )


s3 = new_s3_client()
bucket = os.getenv("S3_BUCKET")
if not bucket:
    raise RuntimeError("S3_BUCKET env var is required")

retention_days = int(os.getenv("OBJECT_LOCK_DAYS", "365"))
lock_until = (datetime.now(timezone.utc) + timedelta(days=retention_days)).replace(
    tzinfo=timezone.utc
)

key_prefix = os.getenv("LOG_PREFIX", "logs")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def put_log_object(content: bytes) -> str:
    """Write `content` to S3 under a UUID key with Object Lock."""

    log_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    key = f"{key_prefix}/{ts}-{log_id}.json"

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType="application/json",
        ObjectLockMode="GOVERNANCE",
        ObjectLockRetainUntilDate=lock_until,
    )

    return key


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.post("/ingest")
async def ingest(request: Request):
    try:
        payload: Any = await request.json()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    logs: List[Dict[str, Any]]
    if isinstance(payload, dict) and "logs" in payload:
        logs = payload["logs"] if isinstance(payload["logs"], list) else [payload["logs"]]
    elif isinstance(payload, list):
        logs = payload
    else:
        logs = [payload]

    keys = []
    for entry in logs:
        content = ("{}\n".format(entry)).encode()
        key = put_log_object(content)
        keys.append(key)

    return {"stored": len(keys), "keys": keys}


# Health-check route


@app.get("/")
async def root():
    return {"status": "ok"}
