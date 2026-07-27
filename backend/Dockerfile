# Tally backend — one container, built from this directory as the context.
# On Render: root directory `backend`, runtime Docker. No queue, no worker: the
# ingestion pipeline runs in-process (see app/api/uploads.py::_run_ingestion).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# No system packages are needed. The previous image installed gcc,
# postgresql-client, tesseract-ocr, ghostscript and poppler-utils for
# psycopg2/OCR — none of which this app uses: the database is reached over
# PostgREST and OCR was never built. pdfplumber and pandas ship wheels.

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Render (and most PaaS) inject $PORT; fall back to 8000 for a local run.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
