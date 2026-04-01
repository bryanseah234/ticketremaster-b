FROM python:3.12-slim

WORKDIR /app

COPY services/user-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/user-service/ .
COPY shared/ /shared/

EXPOSE 5000

CMD ["sh", "-c", "flask db upgrade && gunicorn -w 4 -b 0.0.0.0:5000 app:app"]
