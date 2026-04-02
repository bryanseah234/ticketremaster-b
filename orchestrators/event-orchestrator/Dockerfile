FROM python:3.12-slim

WORKDIR /app

COPY orchestrators/event-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrators/event-orchestrator/ .
COPY shared/ /shared/

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]