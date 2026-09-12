#!/usr/bin/env bash
# One-command startup. Detects the Ollama endpoint, builds the sandbox
# image if missing, and brings the workbench up.
set -uo pipefail

echo "[1/4] locating the local Ollama inference node"
CANDIDATES=("${OLLAMA_BASE_URL:-}" "http://10.0.2.2:11434"
            "http://192.168.59.1:11434" "http://172.17.0.1:11434"
            "http://host.docker.internal:11434" "http://localhost:11434")
FOUND=""
for url in "${CANDIDATES[@]}"; do
    [ -z "$url" ] && continue
    if curl -fs --max-time 3 "$url/api/tags" >/dev/null 2>&1; then
        FOUND="$url"; echo "      found: $url"; break
    fi
done
if [ -z "$FOUND" ]; then
    echo "      ERROR: no Ollama endpoint reachable."
    echo "      Start Ollama with OLLAMA_HOST=0.0.0.0:11434, then re-run,"
    echo "      or set OLLAMA_BASE_URL=http://<host>:11434 explicitly."
    exit 1
fi

echo "[2/4] checking required models"
TAGS=$(curl -fs "$FOUND/api/tags")
for m in qwen3.5:0.8b qwen3.5:2b-q4_K_M qwen2.5-coder:3b gemma3:4b nomic-embed-text; do
    if echo "$TAGS" | grep -q "\"$m"; then
        echo "      ok      $m"
    else
        echo "      MISSING $m   -> ollama pull $m"
    fi
done

echo "[3/4] sandbox image"
if docker image inspect sovereign-sandbox:latest >/dev/null 2>&1; then
    echo "      already built"
else
    docker build -t sovereign-sandbox:latest sandbox/ && echo "      built"
fi

echo "[4/4] starting the workbench"
OLLAMA_BASE_URL="$FOUND" docker compose up -d --build
sleep 12
curl -fs localhost:8080/api/health | python3 -c "
import json,sys
d = json.load(sys.stdin)
print()
print('  status    :', d['status'])
print('  inference :', d['inference_endpoint'], '| reachable:', d['inference_reachable'])
print('  sandbox   :', d['sandbox_available'])
print('  tools     :', len(d['tools']))
missing = [m['name'] for m in d['models'] if not m['present']]
print('  models    :', 'all present' if not missing else f'MISSING {missing}')
print()
print('  Open http://localhost:8080  (or http://<vm-ip>:8080 from the host)')
" 2>/dev/null || echo "  API not responding yet; check: docker compose logs"
