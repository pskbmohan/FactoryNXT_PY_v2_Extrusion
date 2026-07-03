FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Expose Flask default port + device-facing HTTP port (port 80 for Wattmon devices)
EXPOSE 5555 80

# Use sh to invoke entrypoint to avoid executable bit issues
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
