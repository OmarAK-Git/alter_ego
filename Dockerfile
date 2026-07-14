FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY config/ config/
COPY core/ core/
COPY worker/ worker/
COPY batch/ batch/
COPY web/ web/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "web.api:app", "--host", "0.0.0.0", "--port", "8000"]
