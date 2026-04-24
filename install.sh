#!/bin/bash

set -e

# Backend selection: --cpu, --cuda, or auto-detect via nvidia-smi.
# Controls which torch wheel index is used (and whether cupy is installed
# for GPU-accelerated spacy preprocessing).
BACKEND=""
for arg in "$@"; do
    case "$arg" in
        --cpu)  BACKEND="cpu" ;;
        --cuda) BACKEND="cuda" ;;
        -h|--help)
            echo "Usage: $0 [--cpu | --cuda]"
            echo "  --cpu   Install CPU-only torch; skip cupy."
            echo "  --cuda  Install CUDA 12.4 torch + cupy-cuda12x for GPU spacy."
            echo "  (default) Auto-detect: use --cuda if nvidia-smi is on PATH, else --cpu."
            exit 0 ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: $0 [--cpu | --cuda]" >&2
            exit 1 ;;
    esac
done
if [ -z "$BACKEND" ]; then
    if command -v nvidia-smi >/dev/null 2>&1; then
        BACKEND="cuda"
        echo "nvidia-smi detected — installing CUDA backend. Pass --cpu to override."
    else
        BACKEND="cpu"
        echo "No nvidia-smi detected — installing CPU backend. Pass --cuda to override."
    fi
fi

# Ensure uv is installed — https://docs.astral.sh/uv/getting-started/installation/
# uv is only needed during this install script; the runtime wrappers activate
# the venv directly, so they don't need uv on PATH.
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found — installing via the official installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer drops uv at ~/.local/bin/uv but does not touch the
    # current shell's PATH, so add it explicitly for the rest of this script.
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv installation failed. See https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

# Give current user permission to write to /var/lib/topologic
sudo mkdir -p /var/lib/topologic
sudo chown -R $USER:$USER /var/lib/topologic

# Install a uv-managed Python 3.12
uv python install 3.12

# Copy the Python project (pyproject.toml + uv.lock + topologic package) into place,
# then sync the venv from the lockfile. The venv lives at /var/lib/topologic/topologic_env
# (visible top-level path rather than a hidden `.venv` inside the project).
rm -rf /var/lib/topologic/lib
cp -R lib /var/lib/topologic/lib
( cd /var/lib/topologic/lib && UV_PROJECT_ENVIRONMENT=/var/lib/topologic/topologic_env uv sync --frozen --extra "$BACKEND" )

# The labeler lives in its own package + venv because it needs a newer
# `transformers` than spacy-transformers allows in the main env. The main
# topologic pipeline shells out to `topologic-labeler` on demand.
rm -rf /var/lib/topologic/labeler
cp -R labeler /var/lib/topologic/labeler
( cd /var/lib/topologic/labeler && UV_PROJECT_ENVIRONMENT=/var/lib/topologic/topologic_labeler_env uv sync --frozen --extra "$BACKEND" )
sudo ln -sf /var/lib/topologic/topologic_labeler_env/bin/topologic-labeler /usr/local/bin/topologic-labeler

# Install the topologic script
sudo cp topologic /usr/local/bin/
sudo chmod +x /usr/local/bin/topologic

echo -e "\nMoving web application components into place..."

if [ ! -f /etc/topologic/global_settings.ini ]
    then
        sudo mkdir -p /etc/topologic/
        sudo cp config/global_settings.ini /etc/topologic/
        echo "Storage is DuckDB — no database server setup required. Each trained model gets its own model.duckdb file inside its webapp directory."
else
    echo "/etc/topologic/global_settings.ini already exists, not modifying..."
fi

sudo mkdir -p /var/lib/topologic/api_server/
sudo chown -R $USER:$USER /var/lib/topologic/api_server
cp api_server/web_server.sh /var/lib/topologic/api_server/
if [ ! -f /var/lib/topologic/api_server/gunicorn.conf.py ]
    then
        cp api_server/gunicorn.conf.py /var/lib/topologic/api_server/
else
    echo "/var/lib/topologic/api_server/gunicorn.conf.py already exists, not modifying..."
fi

cp -R api /var/lib/topologic/
rm -rf /var/lib/topologic/web-app
# Copy everything except node_modules and the pre-built dist; the dist is
# regenerated per-deployment by the topologic CLI (which writes appConfig.json
# and then runs `npm install && npm run build` in the target directory).
rsync -a --exclude node_modules --exclude dist web-app/ /var/lib/topologic/web-app/
rm -rf /var/lib/topologic/config
cp -Rf config /var/lib/topologic
echo -e "\n## IMPORTANT ##\nTopoLogic runs behind the Gunicorn web server. Make sure you configure the Gunicorn config file in /var/lib/topologic/api_server/gunicorn.conf.py. You should also make sure it autostarts on boot.\n"