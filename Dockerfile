# Backend Dockerfile (python + FastAPI)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# system deps for psycopg2/build tools (only if needed)
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

# copy requirements first (caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# copy app
COPY . /app

# Create non-root user
RUN useradd -m mainto && chown -R mainto:mainto /app
USER mainto

EXPOSE 8000

# For local dev you can pass --reload in docker-compose; in production use gunicorn
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "4"]

