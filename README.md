# Immutable Log-Sink for SOC 2 / ISO 27001

This sub-package turns Fly.io into a **write-once, read-many (WORM)** audit-log
endpoint that costs pennies per tenant yet satisfies SOC 2, ISO 27001 or PCI
requirements for *tamper-evident, immutable* logs.

Highlights
----------
• **Immediate immutability** – every event is streamed straight into an
  S3-compatible bucket created with *Object Lock / Governance mode*.
• **Daily attestation** – a scheduled Fly Machine computes a SHA-256 digest of
  the previous day’s objects and uploads the digest file back to the bucket so
  auditors can verify data integrity.
• **Per-tenant isolation** – one Fly app (two tiny Machines) per customer keeps
  compliance scope simple and lets you pass through storage costs.
• **Scale-to-zero** – the ingest Machine auto-sleeps when idle and wakes on the
  next HTTPS request; attestation Machine only boots once per day.

Directory layout
----------------

```
logsink/
├── app/                   # container source
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py          # /ingest endpoint (FastAPI)
│   └── attest_job.py      # daily SHA-256 root generator
├── modules/
│   └── fly-logsink/       # Terraform module – Fly app + Machines
└── docs/
    └── log-sink-quick-start.md  # copy-paste deployment guide
```

HTTP API
--------

`POST  /ingest`  (Content-Type: `application/json`)

Accepted payloads:

* `{ "logs": [ {…}, {…} ] }`  – preferred
* a **single** JSON object  – will be wrapped into a list internally
* a raw JSON array           – `[ {…}, {…} ]`

Each entry is serialised and uploaded as an individual object at

```
logs/YYYY/MM/DD/HHMMSS-<uuid>.json
```

The response returns the list of S3 keys:

```json
{ "stored": 2, "keys": ["logs/2024/05/02/153301-abc.json", …] }
```

Daily attestation files are written under `attestations/YYYY-MM-DD.txt` and look
like:

```
sha256:<hex-digest>
count:<object-count>
timestamp:2024-05-02T01:00:05Z
```

Environment variables (server & job)
------------------------------------

| Var                  | Purpose                                                |
|----------------------|--------------------------------------------------------|
| `S3_BUCKET`          | Bucket **with Object Lock enabled**                    |
| `S3_ENDPOINT`        | Optional – Wasabi / MinIO endpoint                     |
| `S3_REGION`          | Region name (default `us-east-1`)                      |
| `AWS_ACCESS_KEY_ID`  | IAM / access key                                       |
| `AWS_SECRET_ACCESS_KEY` | Secret key                                          |
| `OBJECT_LOCK_DAYS`   | Retention period (default **365**)                     |
| `LOG_PREFIX`         | Key prefix (`logs` by default)                         |
| `ATTEST_BUCKET`      | Optional bucket for attestation files                  |


Deploying
---------

* Build & push image from `logsink/app`.
* Use the Terraform module under `modules/fly-logsink` – variables mirror the
  env-vars above plus Fly app details.  A full copy-paste walkthrough lives in
  `docs/log-sink-quick-start.md`.


Road-map ideas
--------------
* Push Merkle roots to a public blockchain for *C-level bragging rights*.
* Add OpenTelemetry-HTTP compatibility (`Content-Encoding: gzip`, protobuf).  
* SSE / WebSocket tailing UI guarded by presigned URLs.

Enjoy shipping! 🚀
