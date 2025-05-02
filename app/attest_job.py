"""Daily attestation job – computes a SHA256 digest of the previous day's log
objects and uploads the digest file back to S3.  This gives you a tamper-evident
Merkle-style root without actually pushing to Ethereum (stub).

Environment variables (same as server.py) plus:

ATTEST_BUCKET    – optional; defaults to S3_BUCKET

The Fly Machine is expected to run this script via cron, e.g. "0 1 * * *"
so it processes *yesterday's* objects.
"""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timedelta, timezone

import boto3
from botocore.config import Config


def s3_client():
    endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("S3_REGION", "us-east-1")
    cfg = Config(s3={"addressing_style": "virtual"})
    return boto3.client("s3", endpoint_url=endpoint, region_name=region, config=cfg)


def list_objects(client, bucket: str, prefix: str):
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def compute_digest_for_keys(client, bucket: str, keys):
    hasher = hashlib.sha256()
    for key in sorted(keys):
        obj = client.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        hasher.update(hashlib.sha256(data).digest())
    return hasher.hexdigest()


def main():
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET env required")

    attest_bucket = os.getenv("ATTEST_BUCKET", bucket)

    client = s3_client()

    yesterday = date.today() - timedelta(days=1)
    prefix = f"logs/{yesterday.strftime('%Y/%m/%d')}"  # matches server.py layout

    keys = list(list_objects(client, bucket, prefix))
    if not keys:
        print("No logs found for", yesterday)
        return

    digest = compute_digest_for_keys(client, bucket, keys)

    attest_key = f"attestations/{yesterday.isoformat()}.txt"
    body = f"sha256:{digest}\ncount:{len(keys)}\ntimestamp:{datetime.now(timezone.utc).isoformat()}\n"

    client.put_object(
        Bucket=attest_bucket,
        Key=attest_key,
        Body=body.encode(),
        ContentType="text/plain",
        ObjectLockMode="GOVERNANCE",
        ObjectLockRetainUntilDate=(datetime.now(timezone.utc) + timedelta(days=365)),
    )

    print("Wrote attestation", attest_key)


if __name__ == "__main__":
    main()
