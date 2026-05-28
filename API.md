# API Reference

Base URL: `http://localhost:8080`

---

## Static routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the web UI (`static/index.html`) |
| `GET` | `/outputs/{product}/{file}` | Serves a generated output image |
| `GET` | `/report` | Serves the latest HTML report |

---

## Campaigns

### List campaigns
```
GET /api/campaigns
```
Returns the 25 most recent campaigns.

**Response**
```json
[
  {
    "id": 1,
    "campaign_id": "viva_summer",
    "created_at": "2026-05-24T10:00:00",
    "provider": "flux",
    "summary_json": { "generated": 2, "cost_estimate": 0.10 }
  }
]
```

---

### Get campaign
```
GET /api/campaigns/{id}
```

**Response**
```json
{
  "id": 1,
  "campaign_id": "viva_summer",
  "brief_json": { ... },
  "summary_json": { ... },
  "output_paths_json": { "viva_sparkling_water": ["outputs/..."] }
}
```

---

## Brief

### Parse natural language brief
```
POST /api/brief/parse
Content-Type: application/json

{ "text": "Summer campaign for Viva beverages and energy bars targeting health-conscious adults..." }
```

**Response** — validated brief JSON object

**Errors**
| Code | Meaning |
|---|---|
| `400` | `text` field missing |
| `422` | OpenAI key not configured |
| `500` | Parse or validation failure |

---

### Get example brief
```
GET /api/brief/example
```
Returns the contents of `campaign_brief.json` if it exists.

---

## API Keys

### Save keys
```
POST /api/keys
Content-Type: application/json

{
  "bfl_api_key": "sk-...",
  "openai_api_key": "sk-..."
}
```
Writes keys to `.env` and updates the running process environment. Both fields are optional — omit to leave unchanged.

**Response:** `{ "saved": true }`

---

### Check key status
```
GET /api/keys/status
```

**Response**
```json
{ "bfl": true, "openai": false }
```

---

## Pipeline

### Run pipeline (SSE)
```
POST /api/run
Content-Type: application/json

{
  "brief": { ... },
  "provider": "flux",
  "nl_parse_used": false
}
```

Returns a `text/event-stream` (Server-Sent Events). Each event is a JSON object on a `data:` line.

**Event types**

| Type | Payload | When |
|---|---|---|
| `pipeline_plan` | `{ "products": ["id1", "id2"] }` | First event — before any processing |
| `progress` | `{ "stage": "GENERATE", "message": "..." }` | Each pipeline stage update |
| `prompt` | `{ "product_id": "...", "prompt": "..." }` | Image generation prompt for each product |
| `images_ready` | `{ "product_id": "..." }` | Images saved to disk for a product |
| `complete` | `{ "result": { ... } }` | Pipeline finished successfully |
| `error` | `{ "message": "..." }` | Pipeline failed |

**Progress stages (in order)**

`INIT` → `BRIEF` → `LEGAL` → `PRODUCT` → `RESOLVE` → `GENERATE` → `RENDER` → `SAVE` → `COMPLIANCE` → `SUMMARY` → `REPORT`

---

## Downloads

### Download all outputs as ZIP
```
POST /api/download-zip
Content-Type: application/json

{
  "paths": ["viva_sparkling_water/1x1.png", "viva_sparkling_water/9x16.png"],
  "campaign_id": "viva_summer"
}
```

Returns `application/zip` with `Content-Disposition: attachment; filename={campaign_id}.zip`
