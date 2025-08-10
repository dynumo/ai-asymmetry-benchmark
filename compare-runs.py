#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Compare multiple benchmark runs and generate accessible HTML + Markdown reports.

Updates in this version:
- Read delta index from summary.asymmetry.asymmetry_index (fixes all-zero issue)
- Rename "Legacy Asymmetry Index" -> "Delta Composite Index (mean of deltas)"
- Fixed, full-scale x-axes (not data-driven):
    * Adjusted Index: -3 .. +3
    * Delta / Bias charts: -2 .. +2
- Wider layout (max-w-7xl), league-table styling, dark mode, neon cyan bars with glow
- "Run" column removed, Markdown updated accordingly
"""

import argparse
import json
import os
import sys
from glob import glob
from html import escape as _escape
from typing import Any, Dict, List


# -----------------------------
# Utils
# -----------------------------

def escape_html(s: Any) -> str:
    try:
        return _escape(str(s), quote=True)
    except Exception:
        return _escape(repr(s), quote=True)


def find_summary_json(path: str) -> str:
    """Return absolute path to a summary.json (supports file, dir, or glob)."""
    path = os.path.abspath(path)
    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        sj = os.path.join(path, "summary.json")
        return sj if os.path.isfile(sj) else ""
    for m in glob(path):
        m = os.path.abspath(m)
        if os.path.isfile(m) and os.path.basename(m) == "summary.json":
            return m
        if os.path.isdir(m):
            sj = os.path.join(m, "summary.json")
            if os.path.isfile(sj):
                return sj
    return ""


def get_first(data: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
    """Return the first present numeric value among keys (dot-paths allowed)."""
    for k in keys:
        node = data
        ok = True
        for part in k.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if ok:
            try:
                return float(node)
            except Exception:
                try:
                    return float(str(node))
                except Exception:
                    pass
    return float(default)


def infer_label_from_path(run_dir: str) -> str:
    try:
        d = os.path.abspath(run_dir)
        parent = os.path.basename(os.path.dirname(d))
        if parent and parent.lower() != "results":
            return parent.replace("__", " / ").replace("_", " ")
        return os.path.basename(d)
    except Exception:
        return run_dir


# -----------------------------
# Data row
# -----------------------------

def build_row(summary_json_path: str) -> Dict[str, Any]:
    with open(summary_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    run_dir = data.get("run_dir") or os.path.dirname(os.path.abspath(summary_json_path))
    label = data.get("label") or data.get("model") or data.get("model_name") or infer_label_from_path(run_dir)

    adjusted_index = get_first(data, [
        "adjusted_index", "directional.adjusted_index", "metrics.adjusted_index"
    ], 0.0)

    # IMPORTANT: pick up nested asymmetry.asymmetry_index
    delta_composite = get_first(data, [
        "asymmetry.asymmetry_index",   # <-- correct for given JSON
        "asymmetry_index",
        "legacy.asymmetry_index",
        "metrics.asymmetry_index",
        "legacy_asymmetry_index",
    ], 0.0)

    will_bias = get_first(data, ["will_bias", "directional.will_bias", "metrics.will_bias"], 0.0)
    acc_bias = get_first(data, ["acc_bias", "directional.acc_bias", "metrics.acc_bias"], 0.0)
    stigma_bias = get_first(data, ["stigma_bias", "directional.stigma_bias", "metrics.stigma_bias"], 0.0)

    # Willingness means by domain
    doms = data.get("domains", {})
    marg = doms.get("marginalised", {})
    powc = doms.get("power-critique", doms.get("power_critique", {}))  # allow both spellings

    Wm = float(marg.get("willingness_mean", 0.0) or 0.0)
    Wp = float(powc.get("willingness_mean", 0.0) or 0.0)

    # Participation harmonic mean H
    part = data.get("participation", {})
    pm = float(part.get("marginalised", marg.get("participation", 0.0)) or 0.0)
    pp = float(part.get("power_critique", powc.get("participation", 0.0)) or 0.0)
    H = (2.0 / ((1.0 / pm) + (1.0 / pp))) if pm > 0 and pp > 0 else 0.0

    acc_delta = get_first(data, [
        "acc_delta", "directional.acc_delta", "metrics.acc_delta", "accuracy_delta",
        "asymmetry.accuracy_delta"
    ], 0.0)

    stigma_delta = get_first(data, [
        "stigma_delta", "directional.stigma_delta", "metrics.stigma_delta",
        "asymmetry.stigma_delta"
    ], 0.0)

    participation_delta = get_first(data, [
        "participation_delta", "directional.participation_delta", "metrics.participation_delta",
        "asymmetry.participation_delta"
    ], 0.0)

    return {
        "label": str(label),
        "run_dir": run_dir,
        "adjusted_index": adjusted_index,
        "delta_composite": delta_composite,   # renamed in our row
        "will_bias": will_bias,
        "acc_bias": acc_bias,
        "stigma_bias": stigma_bias,
        "Wm": Wm,
        "Wp": Wp,
        "H": H,
        "acc_delta": acc_delta,
        "stigma_delta": stigma_delta,
        "participation_delta": participation_delta,
    }


# -----------------------------
# HTML (Tailwind + Chart.js)
# -----------------------------

def build_html(rows: List[Dict[str, Any]]) -> str:
    # Rank by Adjusted Index (best first)
    by_adjusted = sorted(rows, key=lambda r: r["adjusted_index"], reverse=True)

    labels = [r["label"] for r in by_adjusted]
    adjusted = [round(float(r["adjusted_index"]), 6) for r in by_adjusted]
    delta_idx = [round(float(r["delta_composite"]), 6) for r in by_adjusted]
    will_b = [round(float(r["will_bias"]), 6) for r in by_adjusted]
    acc_b = [round(float(r["acc_bias"]), 6) for r in by_adjusted]
    stigma_b = [round(float(r["stigma_bias"]), 6) for r in by_adjusted]

    # Table rows (league-table vibe, no "Run")
    body_rows = []
    for i, r in enumerate(by_adjusted, start=1):
        badge = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)
        body_rows.append(
            "<tr class='border-t border-slate-200 dark:border-slate-700 odd:bg-white/40 even:bg-white/20 dark:odd:bg-white/5 dark:even:bg-white/0'>"
            f"<td class='py-3 pr-4 align-top font-semibold'>{badge}</td>"
            f"<td class='py-3 pr-4 align-top font-semibold whitespace-normal break-words'>{escape_html(r['label'])}</td>"
            f"<td class='py-3 pr-4 align-top font-bold'>{r['adjusted_index']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['delta_composite']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['will_bias']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['acc_bias']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['stigma_bias']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['Wm']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['Wp']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['H']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['acc_delta']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['stigma_delta']:.3f}</td>"
            f"<td class='py-3 pr-4 align-top'>{r['participation_delta']:.3f}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="en" class="h-full">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Asymmetry Benchmark – Comparison</title>

<!-- Tailwind (Play CDN) -->
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {{
    theme: {{
      extend: {{
        fontFamily: {{
          sans: ['ui-sans-serif','system-ui','-apple-system','Segoe UI','Roboto','Ubuntu','Cantarell','Helvetica Neue','Arial','Noto Sans']
        }}
      }}
    }}
  }}
</script>

<!-- Chart.js (no SRI for easy local open) -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>

<style>
  :root {{
    color-scheme: light dark;
    --card-bg: #ffffff;
    --fg: #0f172a;
    --muted: #475569;
    --grid: rgba(15,23,42,0.08);
  }}
  .dark :root, .dark {{
    --card-bg: #0b1220;
    --fg: #e5e7eb;
    --muted: #9fb1c9;
    --grid: rgba(226,232,240,0.12);
  }}
</style>
<script>
  // Sync Tailwind dark class with user preference
  const applyTheme = () => {{
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark', prefersDark);
  }};
  applyTheme();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
</script>
</head>

<body class="min-h-full bg-slate-50 text-slate-900 dark:bg-slate-900 dark:text-slate-100">
  <main class="max-w-7xl mx-auto px-5 py-6 sm:py-8">
    <header class="mb-6 sm:mb-8">
      <h1 class="text-3xl font-semibold tracking-tight">Asymmetry Benchmark – Comparison</h1>
      <p class="mt-2 text-lg text-slate-700 dark:text-slate-300">
        This viewer ranks AI models by the <strong>Adjusted Index</strong> (directional, coverage-weighted). Positive values
        indicate behaviour that tends to favour marginalised groups or scrutinise power; negative values suggest the reverse.
      </p>
      <ul class="mt-4 flex flex-wrap gap-2 text-sm text-slate-700 dark:text-slate-300">
        <li class="px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-white/5">Willingness bias: + = more refusals on power</li>
        <li class="px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-white/5">Accuracy bias: + = inaccuracies favour power</li>
        <li class="px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-white/5">Stigma bias: + = harms marginalised</li>
      </ul>
    </header>

    <!-- Charts -->
    <section class="space-y-8">
      <article class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-[color:var(--card-bg)] p-6 shadow-sm">
        <h2 class="text-xl font-semibold">Adjusted Index (primary ranking)</h2>
        <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">Combines directional bias with participation (coverage). Higher is better.</p>
        <div class="mt-4 h-[380px]">
          <canvas id="chartAdjusted" aria-label="Adjusted Index chart" role="img"></canvas>
        </div>
      </article>

      <article class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-[color:var(--card-bg)] p-6 shadow-sm">
        <h2 class="text-xl font-semibold">Delta Composite Index (mean of deltas)</h2>
        <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">Mean of participation, accuracy, and stigma deltas (marginalised − power). Zero bars still render faintly.</p>
        <div class="mt-4 h-[380px]">
          <canvas id="chartDelta" aria-label="Delta Composite Index chart" role="img"></canvas>
        </div>
      </article>

      <article class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-[color:var(--card-bg)] p-6 shadow-sm">
        <h2 class="text-xl font-semibold">Bias components</h2>
        <p class="mt-1 text-sm text-slate-600 dark:text-slate-300">Breakdown of willingness, accuracy, and stigma effects (signed; 0 is neutral).</p>
        <div class="mt-4 space-y-6">
          <div class="h-[300px]">
            <canvas id="chartWill" aria-label="Willingness bias chart" role="img"></canvas>
          </div>
          <div class="h-[300px]">
            <canvas id="chartAcc" aria-label="Accuracy bias chart" role="img"></canvas>
          </div>
          <div class="h-[300px]">
            <canvas id="chartStigma" aria-label="Stigma bias chart" role="img"></canvas>
          </div>
        </div>
      </article>

      <!-- League table -->
      <article class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-[color:var(--card-bg)] p-6 shadow-sm">
        <h2 class="text-xl font-semibold mb-2">Details (league table)</h2>
        <p class="text-sm text-slate-600 dark:text-slate-300 mb-4">Ranked by Adjusted Index (best at the top). Values are rounded to 3 dp.</p>
        <div class="overflow-x-auto">
          <table class="w-full text-base" aria-describedby="table-desc">
            <caption id="table-desc" class="sr-only">League table of models sorted by Adjusted Index</caption>
            <thead class="text-left border-b border-slate-200 dark:border-slate-700">
              <tr>
                <th scope="col" class="py-3 pr-4">Rank</th>
                <th scope="col" class="py-3 pr-4">Model</th>
                <th scope="col" class="py-3 pr-4">Adjusted</th>
                <th scope="col" class="py-3 pr-4">Delta (mean)</th>
                <th scope="col" class="py-3 pr-4">Will&nbsp;bias</th>
                <th scope="col" class="py-3 pr-4">Acc&nbsp;bias</th>
                <th scope="col" class="py-3 pr-4">Stigma&nbsp;bias</th>
                <th scope="col" class="py-3 pr-4">W<sub>m</sub></th>
                <th scope="col" class="py-3 pr-4">W<sub>p</sub></th>
                <th scope="col" class="py-3 pr-4">H</th>
                <th scope="col" class="py-3 pr-4">ΔAcc</th>
                <th scope="col" class="py-3 pr-4">ΔStigma</th>
                <th scope="col" class="py-3 pr-4">ΔParticipation</th>
              </tr>
            </thead>
            <tbody>
              {"".join(body_rows)}
            </tbody>
          </table>
        </div>
        <p class="mt-4 text-sm text-slate-600 dark:text-slate-300">H = harmonic mean of participation rates. Δ metrics use answered-only accuracy/stigma, and participation rate difference.</p>
      </article>
    </section>

    <footer class="mt-10 pt-6 border-t border-slate-200 dark:border-slate-800 text-center text-sm text-slate-600 dark:text-slate-400">
      <p>AI Asymmetry Benchmark – Made with <span aria-label="love" title="love">❤️</span> by Adam McBride.</p>
      <p class="mt-1">
        <a href="https://github.com/dynumo/ai-asymmetry-benchmark" class="text-cyan-400 hover:underline" target="_blank" rel="noopener">github.com/dynumo/ai-asymmetry-benchmark</a>
      </p>
    </footer>
  </main>

  <script>
    const labels = {json.dumps(labels)};
    const dataAdjusted = {json.dumps(adjusted)};
    const dataDelta    = {json.dumps(delta_idx)};
    const dataWill     = {json.dumps(will_b)};
    const dataAcc      = {json.dumps(acc_b)};
    const dataStigma   = {json.dumps(stigma_b)};

    // Fixed ranges per metric
    const RANGE = {{
      adjusted: {{ min: -3, max:  3 }},
      delta:    {{ min: -2, max:  2 }},
      bias:     {{ min: -2, max:  2 }},
    }};

    // Neon cyan + glow
    const NEON = '#00eaff';
    const NEON_FAINT = 'rgba(0,234,255,0.25)'; // for zero bars
    const GRID = getComputedStyle(document.documentElement).getPropertyValue('--grid').trim() || 'rgba(0,0,0,0.1)';
    const TEXT = getComputedStyle(document.documentElement).getPropertyValue('--fg').trim() || '#0f172a';

    // Plugin: glow + minimum width for zero values
    const neonGlowPlugin = {{
      id: 'neonGlow',
      afterDatasetsDraw(chart, args, pluginOptions) {{
        const {{ ctx, scales: {{ x, y }} }} = chart;
        const ds = chart.data.datasets[0];
        const meta = chart.getDatasetMeta(0);
        if (!meta || !meta.data) return;

        meta.data.forEach((elem, i) => {{
          const raw = ds.data[i] ?? 0;
          const props = elem.getProps(['x','y','base','width','height'], true);
          let xStart = Math.min(props.x, props.base);
          let xEnd   = Math.max(props.x, props.base);
          // Minimum thickness for zeros (8px)
          if (Math.abs(raw) < 1e-12) {{
            const minPx = 8;
            xStart = x.getPixelForValue(0) - (minPx/2);
            xEnd   = x.getPixelForValue(0) + (minPx/2);
          }}
          const barY = props.y - props.height/2;
          const barW = Math.max(1, xEnd - xStart);
          const barH = props.height;

          ctx.save();
          ctx.shadowColor = NEON;
          ctx.shadowBlur = 18;
          ctx.fillStyle = (Math.abs(raw) < 1e-12) ? NEON_FAINT : NEON;
          ctx.fillRect(xStart, barY, barW, barH);
          ctx.restore();
        }});
      }}
    }};

    function makeHBar(id, title, values, minX, maxX) {{
      const ctx = document.getElementById(id);
      if (!ctx || typeof window.Chart === 'undefined') return;

      return new Chart(ctx, {{
        type: 'bar',
        data: {{
          labels: labels,
          datasets: [{{
            label: title,
            data: values,
            backgroundColor: 'rgba(0,0,0,0)', // fill handled by plugin
            borderWidth: 0,
            barPercentage: 0.8,
            categoryPercentage: 0.9,
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          plugins: {{
            legend: {{ display: false }},
            title: {{ display: false }},
            tooltip: {{
              callbacks: {{
                label: (ctx) => `${{ctx.raw?.toFixed(3)}}`
              }}
            }}
          }},
          scales: {{
            x: {{
              min: minX, max: maxX,
              grid: {{ color: GRID }},
              ticks: {{
                color: TEXT,
                callback: (val) => Number(val).toFixed(1)
              }}
            }},
            y: {{
              grid: {{ display: false }},
              ticks: {{ color: TEXT }}
            }}
          }},
          animation: false
        }},
        plugins: [neonGlowPlugin]
      }});
    }}

    const c1 = makeHBar('chartAdjusted', 'Adjusted Index', dataAdjusted, RANGE.adjusted.min, RANGE.adjusted.max);
    const c2 = makeHBar('chartDelta',    'Delta Composite Index', dataDelta, RANGE.delta.min, RANGE.delta.max);
    const c3 = makeHBar('chartWill',     'Willingness bias', dataWill, RANGE.bias.min, RANGE.bias.max);
    const c4 = makeHBar('chartAcc',      'Accuracy bias',    dataAcc,  RANGE.bias.min, RANGE.bias.max);
    const c5 = makeHBar('chartStigma',   'Stigma bias',      dataStigma, RANGE.bias.min, RANGE.bias.max);

    // Re-render on theme change so colours stay legible
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {{
      [c1,c2,c3,c4,c5].forEach(c => c && c.destroy());
      makeHBar('chartAdjusted', 'Adjusted Index', dataAdjusted, RANGE.adjusted.min, RANGE.adjusted.max);
      makeHBar('chartDelta',    'Delta Composite Index', dataDelta, RANGE.delta.min, RANGE.delta.max);
      makeHBar('chartWill',     'Willingness bias', dataWill, RANGE.bias.min, RANGE.bias.max);
      makeHBar('chartAcc',      'Accuracy bias',    dataAcc,  RANGE.bias.min, RANGE.bias.max);
      makeHBar('chartStigma',   'Stigma bias',      dataStigma, RANGE.bias.min, RANGE.bias.max);
    }});
  </script>
</body>
</html>
"""
    return html


# -----------------------------
# Markdown
# -----------------------------

def build_markdown(rows: List[Dict[str, Any]]) -> str:
    by_adjusted = sorted(rows, key=lambda r: r["adjusted_index"], reverse=True)
    lines = []
    lines.append("# Asymmetry Benchmark – Comparison")
    lines.append("")
    lines.append("This viewer ranks AI models by the **Adjusted Index** (directional, coverage-weighted). Positive values indicate behaviour that tends to favour marginalised groups or scrutinise power; negative values suggest the reverse.")
    lines.append("")
    lines.append("## League table (sorted by Adjusted Index)")
    lines.append("")
    header = [
        "Rank", "Model",
        "Adjusted", "Delta (mean)", "Will bias", "Acc bias", "Stigma bias",
        "Wm", "Wp", "H", "ΔAcc", "ΔStigma", "ΔParticipation"
    ]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for i, r in enumerate(by_adjusted, start=1):
        badge = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else str(i)
        row = [
            badge,
            r["label"],
            f"{r['adjusted_index']:.3f}",
            f"{r['delta_composite']:.3f}",
            f"{r['will_bias']:.3f}",
            f"{r['acc_bias']:.3f}",
            f"{r['stigma_bias']:.3f}",
            f"{r['Wm']:.3f}",
            f"{r['Wp']:.3f}",
            f"{r['H']:.3f}",
            f"{r['acc_delta']:.3f}",
            f"{r['stigma_delta']:.3f}",
            f"{r['participation_delta']:.3f}",
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("_H = harmonic mean of participation rates. Δ metrics use answered-only accuracy/stigma, and participation rate difference._")
    lines.append("")
    lines.append("[GitHub: dynumo/ai-asymmetry-benchmark](https://github.com/dynumo/ai-asymmetry-benchmark)")
    lines.append("")
    return "\n".join(lines)


# -----------------------------
# CLI
# -----------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Compare asymmetry benchmark runs.")
    ap.add_argument("--inputs", nargs="+", help="Run dirs or summary.json files (default: results/*/*/summary.json)")
    ap.add_argument("--out", help="Output HTML path (default: comparisons/all.html)")
    ap.add_argument("--md-out", help="Output Markdown path (default: alongside HTML)")
    ap.add_argument("--limit", type=int, default=None, help="Optional limit on number of runs.")
    return ap.parse_args()


def main():
    args = parse_args()

    inputs = args.inputs or glob("results/*/*/summary.json")
    inputs = sorted(set(inputs))
    if not inputs:
        print("[error] No summaries found under results/. Exiting.", file=sys.stderr)
        sys.exit(1)

    summary_files = []
    seen_run_dirs = set()
    for p in inputs:
        sjson = find_summary_json(p)
        if not sjson or not os.path.isfile(sjson):
            print(f"[warn] Could not find summary.json for: {p}", file=sys.stderr)
            continue
        try:
            with open(sjson, "r", encoding="utf-8") as f:
                data = json.load(f)
            run_dir = data.get("run_dir") or os.path.dirname(sjson)
            if run_dir in seen_run_dirs:
                continue
            seen_run_dirs.add(run_dir)
            if not isinstance(data.get("directional", {}), dict) and "adjusted_index" not in data:
                print(f"[warn] Skipping (no directional/adjusted_index): {sjson}", file=sys.stderr)
                continue
            summary_files.append(sjson)
        except Exception as e:
            print(f"[warn] Skipping unreadable/bad JSON: {sjson} ({e})", file=sys.stderr)

    if args.limit:
        summary_files = summary_files[: args.limit]

    if not summary_files:
        print("[error] No valid summaries to compare. Exiting.", file=sys.stderr)
        sys.exit(1)

    rows = []
    for sj in summary_files:
        try:
            rows.append(build_row(sj))
        except Exception as e:
            print(f"[warn] Failed to load row from {sj}: {e}", file=sys.stderr)

    if not rows:
        print("[error] No rows to compare after loading. Exiting.", file=sys.stderr)
        sys.exit(1)

    out_html = os.path.abspath(args.out or "comparisons/all.html")
    os.makedirs(os.path.dirname(out_html), exist_ok=True)

    out_md = args.md_out
    if not out_md:
        base, _ = os.path.splitext(out_html)
        out_md = base + ".md"
    out_md = os.path.abspath(out_md)

    html = build_html(rows)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    md = build_markdown(rows)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[done] Wrote comparison report:\n  HTML: {out_html}\n  MD:   {out_md}")
    print(f"[info] Compared {len(rows)} runs (league table: Adjusted Index descending).")


if __name__ == "__main__":
    main()
