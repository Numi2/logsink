FROM python:3.12-slim

# Install system deps for boto3 (none needed really) but keep layer caching.
WORKDIR /app

# Install Python requirements first.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source.
COPY . .

# Default command launches the HTTP ingest server.  The same image is reused
# by the daily attestation cron job with CMD overridden to `python attest_job.py`.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
