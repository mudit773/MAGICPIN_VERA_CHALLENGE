# magicpin Vera Candidate Bot - Production Container
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and dataset
COPY . .

# Expose standard challenge port
EXPOSE 8080

# Healthcheck conforming to challenge-testing-brief.md §2.4
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/v1/healthz || exit 1

# Launch production server
CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8080"]
