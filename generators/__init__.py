"""
MODULE: generators
WHAT: Provider factory and shared prompt builder for image generation.
DECISION: One config value (IMAGE_PROVIDER) selects the active model. Adding a new
provider means writing one class and one factory case -- no changes to pipeline logic.
build_prompt() lives here so both generators produce identical prompts from the same
brief data -- consistent input means comparable output across providers.
PRODUCTION ALTERNATIVE: Dynamic provider loading from a registry, with per-campaign
provider selection based on cost, quality tier, and regional availability.
"""

import os


def get_generator():
    """
    Return the configured ImageGeneratorBase implementation.
    Provider is read from IMAGE_PROVIDER env var (default: flux).
    """
    provider = os.getenv("IMAGE_PROVIDER", "flux")
    if provider == "flux":
        from generators.flux_generator import FluxGenerator
        return FluxGenerator()
    if provider == "gpt-image-1":
        from generators.openai_generator import OpenAIGenerator
        return OpenAIGenerator()
    raise ValueError(
        "Unknown IMAGE_PROVIDER: '{}'. Valid options: flux, gpt-image-1".format(provider)
    )


def build_prompt(product, brief):
    """
    Build the image generation prompt from product description and brief context.
    The product description is written to be rich with visual detail. Region,
    audience, and campaign message add contextual tone without overriding visuals.
    """
    return (
        "{description}. "
        "Product for the {region} market, targeting {audience}. "
        "Campaign tone: {message}. "
        "Professional product photography, high quality, commercial use."
    ).format(
        description=product["description"],
        region=brief["region"],
        audience=brief["target_audience"],
        message=brief["campaign_message"],
    )
