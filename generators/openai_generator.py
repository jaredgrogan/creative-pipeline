"""
MODULE: generators.openai_generator
WHAT: Generates hero images via OpenAI gpt-image-1. Synchronous -- a single API call
returns base64 image data directly with no polling required.
DECISION: Fallback provider for demonstrating multi-model capability. gpt-image-1
is simpler to integrate (no polling) and has lower latency per call. Used when
BFL_API_KEY is unavailable or when the user selects gpt-image-1 in the UI.
PRODUCTION ALTERNATIVE: Multi-model fallback chain: Flux -> gpt-image-1 -> placeholder
to guarantee pipeline completion even if both primary providers are unavailable.
"""

import base64
import os
import time
from pathlib import Path

from openai import OpenAI
from generators.base import ImageGeneratorBase
from config import (
    OPENAI_IMAGE_MODEL, OPENAI_IMAGE_SIZE, GENERATED_ASSETS_DIR,
    MAX_RETRY_ATTEMPTS, RETRY_BACKOFF_SECONDS,
)


class OpenAIGenerator(ImageGeneratorBase):

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
        self.client = OpenAI(api_key=api_key)
        GENERATED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt, product_id):
        """
        Generate via gpt-image-1, decode base64 response, and save locally.
        Retries up to MAX_RETRY_ATTEMPTS on any failure.
        Returns local file path (str) on success. Raises RuntimeError after all retries.
        """
        last_exc = None
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                response = self.client.images.generate(
                    model=OPENAI_IMAGE_MODEL,
                    prompt=prompt,
                    size=OPENAI_IMAGE_SIZE,
                    n=1,
                )
                b64_data = response.data[0].b64_json
                return self._save(b64_data, product_id)
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    delay = RETRY_BACKOFF_SECONDS[attempt]
                    time.sleep(delay)

        raise RuntimeError(
            "gpt-image-1 generation failed after {} attempts. Last error: {}".format(
                MAX_RETRY_ATTEMPTS, last_exc
            )
        )

    def _save(self, b64_data, product_id):
        """Decode base64 image and save to assets/generated/. Returns local path str."""
        dest = GENERATED_ASSETS_DIR / "{}_hero.png".format(product_id)
        dest.write_bytes(base64.b64decode(b64_data))
        return str(dest)
