"""
MODULE: main
WHAT: CLI entry point. Parses arguments, loads the brief, and calls run_pipeline.
DECISION: main.py contains orchestration only -- no business logic. One responsibility:
take a brief path from the command line and hand it to the pipeline.
PRODUCTION ALTERNATIVE: A scheduled job runner or webhook handler replaces the CLI
as the entry point, calling run_pipeline with briefs from an upstream system.
"""

import argparse
import os
import sys
from pathlib import Path



def _load_env():
    """Load .env file if python-dotenv is available. Silently skips if not."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
    except ImportError:
        pass


def _run_setup():
    """Interactive prompt to enter API keys and write them to .env."""
    env_path = Path(__file__).parent / ".env"

    print("Creative Automation Pipeline -- API Key Setup")
    print("Keys will be written to: {}".format(env_path))
    print("Press Enter to keep the current value for any key.\n")

    current_bfl = os.getenv("BFL_API_KEY", "")
    current_oai = os.getenv("OPENAI_API_KEY", "")
    current_provider = os.getenv("IMAGE_PROVIDER", "flux")

    bfl_display = "[configured]" if current_bfl else "[not set]"
    oai_display = "[configured]" if current_oai else "[not set]"

    bfl = input("BFL_API_KEY (Flux) {} > ".format(bfl_display)).strip()
    oai = input("OPENAI_API_KEY {} > ".format(oai_display)).strip()
    provider = input("IMAGE_PROVIDER (flux/gpt-image-1) [{}] > ".format(current_provider)).strip()

    final_bfl = bfl or current_bfl
    final_oai = oai or current_oai
    final_provider = provider if provider in ("flux", "gpt-image-1") else current_provider

    _write_env(env_path, final_bfl, final_oai, final_provider)
    print("\nKeys saved to {}".format(env_path))
    print("Run the pipeline: python main.py --generate campaign_brief.json")


def _write_env(env_path, bfl_key, oai_key, provider):
    """Write API keys and provider choice to .env. Preserves unrecognized lines."""
    managed = {"BFL_API_KEY", "OPENAI_API_KEY", "IMAGE_PROVIDER"}
    lines = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip()
            if key not in managed:
                lines.append(line)
    if bfl_key:
        lines.append("BFL_API_KEY={}".format(bfl_key))
    if oai_key:
        lines.append("OPENAI_API_KEY={}".format(oai_key))
    lines.append("IMAGE_PROVIDER={}".format(provider))
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _progress(stage, message):
    print("[{}] {}".format(stage, message))


def main():
    _load_env()

    parser = argparse.ArgumentParser(
        description="Creative Automation Pipeline -- generate branded social creatives from a brief"
    )
    parser.add_argument(
        "--generate",
        default=None,
        help="Path to a campaign brief JSON file -- runs the full pipeline and generates all creatives",
    )
    parser.add_argument(
        "--provider",
        choices=["flux", "gpt-image-1"],
        default=None,
        help="Image generation provider (overrides IMAGE_PROVIDER env var)",
    )
    parser.add_argument(
        "--parse",
        default=None,
        metavar="TEXT",
        help="Parse a natural language campaign description into a structured JSON brief",
    )
    parser.add_argument(
        "--upload-azure",
        action="store_true",
        help="Upload generated outputs to Azure Blob Storage after pipeline run",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Interactive prompt to enter and save API keys to .env",
    )
    args = parser.parse_args()

    if args.setup:
        _run_setup()
        return

    if args.parse:
        import json
        from brief_parser_nl import parse_natural_language_brief
        print("Parsing brief with GPT-4o...")
        result = parse_natural_language_brief(args.parse)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("ERROR: Failed to parse brief. Check your OPENAI_API_KEY.")
            sys.exit(1)
        return

    if not args.generate:
        parser.error("--generate is required unless --setup is used")

    # Allow provider override via CLI flag
    if args.provider:
        os.environ["IMAGE_PROVIDER"] = args.provider

    # Import after env is set so config picks up overrides
    from brief_parser import load_brief
    from pipeline import run_pipeline

    # --- Brief loading: Azure Blob or local file ---
    if args.generate.startswith("az://"):
        blob_name = args.generate[len("az://"):]
        print("Loading brief from Azure Blob: {}".format(blob_name))
        try:
            from azure_storage import download_brief
            raw = download_brief(blob_name)
            import tempfile, json
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                json.dump(raw, tmp)
                tmp_path = tmp.name
            brief = load_brief(tmp_path)
        except Exception as exc:
            print("ERROR: Failed to load brief from Azure -- {}".format(exc))
            sys.exit(1)
    else:
        brief_path = Path(args.generate)
        if not brief_path.exists():
            print("ERROR: Brief file not found: {}".format(brief_path))
            sys.exit(1)
        try:
            brief = load_brief(str(brief_path))
        except (ValueError, KeyError) as exc:
            print("ERROR: Invalid brief -- {}".format(exc))
            sys.exit(1)

    print("=" * 60)
    print("Creative Automation Pipeline")
    print("Brief: {}".format(brief_path))
    print("Provider: {}".format(os.getenv("IMAGE_PROVIDER", "flux")))
    print("=" * 60)

    result = run_pipeline(brief, progress_callback=_progress)

    print("=" * 60)
    if result["success"]:
        print("Pipeline completed successfully")
        print("  Products processed: {}".format(result["products_processed"]))
        summary = result["run_summary"]
        print("  Generated: {} images".format(summary.get("generated", 0)))
        print("  Reused: {} images".format(summary.get("reused", 0)))
        print("  Duration: {:.1f}s".format(summary.get("duration_s", 0)))
        print("  Est. cost: ${:.4f}".format(summary.get("cost_estimate", 0)))
        if result["report_path"]:
            print("  Report: {}".format(result["report_path"]))
        if args.upload_azure:
            print("Uploading outputs to Azure Blob Storage...")
            try:
                from azure_storage import upload_outputs
                uploaded = upload_outputs(result, brief["campaign_id"])
                print("  Uploaded {} files to Azure:".format(len(uploaded)))
                for b in uploaded:
                    print("    {}".format(b))
            except Exception as exc:
                print("  Azure upload failed: {}".format(exc))
    else:
        print("Pipeline completed with errors")
        for err in result.get("errors", []):
            print("  ERROR: {}".format(err))
        sys.exit(1)


if __name__ == "__main__":
    main()
