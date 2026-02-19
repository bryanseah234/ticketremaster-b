FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Set Python path to make 'src' importable
ENV PYTHONPATH=/app

CMD ["python", "src/app.py"]
