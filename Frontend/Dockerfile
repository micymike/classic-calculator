FROM python:3.12-slim

WORKDIR /app

COPY Frontend/requirements.txt requirements.txt 

RUN ls -la

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port
# EXPOSE 8501

# Command to run the application
CMD streamlit run front.py --server.port $PORT --server.address 0.0.0.0
