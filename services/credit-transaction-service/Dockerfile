FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["sh", "-c", "until flask db upgrade; do echo 'Migration failed, retrying...'; sleep 2; done && gunicorn -w 4 -b 0.0.0.0:5000 app:app"]