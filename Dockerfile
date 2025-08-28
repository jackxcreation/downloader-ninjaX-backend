FROM python:3.10-slim

# Install system dependencies (enhanced)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for cookies and temp files
RUN mkdir -p /app/cookies /app/temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMP_DIR=/app/temp

# Expose port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:10000/ || exit 1

# Run the application
CMD ["python", "app.py"]
