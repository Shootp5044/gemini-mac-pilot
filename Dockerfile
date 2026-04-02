FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

# Copy application code
COPY mac_pilot/ mac_pilot/
COPY cloud_api.py .

EXPOSE 8080

CMD ["python", "cloud_api.py"]
