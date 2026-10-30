# Service image (item 13). Build args let the base-image experiment reuse this
# file: default python:3.11-slim, measured against full python:3.11.
ARG BASE=python:3.11-slim
FROM ${BASE}

WORKDIR /app

# CPU-only PyTorch: the extra index serves wheels without CUDA libraries.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt \
        --extra-index-url https://download.pytorch.org/whl/cpu

# Bake the encoder weights so the container starts without network access.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY src/ src/
# build_resources reads the product catalogue; the demo page reads the label
# export. The eval files (query.csv, label.csv) are excluded by .dockerignore.
COPY data/WANDS/dataset/product.csv data/WANDS/dataset/product.csv
COPY data/demo_labels.json data/demo_labels.json

EXPOSE 8000
CMD ["uvicorn", "api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
