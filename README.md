# WearableAI 2026

Downloads accepted-paper metadata (titles, abstracts, authors, affiliations, contact emails)
from OpenReview for the WearableAI ECCV 2026 workshop, and writes it out as a TSV file.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python version and dependencies for you)
- An OpenReview account with access to the venue

## Setup

1. Install dependencies:

   ```sh
   uv sync
   ```

2. Copy the env template and fill in your OpenReview credentials:

   ```sh
   cp .env.example .env
   ```

   Then edit `.env`:

   ```
   OPENREVIEW_EMAIL=you@example.com
   OPENREVIEW_PASSWORD=your-openreview-password
   ```

   `.env` is gitignored and read automatically by `run.sh` — your credentials never need to
   be typed on the command line or committed to the repo.

## Usage

```sh
./run.sh
```

This downloads accepted submissions for `thecvf.com/ECCV/2026/Workshop/WearableAI` and writes
`WearableAI-accepted_metadata.tsv`.

To target a different venue or customize behavior, run the script directly:

```sh
uv run python src/wearableai_2026/accepted_metadata_downloader.py \
  --venue thecvf.com/ECCV/2026/Workshop/<name> \
  --output <name>-accepted_metadata.tsv
```

Credentials are still picked up from `OPENREVIEW_EMAIL`/`OPENREVIEW_PASSWORD` (or `.env`), or
can be overridden with `--email`/`--password`.

Other options:

| Flag | Default | Description |
| --- | --- | --- |
| `--abstract` | `abstract` | Abstract field key in the submission form (JSON) |
| `--use_meta_review` | off | Use meta-review notes to find accepted papers, instead of decision notes |
| `--recommendation` | `recommendation` | Recommendation field key in the meta-review form (only used with `--use_meta_review`) |
| `--decision` | `decision` | Decision field key in the decision form (ignored with `--use_meta_review`) |
