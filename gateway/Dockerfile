# 🌊 Pacific Gateway — Stateless Microsoft Store License Proxy
# Zero database. Zero accounts. Validates Windows Store tokens with Microsoft.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py key_manager.py ./

EXPOSE 8080

# Run with env vars: see .env.example for required configuration
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
