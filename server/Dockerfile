FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sarabhel ./sarabhel
COPY zones ./zones

# Usuario sin privilegios; el grupo dialout permite abrir el puerto serie del gateway.
RUN useradd --create-home --groups dialout app \
    && mkdir -p /data && chown app:app /data
USER app

# Cada servicio define su comando en docker-compose.yml
CMD ["python", "-m", "sarabhel.dashboard"]
