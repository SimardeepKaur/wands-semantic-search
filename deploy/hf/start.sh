#!/bin/bash
# Space startup: Elasticsearch, Redis, index build, then the API on 7860.
# The Space has no persistent disk, so every start indexes the baked vectors.
set -e
echo "start.sh: $(date -u +%H:%M:%S) starting Elasticsearch"
ES_JAVA_OPTS="-Xms2g -Xmx2g" /opt/elasticsearch/bin/elasticsearch -d -p /tmp/es.pid

for i in $(seq 1 60); do
  curl -s "http://localhost:9200/_cluster/health" | grep -q '"status":"\(green\|yellow\)"' && break
  sleep 2
done
curl -s "http://localhost:9200/_cluster/health" | grep -q '"status"' || { echo "Elasticsearch did not start"; exit 1; }
echo "start.sh: $(date -u +%H:%M:%S) Elasticsearch up"

redis-server --daemonize yes --maxmemory 64mb --maxmemory-policy allkeys-lru

echo "start.sh: $(date -u +%H:%M:%S) building the index from baked vectors"
PYTHONPATH=src python src/rebuild_index.py --model minilm
echo "start.sh: $(date -u +%H:%M:%S) index ready, starting the API"

exec uvicorn api:app --app-dir src --host 0.0.0.0 --port 7860
