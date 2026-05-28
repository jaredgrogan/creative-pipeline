# Campaign Brief JSON Schema

The pipeline accepts a campaign brief as a JSON file passed via `--generate` flag (CLI)
or parsed from natural language via the web UI. Both paths produce and validate the
same schema described here.

---

## Full Schema

```json
{
  "campaign_id": "string",
  "region": "string",
  "language": "string",
  "target_audience": "string",
  "campaign_message": "string",
  "brand": {
    "name": "string",
    "logo_path": "string | null",
    "colors": ["string"]
  },
  "products": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "asset_path": "string | null"
    }
  ]
}
```

---

## Field Reference

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `campaign_id` | string | Yes | URL-safe slug, underscores only, no spaces. Derived from campaign name — no year appended. |
| `region` | string | Yes | Target market. Use standard codes: `US`, `EU`, `JP`, `BR`, etc. |
| `language` | string | Yes | ISO 639-1 code. `en` is the default. Drives text overlay and localization. |
| `target_audience` | string | Yes | Plain-language description of the target audience. Fed into image generation prompt. |
| `campaign_message` | string | Yes | The headline overlaid on every output creative. Keep under 10 words. |
| `brand` | object | Yes | See brand fields below. |
| `products` | array | Yes | Minimum 2 items. See product fields below. |

### Brand object

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Brand name. Used in image prompts and report header. |
| `logo_path` | string \| null | No | Relative path to a PNG logo file for brand compliance checking. Omit or set `null` to skip logo detection. |
| `colors` | array of strings | No | Hex color codes, e.g. `["#2ECC71", "#FFFFFF"]`. Used for brand color compliance check. Empty array disables color check. |

### Product object (one entry per product)

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | URL-safe slug, underscores only. Used as the output folder name: `outputs/{id}/`. |
| `name` | string | Yes | Human-readable product name. Used in report and log output. |
| `description` | string | Yes | Rich visual description for AI image generation. Include product appearance, setting, lighting, and mood. More detail produces better images. |
| `asset_path` | string \| null | No | Relative path to an existing product image. If the file exists it is reused and generation is skipped. Set `null` to always generate. |

---

## Validation Rules

Enforced by `brief_parser.py` at load time — failures abort before any API call is made.

| Rule | Error |
|---|---|
| All 7 top-level fields must be present and non-null | `Brief is missing required field: '{field}'` |
| `brand` must be an object with a non-empty `name` | `Brief brand is missing required field: 'name'` |
| `products` must be an array | `'products' must be a list` |
| `products` must contain at least 2 items | `Brief must contain at least 2 products, found: {n}` |
| Each product must have `id`, `name`, and `description` | `products[{i}] is missing required field: '{field}'` |

### Optional field defaults (applied silently)

| Field | Default |
|---|---|
| `language` | `"en"` |
| `brand.colors` | `[]` |
| `brand.logo_path` | `null` |
| `product.asset_path` | `null` |

---

## Example

```json
{
  "campaign_id": "summer_launch",
  "region": "US",
  "language": "en",
  "target_audience": "health-conscious adults 25-40",
  "campaign_message": "Feel the Difference This Summer",
  "brand": {
    "name": "Viva",
    "logo_path": "assets/viva_logo.png",
    "colors": ["#2ECC71", "#FFFFFF", "#1A1A2E"]
  },
  "products": [
    {
      "id": "viva_sparkling_water",
      "name": "Viva Sparkling Water",
      "description": "Premium sparkling water in a sleek glass bottle with fresh lime and mint, bright white background, clean lifestyle product photography",
      "asset_path": null
    },
    {
      "id": "viva_energy_bar",
      "name": "Viva Energy Bar",
      "description": "Natural energy bar with visible oats and dark chocolate chips on a rustic wooden surface, warm morning light, health and vitality",
      "asset_path": null
    }
  ]
}
```

---

## Asset Reuse Logic

If `asset_path` is set and the file exists at that path, the pipeline reuses it directly
and skips image generation for that product. If the file is missing or `asset_path` is
`null`, the pipeline generates a new image using the configured provider (Flux or GPT Image 1).

Generated images are cached in `assets/generated/` and resolved by convention before
falling back to generation on subsequent runs.

---

## Natural Language Input

The web UI accepts a plain-English campaign description and calls `POST /api/brief/parse`
to convert it to this schema via GPT-4o. The NL parser enforces the same validation rules.
The resulting JSON is displayed in the editor before the pipeline runs and can be edited
manually before submission.
