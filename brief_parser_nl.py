"""
MODULE: brief_parser_nl
WHAT: Converts a plain-English campaign description into a validated brief dict
using GPT-4o with JSON output mode. The result passes through the same validation
as a hand-written JSON brief.
DECISION: Real campaign managers describe campaigns in sentences, not JSON. This
module bridges that gap -- it is the POC equivalent of a structured intake form.
GPT-4o is used (not a smaller model) because brief parsing is the entry point to
the entire pipeline; a misparse here corrupts all downstream output.
PRODUCTION ALTERNATIVE: A structured intake form in a campaign management platform
whose submit action produces the validated JSON schema directly, with no LLM step.
The NL parser is appropriate for a POC where the input is a text field.
"""

import json
import os
from openai import OpenAI
from brief_parser import _validate_brief

SYSTEM_PROMPT = """You are a campaign brief parser for a creative automation pipeline.

The user will describe a marketing campaign in natural language. Extract the
information and return a JSON object that exactly matches this schema:

{
  "campaign_id": "slug using underscores, derived from campaign name only -- no year",
  "region": "target market region code, e.g. US, EU, JP, BR",
  "language": "ISO 639-1 language code, e.g. en, fr, ja, pt",
  "target_audience": "description of the target audience",
  "campaign_message": "the core headline or campaign message, suitable for text overlay on an ad",
  "brand": {
    "name": "brand name",
    "logo_path": null,
    "colors": []
  },
  "products": [
    {
      "id": "product_slug_with_underscores",
      "name": "Human Readable Product Name",
      "description": "detailed visual description for AI image generation -- describe the product appearance, setting, lighting, and mood",
      "asset_path": null
    }
  ]
}

Rules:
- products must contain at least 2 items
- campaign_message should be concise (under 10 words) and punchy -- suitable as ad copy
- product description should be rich with visual detail to guide image generation
- if region or language are not specified, default to US and en
- return only valid JSON, no commentary
"""


def parse_natural_language_brief(text):
    """
    Convert a plain-English campaign description to a validated brief dict.
    Returns the same dict shape as brief_parser.load_brief().
    Raises ValueError if the LLM output cannot be parsed or fails validation.
    Raises EnvironmentError if OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    try:
        brief = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("GPT-4o returned invalid JSON: {}".format(e))

    # Run through the same validation as a hand-written brief
    _validate_brief(brief)
    return brief
