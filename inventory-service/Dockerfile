FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY init.sql ./init.sql

EXPOSE 50051
EXPOSE 8080

CMD ["python", "-m", "src.main"]
