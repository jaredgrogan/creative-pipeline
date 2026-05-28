"""
MODULE: generators.base
WHAT: Abstract base class defining the interface every image generator must implement.
DECISION: Provider-agnostic contract — generate(prompt, product_id) returns a local
file path regardless of which API was called. Pipeline code never knows the provider.
PRODUCTION ALTERNATIVE: Interface extended with async generate(), cost_estimate(),
and capability flags (supports_inpainting, max_resolution, etc.).
"""

from abc import ABC, abstractmethod


class ImageGeneratorBase(ABC):

    @abstractmethod
    def generate(self, prompt, product_id):
        """
        Generate a hero image from prompt.
        Saves to assets/generated/{product_id}_hero.png.
        Returns local file path string on success, raises on failure.
        """
        pass
