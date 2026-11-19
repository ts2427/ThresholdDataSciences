"""Static SVG figure generation for Threshold Data Sciences.

Charts are generated at build time from CSVs committed in content/data/ —
no JavaScript, no plotting library, no external service. SVG is inlined so
it inherits site CSS and prints correctly.

Palette discipline: marks in Ink, gridlines in Rule, labels in the mono
utility face. Signal (#C7621B) appears at most ONCE per chart, only to mark
a threshold, a break, or the single data point the argument turns on —
declared in front matter (`signal:` names the annotation kind), or, for the
timeline type, the phase transition.
"""

import csv
import html
from datetime import datetime
from pathlib import Path

INK = "#0F2338"
RULE = "#C9D1D8"
SIGNAL = "#C7621B"
MUTED = "#51626F"

MONO = "IBM Plex Mono, Consolas, monospace"
SANS = "IBM Plex Sans, Segoe UI, sans-serif"


def esc(s):
    return html.escape(str(s), quote=True)


def load_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"{path.name}: empty CSV")
    return rows


def _num(v):
    return float(v)


def _fmt(v):
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


def _svg_open(w, h, title):
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" '
            f'role="img" aria-label="{esc(title)}" class="chart-svg">')


def _text(x, y, s, size=12, anchor="start", font=MONO, fill=INK, weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x:g}" y="{y:g}" font-family="{font}" '
            f'font-size="{size}" text-anchor="{anchor}" fill="{fill}"{w}>'
            f"{esc(s)}</text>")


# ------------------------------------------------------------------- dot ----

def dot_chart(fig, rows):
    """Rows of group means as large Ink dots on a shared scale, with
    annotation dots from the data (annotation/annotation_value/
    annotation_label columns). fig['signal'] names the annotation kind
    drawn in Signal — the single Signal element."""
    xcol, ycol = fig["x"], fig["y"]
    xmax = _num(rows[0].get("max_score", 10))
    groups, seen = [], set()
    for r in rows:
        if r[xcol] not in seen:
            seen.add(r[xcol])
            groups.append(r[xcol])

    W, LM, RM, TOP, PITCH = 720, 150, 30, 46, 76
    H = TOP + PITCH * len(groups) + 40
    plot_w = W - LM - RM

    def X(v):
        return LM + plot_w * (_num(v) / xmax)

    p = [_svg_open(W, H, fig["title"])]
    # gridlines + scale labels
    step = 2 if xmax <= 12 else max(1, int(xmax // 5))
    v = 0
    while v <= xmax:
        x = X(v)
        p.append(f'<line x1="{x:g}" y1="{TOP - 18}" x2="{x:g}" '
                 f'y2="{H - 34}" stroke="{RULE}" stroke-width="1"/>')
        p.append(_text(x, H - 16, _fmt(v), 11, "middle", fill=MUTED))
        v += step

    for i, g in enumerate(groups):
        y = TOP + PITCH * i + PITCH / 2 - 10
        p.append(_text(LM - 14, y + 4, g, 13, "end", SANS, weight="600"))
        p.append(f'<line x1="{LM}" y1="{y:g}" x2="{W - RM}" y2="{y:g}" '
                 f'stroke="{RULE}" stroke-width="1"/>')
        grows = [r for r in rows if r[xcol] == g]
        mean = grows[0][ycol]
        p.append(f'<circle cx="{X(mean):g}" cy="{y:g}" r="9" fill="{INK}"/>')
        p.append(_text(X(mean), y - 16, _fmt(mean), 12, "middle",
                       weight="500"))
        for r in grows:
            kind = (r.get("annotation") or "").strip()
            if not kind:
                continue
            av = r["annotation_value"]
            color = SIGNAL if kind == fig.get("signal") else INK
            ax = X(av)
            p.append(f'<circle cx="{ax:g}" cy="{y:g}" r="6" fill="none" '
                     f'stroke="{color}" stroke-width="2.5"/>')
            anchor = ("start" if ax < LM + plot_w * 0.25
                      else "end" if ax > LM + plot_w * 0.75 else "middle")
            lx = ax + (10 if anchor == "start" else -10 if anchor == "end" else 0)
            p.append(_text(lx, y + 26, r["annotation_label"], 11, anchor,
                           fill=color if color == SIGNAL else MUTED))
    p.append("</svg>")
    return "".join(p)


# -------------------------------------------------------------- bar (h) -----

def bar_chart(fig, rows):
    """Horizontal bars; optional `group` column renders grouped sections
    with mono headers. Labels sit above their bars (long labels survive
    small screens). Scale is 0-100 for percent data, else 0-max."""
    xcol, ycol, gcol = fig["x"], fig["y"], fig.get("group")
    vmax = 100 if all(_num(r[ycol]) <= 100 for r in rows) else \
        max(_num(r[ycol]) for r in rows)

    W, LM, RM = 720, 30, 60
    plot_w = W - LM - RM
    ROW, GHEAD = 58, 34
    groups = []
    if gcol:
        seen = set()
        for r in rows:
            if r[gcol] not in seen:
                seen.add(r[gcol])
                groups.append(r[gcol])
    H = 20 + (len(groups) * GHEAD if gcol else 0) + ROW * len(rows) + 36

    def X(v):
        return LM + plot_w * (_num(v) / vmax)

    p = [_svg_open(W, H, fig["title"])]
    for gv in (0, 25, 50, 75, 100) if vmax == 100 else ():
        x = X(gv)
        p.append(f'<line x1="{x:g}" y1="14" x2="{x:g}" y2="{H - 30}" '
                 f'stroke="{RULE}" stroke-width="1"/>')
        p.append(_text(x, H - 12, str(gv), 11, "middle", fill=MUTED))

    y = 24
    ordered = groups if gcol else [None]
    for g in ordered:
        if gcol:
            p.append(_text(LM, y + 8, str(g).upper(), 11.5, fill=MUTED,
                           weight="500"))
            y += GHEAD
        for r in [r for r in rows if not gcol or r[gcol] == g]:
            p.append(_text(LM, y + 6, r[xcol], 13, font=SANS))
            bw = X(r[ycol]) - LM
            p.append(f'<rect x="{LM}" y="{y + 14}" width="{bw:g}" '
                     f'height="20" fill="{INK}"/>')
            p.append(_text(X(r[ycol]) + 8, y + 29, _fmt(r[ycol]) + "%"
                           if vmax == 100 else _fmt(r[ycol]), 12,
                           weight="500"))
            y += ROW
    p.append("</svg>")
    return "".join(p)


# ---------------------------------------------------------------- column ----

def column_chart(fig, rows):
    xcol, ycol = fig["x"], fig["y"]
    vmax = max(_num(r[ycol]) for r in rows)
    W, H, LM, BOT = 720, 320, 50, 60
    plot_w, plot_h = W - LM - 20, H - BOT - 30
    n = len(rows)
    bw = min(64, plot_w / n * 0.6)
    p = [_svg_open(W, H, fig["title"])]
    p.append(f'<line x1="{LM}" y1="{H - BOT}" x2="{W - 20}" y2="{H - BOT}" '
             f'stroke="{RULE}" stroke-width="1"/>')
    for i, r in enumerate(rows):
        cx = LM + plot_w * (i + 0.5) / n
        bh = plot_h * _num(r[ycol]) / vmax
        p.append(f'<rect x="{cx - bw / 2:g}" y="{H - BOT - bh:g}" '
                 f'width="{bw:g}" height="{bh:g}" fill="{INK}"/>')
        p.append(_text(cx, H - BOT - bh - 8, _fmt(r[ycol]), 12, "middle",
                       weight="500"))
        p.append(_text(cx, H - BOT + 18, r[xcol], 11, "middle", fill=MUTED))
    p.append("</svg>")
    return "".join(p)


# ------------------------------------------------------------------ line ----

def line_chart(fig, rows):
    xcol, ycol = fig["x"], fig["y"]
    vals = [_num(r[ycol]) for r in rows]
    vmax, vmin = max(vals), min(0, min(vals))
    W, H, LM, BOT = 720, 320, 50, 60
    plot_w, plot_h = W - LM - 20, H - BOT - 30
    n = len(rows)
    pts = []
    for i, v in enumerate(vals):
        x = LM + plot_w * (i / max(1, n - 1))
        y = H - BOT - plot_h * ((v - vmin) / (vmax - vmin or 1))
        pts.append((x, y))
    p = [_svg_open(W, H, fig["title"])]
    p.append(f'<line x1="{LM}" y1="{H - BOT}" x2="{W - 20}" y2="{H - BOT}" '
             f'stroke="{RULE}" stroke-width="1"/>')
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:g} {y:g}"
                    for i, (x, y) in enumerate(pts))
    p.append(f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="2.5"/>')
    for (x, y), r in zip(pts, rows):
        p.append(f'<circle cx="{x:g}" cy="{y:g}" r="4" fill="{INK}"/>')
        p.append(_text(x, H - BOT + 18, r[xcol], 11, "middle", fill=MUTED))
    p.append("</svg>")
    return "".join(p)


# -------------------------------------------------------------- interval ----

def interval_chart(fig, rows):
    """Point estimates with vertical intervals on a shared scale that may
    run below zero (e.g. an event study). Columns: x (category), y
    (estimate), and fig['lo'] / fig['hi'] (interval bounds). A dashed zero
    line in Rule; fig['signal_before'] names the x value before which a
    vertical marker is drawn in Signal (the chart's single Signal
    element, e.g. where a policy takes effect)."""
    xcol, ycol, lo, hi = fig["x"], fig["y"], fig["lo"], fig["hi"]
    vals = [_num(r[c]) for r in rows for c in (ycol, lo, hi)]
    vmin, vmax = min(0.0, min(vals)), max(0.0, max(vals))
    span = (vmax - vmin) or 1.0
    W, H, LM, BOT, TOP = 720, 340, 56, 52, 24
    plot_w, plot_h = W - LM - 20, H - BOT - TOP
    n = len(rows)

    def X(i):
        return LM + plot_w * (i + 0.5) / n

    def Y(v):
        return TOP + plot_h * (vmax - v) / span

    p = [_svg_open(W, H, fig["title"])]
    step = 2 if span <= 16 else 5
    t = step * (int(vmin // step))
    while t <= vmax + 1e-9:
        p.append(f'<line x1="{LM}" y1="{Y(t):g}" x2="{W - 20}" y2="{Y(t):g}" '
                 f'stroke="{RULE}" stroke-width="1"/>')
        p.append(_text(LM - 8, Y(t) + 4, _fmt(t), 11, "end", fill=MUTED))
        t += step
    p.append(f'<line x1="{LM}" y1="{Y(0):g}" x2="{W - 20}" y2="{Y(0):g}" '
             f'stroke="{MUTED}" stroke-width="1.2"/>')
    sb = fig.get("signal_before")
    for i, r in enumerate(rows):
        if sb is not None and str(r[xcol]) == str(sb):
            x = X(i) - plot_w / n / 2
            p.append(f'<line x1="{x:g}" y1="{TOP - 6}" x2="{x:g}" y2="{H - BOT}" '
                     f'stroke="{SIGNAL}" stroke-width="2"/>')
        x = X(i)
        p.append(f'<line x1="{x:g}" y1="{Y(_num(r[lo])):g}" x2="{x:g}" '
                 f'y2="{Y(_num(r[hi])):g}" stroke="{INK}" stroke-width="2"/>')
        p.append(f'<circle cx="{x:g}" cy="{Y(_num(r[ycol])):g}" r="4.5" fill="{INK}"/>')
        p.append(_text(x, H - BOT + 18, r[xcol], 11, "middle", fill=MUTED))
    if fig.get("x_label"):
        p.append(_text(LM + plot_w / 2, H - 10, fig["x_label"], 11, "middle", fill=MUTED))
    p.append("</svg>")
    return "".join(p)


# ------------------------------------------------------------- waterfall ----

def wrap_label(text, width=12):
    """Greedy word wrap for axis labels: lines of at most `width`
    characters (a single longer word stays on its own line)."""
    lines, cur = [], ""
    for w in str(text).split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def waterfall_rows(rows, xcol, ycol, kcol="kind"):
    """Bar geometry for a bridge chart. Rows have kind 'start', 'step' or
    'end'. 'start'/'end' values are levels; 'step' values are signed
    changes. Returns [(label, bottom, top, value, kind)]. Raises if the end
    level does not equal start + the sum of the steps."""
    out, level = [], None
    for r in rows:
        kind, v = r[kcol], _num(r[ycol])
        if kind == "start":
            level = v
            out.append((r[xcol], 0.0, v, v, kind))
        elif kind == "step":
            if level is None:
                raise ValueError("waterfall: a step comes before the start bar")
            new = level + v
            out.append((r[xcol], min(level, new), max(level, new), v, kind))
            level = new
        elif kind == "end":
            if level is None or abs(level - v) > 1e-6:
                raise ValueError(f"waterfall: end {v} != start + steps {level}")
            out.append((r[xcol], 0.0, v, v, kind))
        else:
            raise ValueError(f"waterfall: unknown kind {kind!r}")
    return out


def waterfall_chart(fig, rows):
    """Bridge chart: a start bar, floating bars for each signed step, an end
    bar. Levels in Ink, steps in Muted; every bar labeled with its value
    (steps with their sign). No Signal element."""
    bars = waterfall_rows(rows, fig["x"], fig["y"], fig.get("kind", "kind"))
    top = max(b[2] for b in bars)
    W, H, LM, BOT, TOP = 720, 340, 20, 64, 30
    plot_w, plot_h = W - LM - 20, H - BOT - TOP
    n = len(bars)
    bw = min(70, plot_w / n * 0.62)

    def Y(v):
        return TOP + plot_h * (1 - v / top)

    p = [_svg_open(W, H, fig["title"])]
    p.append(f'<line x1="{LM}" y1="{Y(0):g}" x2="{W - 20}" y2="{Y(0):g}" '
             f'stroke="{RULE}" stroke-width="1"/>')
    prev_level_y = None
    for i, (label, lo, hi, v, kind) in enumerate(bars):
        cx = LM + plot_w * (i + 0.5) / n
        h = max(Y(lo) - Y(hi), 1.5)          # keep tiny steps visible
        color = INK if kind in ("start", "end") else MUTED
        p.append(f'<rect x="{cx - bw / 2:g}" y="{Y(hi):g}" width="{bw:g}" '
                 f'height="{h:g}" fill="{color}"/>')
        text = (f"{v:+,.0f}".replace("-", "−") if kind == "step" else f"{v:,.0f}")
        p.append(_text(cx, Y(hi) - 8, text, 12, "middle", weight="500"))
        if prev_level_y is not None:
            p.append(f'<line x1="{cx - plot_w / n + bw / 2:g}" y1="{prev_level_y:g}" '
                     f'x2="{cx - bw / 2:g}" y2="{prev_level_y:g}" stroke="{MUTED}" '
                     f'stroke-width="1" stroke-dasharray="3 3"/>')
        level = hi if kind == "start" or (kind == "step" and v > 0) else lo
        prev_level_y = Y(level) if kind != "end" else None
        for k, line in enumerate(wrap_label(label)):
            p.append(_text(cx, H - BOT + 18 + 14 * k, line, 11, "middle", fill=MUTED))
    p.append("</svg>")
    return "".join(p)


# -------------------------------------------------------------- timeline ----

def timeline_chart(fig, rows):
    """Dated milestones on a horizontal axis rendered as a step function:
    the line runs low through the first phase and steps up where the phase
    changes; the riser is the chart's single Signal element."""
    dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in rows]
    t0, t1 = min(dates), max(dates)
    span = (t1 - t0).days or 1

    W, H, LM, RM = 760, 300, 40, 40
    plot_w = W - LM - RM
    Y_LOW, Y_HIGH = 190, 120

    def X(d):
        return LM + plot_w * ((d - t0).days / span)

    # phase transition = first row whose phase differs from the first phase
    first_phase = rows[0]["phase"]
    trans_x = None
    for r, d in zip(rows, dates):
        if r["phase"] != first_phase:
            trans_x = X(d)
            break

    p = [_svg_open(W, H, fig["title"])]
    if trans_x is None:
        p.append(f'<line x1="{LM}" y1="{Y_LOW}" x2="{W - RM}" y2="{Y_LOW}" '
                 f'stroke="{INK}" stroke-width="3"/>')
    else:
        p.append(f'<line x1="{LM}" y1="{Y_LOW}" x2="{trans_x:g}" '
                 f'y2="{Y_LOW}" stroke="{INK}" stroke-width="3"/>')
        p.append(f'<line x1="{trans_x:g}" y1="{Y_LOW}" x2="{trans_x:g}" '
                 f'y2="{Y_HIGH}" stroke="{SIGNAL}" stroke-width="3"/>')
        p.append(f'<line x1="{trans_x:g}" y1="{Y_HIGH}" x2="{W - RM}" '
                 f'y2="{Y_HIGH}" stroke="{INK}" stroke-width="3"/>')

    # milestone markers with staggered labels (leader lines avoid overlap)
    offsets = [-58, 64, -96, 100]
    for i, (r, d) in enumerate(zip(rows, dates)):
        x = X(d)
        y_line = Y_LOW if trans_x is None or x < trans_x else Y_HIGH
        p.append(f'<circle cx="{x:g}" cy="{y_line}" r="5" fill="{INK}"/>')
        off = offsets[i % len(offsets)]
        ly = y_line + off
        p.append(f'<line x1="{x:g}" y1="{y_line + (7 if off > 0 else -7)}" '
                 f'x2="{x:g}" y2="{ly + (-12 if off > 0 else 6)}" '
                 f'stroke="{RULE}" stroke-width="1"/>')
        anchor = ("start" if x < LM + plot_w * 0.12
                  else "end" if x > W - RM - plot_w * 0.12 else "middle")
        words, lines, cur = r["milestone"].split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if len(trial) > 26 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        lines.append(cur)
        for j, ln in enumerate(lines):
            p.append(_text(x, ly + j * 14, ln, 11.5, anchor, SANS))
        p.append(_text(x, ly + len(lines) * 14 + 1, d.strftime("%b %Y"),
                       10.5, anchor, fill=MUTED))
    p.append("</svg>")
    return "".join(p)


RENDERERS = {"dot": dot_chart, "bar": bar_chart, "column": column_chart,
             "line": line_chart, "timeline": timeline_chart, "interval": interval_chart,
             "waterfall": waterfall_chart}


# ------------------------------------------------------------- assembly -----

def data_table(rows):
    heads = list(rows[0].keys())
    out = ['<div class="table-scroll"><table>', "<thead><tr>"]
    out += [f"<th>{esc(h)}</th>" for h in heads]
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>" + "".join(f"<td>{esc(r[h])}</td>" for h in heads)
                   + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render_figure(fig, data_dir):
    """Full <figure> HTML: SVG, figcaption (title/caption/source), data
    table in <details>, and a download link when data_public."""
    csv_path = Path(data_dir) / fig["data"]
    rows = load_csv(csv_path)
    svg = RENDERERS[fig["type"]](fig, rows)

    src = esc(fig.get("source", ""))
    if fig.get("source_url"):
        src = f'<a href="{esc(fig["source_url"])}">{src}</a>'
    parts = [f'<figure class="chart" id="{esc(fig["id"])}">', svg,
             "<figcaption>",
             f'<span class="fig-title">{esc(fig["title"])}</span>']
    if fig.get("caption"):
        parts.append(f'<span class="fig-caption">{esc(fig["caption"])}</span>')
    if src:
        parts.append(f'<span class="fig-source">Source: {src}</span>')
    parts.append("</figcaption>")
    parts.append('<details class="fig-data"><summary>View data table'
                 "</summary>" + data_table(rows) + "</details>")
    if fig.get("data_public"):
        parts.append(f'<p class="fig-download"><a href="/static/data/'
                     f'{esc(fig["data"])}" download>Download the data '
                     "(CSV)</a></p>")
    parts.append("</figure>")
    return "".join(parts)
