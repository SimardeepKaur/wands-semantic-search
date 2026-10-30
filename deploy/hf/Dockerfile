# The public demo image (item 17): Elasticsearch, Redis and the API in ONE
# container, because a Hugging Face Space runs exactly one. Built from the
# Space repo layout that deploy/hf/assemble.sh produces.
#
# Space constraints handled here: port 7860, everything runs as uid 1000,
# node.store.allow_mmap false (a Space cannot change kernel settings), no
# persistent disk (the index is built from baked vectors at every start).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git redis-server \
    && rm -rf /var/lib/apt/lists/*

# Elasticsearch from the official tarball. arch switch keeps the same file
# buildable on an arm Mac for local testing; Spaces build on x86_64.
RUN arch=$(uname -m) && case "$arch" in \
        x86_64) esarch=x86_64 ;; \
        aarch64|arm64) esarch=aarch64 ;; \
        *) echo "unsupported arch $arch" && exit 1 ;; \
    esac && \
    curl -fsSL "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.15.3-linux-${esarch}.tar.gz" \
        | tar -xz -C /opt && \
    mv /opt/elasticsearch-8.15.3 /opt/elasticsearch

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt \
        --extra-index-url https://download.pytorch.org/whl/cpu

# The product catalogue (public WANDS repo) and the stored vectors (this
# project's data release). The demo label overlay is generated here and the
# eval csvs are removed: the serving image keeps no query or label data.
RUN git clone --depth 1 https://github.com/wayfair/WANDS.git /tmp/wands && \
    mkdir -p data/WANDS/dataset data/vectors && \
    cp /tmp/wands/dataset/*.csv data/WANDS/dataset/ && rm -rf /tmp/wands && \
    curl -fsSL -o data/vectors/products_minilm.npy \
        "https://github.com/SimardeepKaur/wands-semantic-search/releases/download/data-v1/products_minilm.npy" && \
    curl -fsSL -o data/vectors/product_ids_minilm.npy \
        "https://github.com/SimardeepKaur/wands-semantic-search/releases/download/data-v1/product_ids_minilm.npy"

COPY src/ src/
COPY eval/ eval/
# Generate the demo label overlay, then drop every eval csv: only the product
# catalogue stays in the serving image.
RUN python eval/export_demo_labels.py && \
    find data/WANDS/dataset -name '*.csv' ! -name 'product.csv' -delete

# Spaces run the container as uid 1000; Elasticsearch refuses root anyway.
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/es-data /home/user/es-logs && \
    printf '%s\n' \
        "discovery.type: single-node" \
        "xpack.security.enabled: false" \
        "node.store.allow_mmap: false" \
        "path.data: /home/user/es-data" \
        "path.logs: /home/user/es-logs" \
        "http.port: 9200" > /opt/elasticsearch/config/elasticsearch.yml && \
    chown -R user:user /opt/elasticsearch /home/user /app
USER user
ENV HOME=/home/user

# Bake the encoder weights into the user's cache: a sleeping Space must wake
# without reaching the Hugging Face Hub.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user:user start.sh .
EXPOSE 7860
CMD ["bash", "start.sh"]
