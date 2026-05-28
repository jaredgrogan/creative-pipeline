"""
MODULE: generators.google_generator
WHAT: Stub for Google Imagen image generation (optional third provider).
DECISION: Included as a stub to demonstrate the provider-agnostic architecture
is genuinely extensible. Adding a real provider means implementing one class.
PRODUCTION ALTERNATIVE: Google Imagen 3 via Vertex AI — strong quality, integrates
with Google Cloud storage and IAM for enterprise deployments.
"""

from generators.base import ImageGeneratorBase


class GoogleGenerator(ImageGeneratorBase):

    def __init__(self):
        raise NotImplementedError(
            "Google Imagen integration is not yet implemented. "
            "Set IMAGE_PROVIDER=flux or IMAGE_PROVIDER=gpt-image-1 in your .env file."
        )

    def generate(self, prompt, product_id):
        pass
