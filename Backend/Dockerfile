FROM python:3.12-slim

WORKDIR /app

COPY Backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/main.py .
COPY Backend/. .

# Expose port
# EXPOSE 8000

# Command to run the application
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
