"""
MODULE: app
WHAT: Streamlit UI -- primary interface for the creative automation pipeline.
Accepts a campaign brief via natural language input or JSON file upload, runs the
pipeline with live progress, and displays results inline.
DECISION: A browser UI makes the tool accessible to non-technical users (brand
managers, creative directors) without any CLI knowledge. Streamlit runs locally
with a single command -- no deployment required for the POC.
PRODUCTION ALTERNATIVE: A purpose-built web application with auth, campaign history,
approval workflow, and DAM integration.
"""

import json
import os
from pathlib import Path

import streamlit as st


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
    except ImportError:
        pass


def main():
    _load_env()

    st.set_page_config(
        page_title="Creative Automation Pipeline",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ------------------------------------------------------------------
    # Sidebar -- API keys + campaign history
    # ------------------------------------------------------------------
    with st.sidebar:
        st.title("API Keys")
        _render_api_key_settings()
        st.divider()
        st.title("Campaign History")
        _render_sidebar()

    # ------------------------------------------------------------------
    # Main header
    # ------------------------------------------------------------------
    st.title("Creative Automation Pipeline")
    st.caption("Generate branded social creatives from a campaign brief.")

    # ------------------------------------------------------------------
    # Run settings
    # ------------------------------------------------------------------
    col_left, col_p, col_tc, col_fs, col_fb = st.columns([2, 1, 1, 1, 1])
    with col_p:
        provider_choice = st.selectbox(
            "Image Provider",
            options=["flux", "gpt-image-1"],
            index=0,
            format_func=lambda x: {"flux": "Flux 1.1 Pro", "gpt-image-1": "GPT Image 1"}.get(x, x),
            help="Flux 1.1 Pro is the primary provider. GPT Image 1 is the OpenAI fallback.",
        )
        os.environ["IMAGE_PROVIDER"] = provider_choice
    with col_tc:
        text_color_choice = st.selectbox(
            "Text Color",
            options=["white", "black"],
            index=0,
            help="Text overlay color. Shadow is always the opposite color.",
        )
    with col_fs:
        font_style_choice = st.selectbox(
            "Font Style",
            options=["sans", "serif", "mono"],
            index=0,
            help="sans: Arial/Roboto. serif: Times New Roman/Georgia. mono: Consolas/Courier.",
        )
    with col_fb:
        font_bold_choice = st.selectbox(
            "Font Weight",
            options=["bold", "regular"],
            index=0,
            help="bold (default) or regular weight.",
        )
        font_bold_value = (font_bold_choice == "bold")

    # ------------------------------------------------------------------
    # Brief input tabs
    # ------------------------------------------------------------------
    tab_nl, tab_json = st.tabs(["Natural Language Brief", "JSON Brief"])

    brief = None
    nl_parse_used = False

    with tab_nl:
        st.markdown("Describe your campaign in plain language. The pipeline will parse it into a structured brief.")
        example_nl = (
            "Campaign for Viva brand. Summer 2026 launch. "
            "Two products: a sparkling water with tropical fruit flavor and an energy bar with nuts and honey. "
            "Target health-conscious adults in the US market. "
            "Brand colors: coral (#FF6B6B) and teal (#4ECDC4). "
            "Campaign message: 'Fuel Your Summer'. English only."
        )
        nl_input = st.text_area(
            "Campaign brief",
            value="",
            height=180,
            placeholder="Describe your campaign here — brand, products, audience, region, and message...",
        )
        if st.button("Parse Brief", key="parse_nl"):
            if not nl_input.strip():
                st.warning("Enter a brief description first.")
            else:
                with st.spinner("Parsing brief with GPT-4o..."):
                    parsed = _parse_nl_brief(nl_input.strip())
                if parsed:
                    st.session_state["nl_brief"] = parsed
                    st.session_state["nl_parse_used"] = True
                    st.success("Brief parsed successfully.")
                    st.json(parsed)
                else:
                    st.error("Failed to parse brief. Check your OpenAI API key and try again.")

        if "nl_brief" in st.session_state:
            brief = st.session_state["nl_brief"]
            nl_parse_used = st.session_state.get("nl_parse_used", False)
            if st.button("Run Pipeline", key="run_nl", type="primary"):
                brief = dict(brief)
                brief["text_color"] = text_color_choice
                brief["font_style"] = font_style_choice
                brief["font_bold"] = font_bold_value
                _run_and_display(brief, nl_parse_used)

    with tab_json:
        st.markdown("Upload a JSON brief file or paste JSON directly.")
        uploaded = st.file_uploader("Upload brief JSON", type=["json"])
        json_paste = st.text_area(
            "Or paste JSON here",
            value="",
            height=200,
            placeholder='{"campaign_id": "summer_2026", "brand": {...}, "products": [...]}',
        )

        json_brief = None
        if uploaded:
            try:
                json_brief = json.loads(uploaded.read().decode("utf-8"))
                st.success("File loaded: {}".format(uploaded.name))
            except Exception as exc:
                st.error("JSON parse error: {}".format(exc))
        elif json_paste.strip():
            try:
                json_brief = json.loads(json_paste.strip())
            except Exception as exc:
                st.error("JSON parse error: {}".format(exc))

        # Load the default brief as a convenience
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Load example brief", key="load_example"):
                example_path = Path(__file__).parent / "campaign_brief.json"
                if example_path.exists():
                    json_brief = json.loads(example_path.read_text(encoding="utf-8"))
                    st.session_state["example_brief"] = json_brief
                    st.success("Loaded campaign_brief.json")
                    st.json(json_brief)
                else:
                    st.warning("campaign_brief.json not found in pipeline directory.")

        if "example_brief" in st.session_state and json_brief is None:
            json_brief = st.session_state["example_brief"]

        if json_brief:
            with col_b:
                if st.button("Run Pipeline", key="run_json", type="primary"):
                    json_brief = dict(json_brief)
                    json_brief["text_color"] = text_color_choice
                    json_brief["font_style"] = font_style_choice
                    json_brief["font_bold"] = font_bold_value
                    _run_and_display(json_brief, nl_parse_used=False)


# ---------------------------------------------------------------------------
# Pipeline execution and results display
# ---------------------------------------------------------------------------

def _run_and_display(brief, nl_parse_used):
    """Run the pipeline and render results inline."""
    from pipeline import run_pipeline
    from logger import reset_logger

    reset_logger()

    st.divider()
    st.subheader("Pipeline Progress")

    progress_area = st.empty()
    log_lines = []

    def progress_callback(stage, message):
        log_lines.append("[{}] {}".format(stage, message))
        progress_area.code("\n".join(log_lines[-20:]), language=None)

    with st.spinner("Running pipeline..."):
        try:
            result = run_pipeline(brief, progress_callback=progress_callback, nl_parse_used=nl_parse_used)
        except Exception as exc:
            st.error("Pipeline error: {}".format(exc))
            return

    progress_area.empty()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    if not result["success"] and result.get("errors"):
        st.error("Pipeline failed:")
        for err in result["errors"]:
            st.write("- {}".format(err))
        return

    summary = result["run_summary"]

    # Metrics row
    st.subheader("Run Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Products", result["products_processed"])
    c2.metric("Generated", summary.get("generated", 0))
    c3.metric("Reused", summary.get("reused", 0))
    c4.metric("Duration", "{:.1f}s".format(summary.get("duration_s", 0)))
    c5.metric("Est. Cost", "${:.4f}".format(summary.get("cost_estimate", 0)))

    if result.get("report_path"):
        st.info("HTML report saved: {}".format(result["report_path"]))

    # Creative output by product
    st.divider()
    st.subheader("Creative Outputs")

    for product_id, paths in result["outputs_by_product"].items():
        display_name = product_id.replace("_", " ").title()
        st.markdown("**{}**".format(display_name))

        cols = st.columns(len(paths))
        for col, img_path in zip(cols, paths):
            with col:
                label = Path(img_path).stem  # 1x1, 9x16, 16x9
                st.caption(label)
                if Path(img_path).exists():
                    st.image(str(img_path), use_container_width=True)
                else:
                    st.warning("Image not found")

        # Compliance summary
        product_compliance = result.get("compliance_by_product", {}).get(product_id, {})
        if product_compliance:
            with st.expander("Brand compliance details -- {}".format(display_name)):
                for img_path, comp in product_compliance.items():
                    st.markdown("**{}**".format(Path(img_path).name))
                    logo_status = comp.get("logo_present")
                    color_status = comp.get("color_compliant")
                    logo_label = "OK" if logo_status is True else ("MISSING" if logo_status is False else "skipped")
                    color_label = "OK" if color_status is True else ("NON-COMPLIANT" if color_status is False else "skipped")
                    st.write("Logo: {} | Colors: {}".format(logo_label, color_label))
                    if comp.get("dominant_colors"):
                        st.write("Dominant colors: {}".format(", ".join(comp["dominant_colors"])))
                    for note in comp.get("notes", []):
                        st.caption(note)


# ---------------------------------------------------------------------------
# NL brief parser call
# ---------------------------------------------------------------------------

def _parse_nl_brief(text):
    """Call brief_parser_nl and return parsed dict or None on failure."""
    try:
        from brief_parser_nl import parse_natural_language_brief
        return parse_natural_language_brief(text)
    except Exception as exc:
        st.error("NL parse error: {}".format(exc))
        return None


# ---------------------------------------------------------------------------
# Sidebar -- API key settings
# ---------------------------------------------------------------------------

def _render_api_key_settings():
    """
    Let users enter API keys directly in the UI. Keys are written to .env
    and loaded into the environment for the current session. Never displayed
    after saving -- shown as password fields only while being entered.
    """
    env_path = Path(__file__).parent / ".env"

    bfl_key = os.getenv("BFL_API_KEY", "")
    oai_key = os.getenv("OPENAI_API_KEY", "")

    bfl_status = "configured" if bfl_key else "not set"
    oai_status = "configured" if oai_key else "not set"

    with st.expander("Configure API Keys ({} / {})".format(bfl_status, oai_status)):
        st.caption("Keys are saved to .env in the pipeline directory and never logged.")

        new_bfl = st.text_input(
            "BFL API Key (Flux)",
            value="",
            type="password",
            placeholder="Paste key -- leave blank to keep current",
            key="input_bfl_key",
        )
        new_oai = st.text_input(
            "OpenAI API Key",
            value="",
            type="password",
            placeholder="Paste key -- leave blank to keep current",
            key="input_oai_key",
        )

        if st.button("Save Keys", key="save_api_keys"):
            updated = False
            if new_bfl.strip():
                os.environ["BFL_API_KEY"] = new_bfl.strip()
                updated = True
            if new_oai.strip():
                os.environ["OPENAI_API_KEY"] = new_oai.strip()
                updated = True

            if updated:
                _write_env(env_path)
                st.success("Keys saved to .env and active for this session.")
            else:
                st.info("No changes -- enter a key value to update.")


def _write_env(env_path):
    """Write current BFL_API_KEY and OPENAI_API_KEY to .env file."""
    lines = []
    # Preserve any existing lines that are not the keys we manage
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if (not stripped.startswith("BFL_API_KEY=")
                    and not stripped.startswith("OPENAI_API_KEY=")
                    and not stripped.startswith("IMAGE_PROVIDER=")):
                lines.append(line)

    bfl = os.getenv("BFL_API_KEY", "")
    oai = os.getenv("OPENAI_API_KEY", "")
    provider = os.getenv("IMAGE_PROVIDER", "flux")

    if bfl:
        lines.append("BFL_API_KEY={}".format(bfl))
    if oai:
        lines.append("OPENAI_API_KEY={}".format(oai))
    lines.append("IMAGE_PROVIDER={}".format(provider))

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Sidebar -- campaign history
# ---------------------------------------------------------------------------

def _render_sidebar():
    from campaign_store import list_campaigns

    try:
        campaigns = list_campaigns()
    except Exception:
        campaigns = []

    if not campaigns:
        st.caption("No previous campaigns found.")
        return

    st.caption("{} previous campaign(s)".format(len(campaigns)))

    for camp in campaigns[:10]:  # show 10 most recent
        campaign_id = camp["campaign_id"]
        saved_at = camp["timestamp"][:16].replace("T", " ") if camp["timestamp"] else ""
        with st.expander("{} -- {}".format(campaign_id, saved_at)):
            summary = camp.get("summary", {})
            st.write("Provider: {}".format(summary.get("provider", "--")))
            st.write("Generated: {}".format(summary.get("generated", 0)))
            st.write("Reused: {}".format(summary.get("reused", 0)))
            st.write("Duration: {:.1f}s".format(summary.get("duration_s", 0)))
            cost = summary.get("cost_estimate", 0)
            st.write("Cost: ${:.4f}".format(cost))


if __name__ == "__main__":
    main()
