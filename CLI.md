# CLI Reference

## Start the server

```bash
python server.py
python server.py --host 0.0.0.0 --port 8080
```

Default host: `0.0.0.0` — Default port: `8080`

---

## Run the pipeline (CLI)

```bash
python main.py --generate campaign_brief.json
python main.py --generate campaign_brief.json --provider flux
python main.py --generate campaign_brief.json --provider gpt-image-1
python main.py --generate campaign_brief.json --upload-azure
python main.py --generate az://briefs/campaign_brief.json
python main.py --parse "Summer campaign for Viva beverages and energy bars targeting health-conscious adults"

# Additional example briefs
python main.py --generate briefs/tech_brief.json
python main.py --generate briefs/lumina_brief.json
python main.py --generate briefs/maison_brief.json
python main.py --generate briefs/onyx_brief.json
```

| Flag | Required | Values | Description |
|---|---|---|---|
| `--generate` | Yes (unless `--setup` or `--parse`) | Path to `.json` file or `az://blob` | Campaign brief to process |
| `--provider` | No | `flux` / `gpt-image-1` | Overrides `IMAGE_PROVIDER` env var |
| `--upload-azure` | No | — | Upload generated outputs to Azure Blob Storage after run |
| `--parse` | No | Natural language string | Parse a description into a structured JSON brief |
| `--setup` | No | — | Interactive prompt to save API keys to `.env` |

---

## First-time setup

```bash
python main.py --setup
```

Prompts for `BFL_API_KEY`, `OPENAI_API_KEY`, and `IMAGE_PROVIDER`. Writes to `.env`.

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BFL_API_KEY` | Yes (if using Flux) | — | Black Forest Labs API key |
| `OPENAI_API_KEY` | Yes (if using GPT Image 1 or NL parse) | — | OpenAI API key |
| `IMAGE_PROVIDER` | No | `flux` | Active image generation provider |

Set in `.env` or export before running:

```bash
export BFL_API_KEY=sk-...
export OPENAI_API_KEY=sk-...
export IMAGE_PROVIDER=flux
```

---

## Streamlit UI

```bash
streamlit run app.py
```

Opens at `http://localhost:8501` by default.

---

## Output locations

| Path | Contents |
|---|---|
| `outputs/{product_id}/1x1.png` | Instagram Feed (1080×1080) |
| `outputs/{product_id}/9x16.png` | Stories / Reels (1080×1920) |
| `outputs/{product_id}/16x9.png` | Facebook / YouTube (1920×1080) |
| `outputs/report.html` | Self-contained HTML report with all creatives |
| `campaign_run.log` | Full structured run log |
| `campaigns/{id}_{ts}/` | Persisted brief and run summary |
