FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed to build mysqlclient
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    netcat-openbsd \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

EXPOSE 5000

COPY wait-for-db.sh /wait-for-db.sh
CMD ["sh", "/wait-for-db.sh"]



