"""
MODULE: report_generator
WHAT: Generates a self-contained HTML report displaying all output creatives organized
by product and format, with a run summary table at the bottom.
DECISION: A pipeline that produces files no one can easily review is incomplete. The
HTML report closes the output loop -- client-viewable in any browser, no server required.
Images are base64-encoded inline so the file is fully portable: email it, share it,
open it offline. No CDN, no external CSS, no JavaScript dependencies.
PRODUCTION ALTERNATIVE: A dashboard in a campaign management platform showing real-time
creative status, compliance scores, approval workflow state, and performance metrics
once campaigns go live.
"""

import base64
import webbrowser
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR, REPORT_FILENAME, REPORT_AUTO_OPEN, ASPECT_RATIOS


def generate_report(output_paths_by_product, run_summary):
    """
    Generate outputs/report.html and optionally open it in the browser.

    Args:
        output_paths_by_product: dict of {product_id: [Path, ...]}
            Paths ordered to match ASPECT_RATIOS order (1x1, 9x16, 16x9).
        run_summary: dict with keys from logger.write_summary stats
            (campaign_id, generated, reused, errors, provider, duration_s, cost)

    Returns:
        Path to the generated report file.
    """
    report_path = OUTPUT_DIR / REPORT_FILENAME
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    html = _build_html(output_paths_by_product, run_summary)
    report_path.write_text(html, encoding="utf-8")

    if REPORT_AUTO_OPEN:
        webbrowser.open(report_path.as_uri())

    return report_path


# ---------------------------------------------------------------------------
# HTML construction
# ---------------------------------------------------------------------------

def _build_html(output_paths_by_product, run_summary):
    campaign_id = run_summary.get("campaign_id", "Campaign Report")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    product_sections = "\n".join(
        _product_section(product_id, paths)
        for product_id, paths in output_paths_by_product.items()
    )

    summary_rows = _summary_table_rows(run_summary)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{campaign_id} -- Creative Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #0f0f13;
    color: #e8e8f0;
    padding: 40px 32px;
    min-height: 100vh;
  }}
  .header {{
    border-bottom: 1px solid #2a2a3a;
    padding-bottom: 24px;
    margin-bottom: 40px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }}
  .header-left h1 {{
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #ffffff;
  }}
  .header-left .meta {{
    font-size: 13px;
    color: #6b6b85;
    margin-top: 6px;
  }}
  .badge {{
    display: inline-block;
    background: #1e1e2e;
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 12px;
    color: #9b9bb5;
    margin-right: 8px;
  }}
  .product-section {{
    margin-bottom: 56px;
  }}
  .product-title {{
    font-size: 16px;
    font-weight: 600;
    color: #c8c8e0;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1e1e2e;
  }}
  .format-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }}
  .format-card {{
    background: #1a1a26;
    border: 1px solid #2a2a3a;
    border-radius: 10px;
    overflow: hidden;
  }}
  .format-card-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 14px;
    border-top: 1px solid #2a2a3a;
  }}
  .format-label {{
    font-size: 11px;
    font-weight: 600;
    color: #6b6b85;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .btn-dl {{
    font-size: 11px;
    font-weight: 600;
    color: #007aff;
    text-decoration: none;
    letter-spacing: 0.03em;
  }}
  .btn-dl:hover {{ opacity: 0.75; }}
  .format-image-wrap {{
    padding: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
    background: #111118;
    min-height: 180px;
  }}
  .format-image-wrap img {{
    max-width: 100%;
    max-height: 320px;
    border-radius: 4px;
    display: block;
  }}
  .missing-image {{
    font-size: 12px;
    color: #555568;
    padding: 40px;
    text-align: center;
  }}
  .summary-section {{
    margin-top: 60px;
    border-top: 1px solid #2a2a3a;
    padding-top: 32px;
  }}
  .summary-section h2 {{
    font-size: 15px;
    font-weight: 600;
    color: #c8c8e0;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 16px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  td {{
    padding: 10px 14px;
    border-bottom: 1px solid #1e1e2e;
    color: #9b9bb5;
  }}
  td:first-child {{
    color: #6b6b85;
    width: 180px;
    font-weight: 500;
  }}
  td.ok {{ color: #2ecc71; }}
  td.warn {{ color: #e67e22; }}
  .footer {{
    margin-top: 48px;
    font-size: 11px;
    color: #3a3a50;
    text-align: center;
  }}
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <h1>{campaign_id}</h1>
    <div class="meta">
      <span class="badge">Creative Automation Pipeline</span>
      <span class="badge">{timestamp}</span>
    </div>
  </div>
</div>

{product_sections}

<div class="summary-section">
  <h2>Run Summary</h2>
  <table>
    {summary_rows}
  </table>
</div>

<div class="footer">Generated by Creative Automation Pipeline</div>
</body>
</html>""".format(
        campaign_id=campaign_id,
        timestamp=timestamp,
        product_sections=product_sections,
        summary_rows=summary_rows,
    )


def _product_section(product_id, paths):
    """Build the HTML block for one product with its three format images."""
    display_name = product_id.replace("_", " ").title()
    format_cards = ""

    # Build a map from format_name to path for safe lookup
    path_by_format = {}
    for p in paths:
        path_by_format[Path(p).stem] = p  # stem = "1x1", "9x16", "16x9"

    for ratio in ASPECT_RATIOS:
        format_name = ratio["name"]
        label = ratio["label"]
        image_path = path_by_format.get(format_name)

        if image_path and Path(image_path).exists():
            b64 = _encode_image(image_path)
            filename = "{}_{}.png".format(product_id, format_name)
            img_tag = '<img src="data:image/png;base64,{b64}" alt="{name} {fmt}">'.format(
                b64=b64, name=display_name, fmt=format_name
            )
            dl_link = '<a class="btn-dl" href="data:image/png;base64,{b64}" download="{fn}" data-b64="{b64}" data-filename="{fn}">&#8595; Download</a>'.format(
                b64=b64, fn=filename
            )
        else:
            img_tag = '<div class="missing-image">Image not found</div>'
            dl_link = ''

        format_cards += """
    <div class="format-card">
      <div class="format-image-wrap">{img_tag}</div>
      <div class="format-card-footer">
        <span class="format-label">{label}</span>
        {dl_link}
      </div>
    </div>""".format(label=label, img_tag=img_tag, dl_link=dl_link)

    return """
<div class="product-section">
  <div class="product-title">{display_name}</div>
  <div class="format-grid">{format_cards}
  </div>
</div>""".format(display_name=display_name, format_cards=format_cards)


def _summary_table_rows(run_summary):
    """Build table rows from the run summary dict."""
    provider = run_summary.get("provider", "unknown")
    generated = run_summary.get("generated", 0)
    reused = run_summary.get("reused", 0)
    errors = run_summary.get("errors", 0)
    duration = run_summary.get("duration_s", 0)
    cost = run_summary.get("cost_estimate", 0)
    campaign_id = run_summary.get("campaign_id", "--")

    error_class = "warn" if errors > 0 else "ok"

    rows = [
        ("Campaign ID", campaign_id, ""),
        ("Provider", provider, ""),
        ("Images generated", str(generated), ""),
        ("Assets reused", str(reused), ""),
        ("Errors", str(errors), error_class),
        ("Duration", "{:.1f}s".format(duration), ""),
        ("Estimated API cost", "${:.4f}".format(cost), ""),
    ]

    html = ""
    for label, value, css_class in rows:
        html += "<tr><td>{}</td><td class=\"{}\">{}</td></tr>\n".format(
            label, css_class, value
        )
    return html


def _encode_image(image_path):
    """Base64-encode an image file for inline HTML embedding."""
    with open(str(image_path), "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
