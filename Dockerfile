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

CMD ["gunicorn", "waste_classification.wsgi:application", "--bind", "0.0.0.0:8080", "--timeout", "120"]