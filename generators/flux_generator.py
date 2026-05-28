"""
MODULE: generators.flux_generator
WHAT: Generates hero images via the Black Forest Labs Flux 1.1 Pro direct API.
Uses an async submit-then-poll pattern: submit the job, receive a task ID, poll
until the result URL is ready, then download and save locally.
DECISION: Flux 1.1 Pro produces significantly more photorealistic output than
gpt-image-1 for lifestyle product photography -- critical when visual quality is the
primary differentiator for social ad creatives. The BFL direct API avoids
third-party intermediaries (fal.ai, Replicate) and their additional latency.
PRODUCTION ALTERNATIVE: Replace polling loop with a webhook callback. At scale,
polling N concurrent jobs is wasteful -- push notification is the correct pattern.
"""

import time
import requests
from pathlib import Path

from generators.base import ImageGeneratorBase
from config import (
    BFL_API_BASE, BFL_MODEL, BFL_IMAGE_WIDTH, BFL_IMAGE_HEIGHT,
    GENERATED_ASSETS_DIR, MAX_RETRY_ATTEMPTS, RETRY_BACKOFF_SECONDS,
)

import os

POLL_INTERVAL = 2    # seconds between status checks
POLL_TIMEOUT = 120   # max seconds to wait for a result


class FluxGenerator(ImageGeneratorBase):

    def __init__(self):
        self.api_key = os.getenv("BFL_API_KEY")
        if not self.api_key:
            raise EnvironmentError("BFL_API_KEY is not set. Add it to your .env file.")
        self.headers = {
            "x-key": self.api_key,
            "Content-Type": "application/json",
        }
        GENERATED_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt, product_id):
        """
        Submit, poll, download. Retries up to MAX_RETRY_ATTEMPTS on any failure.
        Returns local file path (str) on success. Raises RuntimeError after all retries.
        """
        last_exc = None
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                task_id, polling_url = self._submit(prompt)
                image_url = self._poll(task_id, polling_url)
                return self._download(image_url, product_id)
            except Exception as exc:
                last_exc = exc
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    delay = RETRY_BACKOFF_SECONDS[attempt]
                    time.sleep(delay)

        raise RuntimeError(
            "Flux generation failed after {} attempts. Last error: {}".format(
                MAX_RETRY_ATTEMPTS, last_exc
            )
        )

    def _submit(self, prompt):
        """POST generation request. Returns (task_id, polling_url) tuple."""
        url = "{}/{}".format(BFL_API_BASE, BFL_MODEL)
        payload = {
            "prompt": prompt,
            "width": BFL_IMAGE_WIDTH,
            "height": BFL_IMAGE_HEIGHT,
        }
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        task_id = data.get("id")
        if not task_id:
            raise RuntimeError("Flux submit returned no task ID. Response: {}".format(data))
        # Use the polling_url from the response -- BFL routes to regional subdomains
        # (e.g. api.us4.bfl.ai) that differ from the submission host.
        polling_url = data.get("polling_url") or "{}/get_result?id={}".format(BFL_API_BASE, task_id)
        return task_id, polling_url

    def _poll(self, task_id, polling_url):
        """
        Poll get_result until status is Ready. Returns the image URL.
        Raises RuntimeError on error status or timeout.
        """
        elapsed = 0

        while elapsed < POLL_TIMEOUT:
            response = requests.get(polling_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            status = data.get("status")

            if status == "Ready":
                image_url = data.get("result", {}).get("sample")
                if not image_url:
                    raise RuntimeError("Flux result is Ready but sample URL is missing.")
                return image_url

            if status == "Error":
                raise RuntimeError("Flux job failed with error status. Task: {}".format(task_id))

            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        raise RuntimeError(
            "Flux job timed out after {}s. Task: {}".format(POLL_TIMEOUT, task_id)
        )

    def _download(self, image_url, product_id):
        """Download image from URL and save to assets/generated/. Returns local path str."""
        dest = GENERATED_ASSETS_DIR / "{}_hero.png".format(product_id)
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        dest.write_bytes(response.content)
        return str(dest)
