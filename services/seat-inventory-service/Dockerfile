FROM python:3.12-slim

WORKDIR /app

COPY services/seat-inventory-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/seat-inventory-service/ .
COPY shared/ /shared/

EXPOSE 5000 50051

CMD ["sh", "-c", "flask db upgrade && python server.py"]
