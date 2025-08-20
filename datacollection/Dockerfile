# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Copier et installer les d�pendances
COPY requirements.txt azure_blob_setup.py download_blob.py ./
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du projet
COPY . .

# Par d�faut, lance le scraper JSON + images
ENTRYPOINT ["python", "download_blob.py"]
