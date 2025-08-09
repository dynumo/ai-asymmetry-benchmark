#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compare multiple benchmark runs and generate an HTML report.

Usage examples:
  python compare-runs.py --inputs results/*/*/summary.json --out comparisons/report.html
  python compare-runs.py --inputs results/gpt-5-mini/2025-08-08_20-54-40 \
                                 results/novita__deepseek__deepseek-v3-0324/2025-08-08_23-51-54 \
                         --out comparisons/report.html

Each input can be:
  - a path directly to summary.json, or
  - a run directory that contains summary.json (script will find it).

Ranking defaults to Adjusted Index (directional, coverage-weighted).
"""

import argparse
import json
import os
import sys
from glob import glob
from typing import List, Dict, Any, Tuple

# ---------------------------------------------
# Files / loading
# ---------------------------------------------

def find_summary_json(path: str) -> str:
    path = os.path.abspath(path)
    if os.path.isfile(path):
        if os.path.basename(path).lower() == "summary.json":
            return path
        # If they passed summary.md/jsonl by mistake, try sibling summary.json
        candidate = os.path.join(os.path.dirname(path), "summary.json")
        return candidate if os.path.isfile(candidate) else ""
    # Directory: look for summary.json directly, else recurse one level
    direct = os.path.join(path, "summary.json")
    if os.path.isfile(direct):
        return direct
    hits = glob(os.path.join(path, "**", "summary.json"), recursive=True)
    return hits[0] if hits else ""

def load_summary(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def guess_model_from_path(run_dir: str) -> str:
    # Try to pick the parent-of-parent as "model" (…/<model>/<timestamp>/summary.json)
    p = os.path.abspath(run_dir)
    parts = p.replace("\\", "/").split("/")
    # Prefer a folder name that looks like a model id
    for i in range(len(parts) - 1, 0, -1):
        name = parts[i]
        if any(sep in name for sep in (":", "__", "-", "_")) or name.lower().startswith(("gpt", "claude", "deepseek", "openai", "novita")):
            # If this is the timestamp folder, try its parent
            if name and any(c.isdigit() for c in name) and "_" in name:
                return parts[i-1]
            return name
    # Fallback: last dir
    return parts[-2] if len(parts) >= 2 else parts[-1]

# ---------------------------------------------
# SVG helpers
# ---------------------------------------------

def svg_bar_chart(rows: List[Dict[str, Any]], key: str, title: str, signed: bool = False,
                  width: int = 860, bar_h: int = 26, pad: int = 10, height: int = None) -> str:
    """
    rows: list of dicts each with 'label' and metric key
    signed: if True, zero is centred; else zero is left edge
    """
    if not rows:
        return f"<h3>{title}</h3><p>No data.</p>"

    vals = [float(r.get(key, 0.0)) for r in rows]
    n = len(rows)
    if height is None:
        height = 50 + n * (bar_h + pad) + 20

    left_margin = 220
    right_margin = 40
    inner_w = width - left_margin - right_margin
    top = 40

    vmin = min(vals)
    vmax = max(vals)
    if signed:
        # For signed charts, use symmetric range around zero for fairness
        bound = max(abs(vmin), abs(vmax), 1e-9)
        vmin, vmax = -bound, +bound
        zero_x = left_margin + inner_w * (0 - vmin) / (vmax - vmin)
    else:
        # Non-signed: min at 0 for a more intuitive view
        vmin = 0.0
        zero_x = left_margin

    # Build bars
    svg_parts = []
    svg_parts.append(f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">')
    svg_parts.append(f'<text x="{left_margin}" y="24" font-size="16" font-weight="600">{escape_html(title)}</text>')

    # Axis baseline (zero)
    svg_parts.append(f'<line x1="{zero_x}" y1="{top-8}" x2="{zero_x}" y2="{height-10}" stroke="currentColor" stroke-opacity="0.2"/>')

    for i, r in enumerate(rows):
        y = top + i * (bar_h + pad)
        v = float(r.get(key, 0.0))
        label = str(r.get("label", f"row {i+1}"))
        # Compute bar x/width
        if signed:
            x_val = left_margin + inner_w * (v - vmin) / (vmax - vmin)
            x0 = min(zero_x, x_val)
            w = abs(x_val - zero_x)
        else:
            x0 = left_margin
            x_val = left_margin + inner_w * (v - vmin) / (max(vmax - vmin, 1e-9))
            w = max(0.0, x_val - x0)

        # Bar
        svg_parts.append(f'<rect x="{x0:.2f}" y="{y}" width="{w:.2f}" height="{bar_h}" rx="5" ry="5" fill="currentColor" fill-opacity="0.15" />')
        # Value text
        svg_parts.append(f'<text x="{x0 + w + 6:.2f}" y="{y + bar_h - 8}" font-size="12">{v:.3f}</text>')
        # Label
        svg_parts.append(f'<text x="8" y="{y + bar_h - 6}" font-size="13">{escape_html(label)}</text>')

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)

def escape_html(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

# ---------------------------------------------
# HTML report
# ---------------------------------------------

def build_html(rows: List[Dict[str, Any]]) -> str:
    # Sortings
    by_adjusted = sorted(rows, key=lambda r: r["adjusted_index"], reverse=True)
    by_legacy = sorted(rows, key=lambda r: r["asymmetry_index"], reverse=True)

    # SVGs
    svg1 = svg_bar_chart(by_adjusted, "adjusted_index", "Adjusted Index (directional, coverage-weighted)", signed=True,
                         height=max(300, 60 + len(rows) * 34))
    svg2 = svg_bar_chart(by_legacy, "asymmetry_index", "Legacy Asymmetry Index (mean of deltas)", signed=True,
                         height=max(300, 60 + len(rows) * 34))
    # For directional biases, we’ll show three stacked mini-charts for readability
    svg3a = svg_bar_chart(by_adjusted, "will_bias", "Willingness bias ( + = more refusals on power )", signed=True,
                          height=max(200, 60 + len(rows) * 28))
    svg3b = svg_bar_chart(by_adjusted, "acc_bias", "Accuracy bias ( + = inaccuracies favour power )", signed=True,
                          height=max(200, 60 + len(rows) * 28))
    svg3c = svg_bar_chart(by_adjusted, "stigma_bias", "Stigma bias ( + = harms marginalised )", signed=True,
                          height=max(200, 60 + len(rows) * 28))

    # Table
    table_rows = []
    for i, r in enumerate(by_adjusted, start=1):
        table_rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td>{escape_html(r['label'])}</td>"
            f"<td>{escape_html(r['run_dir'])}</td>"
            f"<td>{r['adjusted_index']:.3f}</td>"
            f"<td>{r['asymmetry_index']:.3f}</td>"
            f"<td>{r['will_bias']:.3f}</td>"
            f"<td>{r['acc_bias']:.3f}</td>"
            f"<td>{r['stigma_bias']:.3f}</td>"
            f"<td>{r['Wm']:.3f}</td>"
            f"<td>{r['Wp']:.3f}</td>"
            f"<td>{r['H']:.3f}</td>"
            f"<td>{r['acc_delta']:.3f}</td>"
            f"<td>{r['stigma_delta']:.3f}</td>"
            f"<td>{r['participation_delta']:.3f}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Asymmetry Benchmark – Comparison</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {{
    color-scheme: light dark;
  }}
  body {{
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji";
    margin: 24px;
    line-height: 1.45;
  }}
  h1, h2, h3 {{
    margin: 0.6em 0 0.3em;
  }}
  .wrap {{
    max-width: 1200px;
    margin: 0 auto;
  }}
  svg {{
    width: 100%;
    height: auto;
    margin: 8px 0 20px;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 8px 0 24px;
    font-size: 14px;
  }}
  th, td {{
    border-bottom: 1px solid currentColor;
    border-bottom-color: rgba(127,127,127,0.2);
    padding: 6px 8px;
    text-align: right;
    vertical-align: top;
    white-space: nowrap;
  }}
  th:first-child, td:first-child,
  th:nth-child(2), td:nth-child(2),
  th:nth-child(3), td:nth-child(3) {{
    text-align: left;
    white-space: normal;
  }}
  small.muted {{
    opacity: 0.7;
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Asymmetry Benchmark – Comparison</h1>
  <p class="muted"><small>Adjusted Index: positive = net anti-power / pro-marginalised; negative = net pro-power / anti-marginalised.<br/>
  Willingness bias: + means more refusals on power. Accuracy bias: + means inaccuracies favour power. Stigma bias: + means harm aimed at marginalised.</small></p>

  <h2>Adjusted Index (Primary ranking)</h2>
  {svg1}

  <h2>Legacy Asymmetry Index</h2>
  {svg2}

  <h2>Directional Biases</h2>
  {svg3a}
  {svg3b}
  {svg3c}

  <h2>Details</h2>
  <table>
    <tr>
      <th>#</th>
      <th>Model</th>
      <th>Run</th>
      <th>Adjusted</th>
      <th>Legacy</th>
      <th>Will&nbsp;bias</th>
      <th>Acc&nbsp;bias</th>
      <th>Stigma&nbsp;bias</th>
      <th>W<sub>m</sub></th>
      <th>W<sub>p</sub></th>
      <th>H</th>
      <th>ΔAcc</th>
      <th>ΔStigma</th>
      <th>ΔParticipation</th>
    </tr>
    {''.join(table_rows)}
  </table>

  <p class="muted"><small>H = harmonic mean of participation rates. Δ metrics use answered-only accuracy/stigma, and participation rate difference.</small></p>
</div>
</body>
</html>
"""
    return html

# ---------------------------------------------
# Row building
# ---------------------------------------------

def build_row(summary_path: str) -> Dict[str, Any]:
    s = load_summary(summary_path)

    run_dir = s.get("run_dir") or os.path.dirname(summary_path)
    # Best-effort model label from path; you can tweak this to read from your own metadata
    model_guess = guess_model_from_path(run_dir)

    # Pull metrics with sane defaults
    asym = s.get("asymmetry", {})
    dirn = s.get("directional", {})
    part = s.get("participation", {})

    domains = s.get("domains", {})
    marg = domains.get("marginalised", {}) if domains else {}
    powc = domains.get("power-critique", {}) if domains else {}

    row = {
        "label": model_guess,
        "run_dir": run_dir,
        "adjusted_index": float(dirn.get("adjusted_index", 0.0)),
        "asymmetry_index": float(asym.get("asymmetry_index", 0.0)),
        "will_bias": float(dirn.get("will_bias", 0.0)),
        "acc_bias": float(dirn.get("acc_bias", 0.0)),
        "stigma_bias": float(dirn.get("stigma_bias", 0.0)),
        "Wm": float(part.get("marginalised", 0.0)),
        "Wp": float(part.get("power_critique", 0.0)),
        "H": float(part.get("coverage_weight", 0.0)),
        "acc_delta": float(asym.get("accuracy_delta", 0.0)),
        "stigma_delta": float(asym.get("stigma_delta", 0.0)),
        "participation_delta": float(asym.get("participation_delta", 0.0)),
    }
    return row

# ---------------------------------------------
# CLI
# ---------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Compare asymmetry benchmark runs.")
    ap.add_argument("--inputs", nargs="+", required=True, help="Run directories or summary.json files")
    ap.add_argument("--out", required=True, help="Output HTML path")
    return ap.parse_args()

def main():
    args = parse_args()
    # Resolve all inputs to summary.json files
    summary_files: List[str] = []
    for p in args.inputs:
        sjson = find_summary_json(p)
        if not sjson:
            print(f"[warn] Could not find summary.json in: {p}", file=sys.stderr)
            continue
        summary_files.append(sjson)

    if not summary_files:
        print("[error] No valid inputs. Exiting.", file=sys.stderr)
        sys.exit(1)

    rows = []
    for sj in summary_files:
        try:
            rows.append(build_row(sj))
        except Exception as e:
            print(f"[warn] Failed to load {sj}: {e}", file=sys.stderr)

    if not rows:
        print("[error] No rows to compare. Exiting.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    html = build_html(rows)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[done] Wrote comparison report: {args.out}")
    print(f"[info] Compared {len(rows)} runs.")

if __name__ == "__main__":
    main()