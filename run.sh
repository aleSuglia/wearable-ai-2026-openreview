#!/bin/zsh

# Load OPENREVIEW_EMAIL / OPENREVIEW_PASSWORD from .env if present.
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "$OPENREVIEW_EMAIL" ] || [ -z "$OPENREVIEW_PASSWORD" ]; then
  echo "Missing credentials: set OPENREVIEW_EMAIL and OPENREVIEW_PASSWORD (e.g. copy .env.example to .env and fill it in)." >&2
  exit 1
fi

venue_id=thecvf.com/ECCV/2026/Workshop/WearableAI
short_venue_name=WearableAI
uv run python src/wearableai_2026/accepted_metadata_downloader.py \
  --venue ${venue_id} \
  --output ${short_venue_name}-accepted_metadata.tsv
