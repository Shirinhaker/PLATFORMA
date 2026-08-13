FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN python -m pip install .

USER 10001
CMD ["sh", "-c", "if [ \"${KOPRIK_TELEGRAM_CUTOVER_ONCE:-0}\" = \"1\" ]; then python -m app.auth.telegram_cutover_once; fi && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
