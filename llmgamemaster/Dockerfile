FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy configuration and utilities first
COPY config.py .
COPY utils.py .

# Copy core services 
COPY db_service.py .
COPY llm_service.py .
COPY element_manager.py .
COPY async_utils.py .

# Copy authentication modules (BEFORE app.py since app.py imports them)
COPY auth.py .
COPY auth_routes.py .

# Copy image and static file handling
COPY image_storage_service.py .
COPY static_files_middleware.py .

# Copy templates directory
COPY templates/ ./templates/

# Copy main application (LAST since it imports everything else)
COPY app.py .

# Copy optional scripts
COPY verify_config.py .
COPY migration_images.py .

# Create necessary directories
RUN mkdir -p /app/logs /app/static/images/characters /app/static/images/npcs /app/static/images/locations /app/static/images/campaigns

# Note: LLM provider and configuration are set via environment variables from docker-compose
# No configuration files created in the image for security and flexibility

# Expose API port
EXPOSE 5001

# Run the FastAPI application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001"] 