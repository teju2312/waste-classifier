FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p media staticfiles logs

EXPOSE 8000

# Updated CMD line to disable multi-worker thread buffering and catch the trace raw
CMD python manage.py migrate --noinput && gunicorn waste_classification.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 1 --log-level debug