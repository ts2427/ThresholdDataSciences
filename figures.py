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
    vertical = fig.get("vertical_labels")  # optional: names read downward (long category lists)
    if vertical:
        extra = 7 * max(len(str(r[xcol])) for r in rows)
        H, BOT = H + extra, BOT + extra
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
        if vertical:
            y0 = H - BOT + 10
            p.append(_text(x, y0, r[xcol], 11, "start", fill=MUTED).replace(
                "<text ", f'<text transform="rotate(90 {x:g} {y0:g})" ', 1))
        else:
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

def data_table(rows, columns=None):
    heads = columns or list(rows[0].keys())
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
    if fig.get("description"):   # optional text description (new chart types)
        parts.append(f'<span class="fig-caption">{esc(fig["description"])}</span>')
    if src:
        parts.append(f'<span class="fig-source">Source: {src}</span>')
    parts.append("</figcaption>")
    table_rows = rows
    if fig.get("table_where"):   # optional: e.g. only the county rows of a map
        col, val = fig["table_where"]
        table_rows = [r for r in rows if r.get(col) == val]
    parts.append('<details class="fig-data"><summary>View data table'
                 "</summary>" + data_table(table_rows, fig.get("table_columns"))
                 + "</details>")
    if fig.get("data_public"):
        parts.append(f'<p class="fig-download"><a href="/static/data/'
                     f'{esc(fig["data"])}" download>Download the data '
                     "(CSV)</a></p>")
    parts.append("</figure>")
    return "".join(parts)



# ======================================================================
# Chart types added for "When the Network Goes Dark" (2026-11-22).
# Appended only: nothing above this line changed, and every Medicaid and
# OSHA figure is snapshot-tested (tests/test_existing_figures_unchanged.py).
# Data in Ink and Slate; Signal only for highlights (rule-period markers,
# a storm track). Each SVG carries <title> and <desc>; render_figure adds
# the data table.
# ======================================================================

SLATE = "#2E5A88"
PAPER = "#FFFFFF"


def _svg_open_described(w, h, fig):
    """Like _svg_open, plus <title> and <desc> referenced by aria-labelledby."""
    fid = esc(fig["id"])
    desc = fig.get("description") or fig.get("caption") or fig["title"]
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img" '
            f'aria-labelledby="{fid}-t {fid}-d" class="chart-svg">'
            f'<title id="{fid}-t">{esc(fig["title"])}</title><desc id="{fid}-d">{esc(desc)}</desc>')


def _ink_shade(v, vmax, floor=0.08):
    """Sequential single-hue fill: Ink at an opacity that rises with the value."""
    a = floor + (1 - floor) * max(0.0, min(1.0, v / vmax)) if vmax else floor
    return f'fill="{INK}" fill-opacity="{a:.3f}"'


def _legend_ticks(vmax, n=4):
    """Ticks for a shade legend, ending at the maximum itself."""
    t = _ticks(vmax, n)
    return t if abs(t[-1] - vmax) < 1e-9 else t + [round(vmax, 1)]


def _clip_segment(x0, y0, x1, y1, w, h):
    """Liang-Barsky: the part of a segment inside [0, w] x [0, h], or None."""
    t0, t1, dx, dy = 0.0, 1.0, x1 - x0, y1 - y0
    for p, q in ((-dx, x0), (dx, w - x0), (-dy, y0), (dy, h - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy


def _ticks(vmax, n=4):
    if vmax <= 0:
        return [0]
    raw = vmax / n
    mag = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 1
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    out, t = [], 0.0
    while t <= vmax + 1e-9:
        out.append(round(t, 6))
        t += step
    return out


# ------------------------------------------------------------- multiples ----

def multiples_chart(fig, rows):
    """Small multiples: one panel per value of fig['panel'], each with up to two
    line series (fig['series'] column; the first listed in fig['series_order'] is
    Ink and solid, the second Slate and dashed) and an optional band (fig['lo'],
    fig['hi']) drawn for the first series. A Signal rule and label mark the first
    panel of each new value of fig['group'] (e.g. a rule period)."""
    pcol, xcol, ycol, scol = fig["panel"], fig["x"], fig["y"], fig["series"]
    order = fig["series_order"]
    lo, hi, gcol = fig.get("lo"), fig.get("hi"), fig.get("group")
    panels = list(dict.fromkeys(r[pcol] for r in rows))
    groups = {r[pcol]: r.get(gcol, "") for r in rows} if gcol else {}
    xs = [_num(r[xcol]) for r in rows]
    xmin, xmax = min(xs), max(xs)
    ymax = float(fig.get("y_max") or max(_num(r[ycol]) for r in rows))
    cols = int(fig.get("columns", 4))
    W, PW, PH, GAP, TOP, LEG = 720, 0, 104, 46, 30, 30
    PW = (W - 20 - (cols - 1) * 16) / cols
    nrows = -(-len(panels) // cols)
    H = TOP + LEG + nrows * (PH + GAP) + 20
    p = [_svg_open_described(W, H, fig)]
    # legend
    lx = 10
    for i, s in enumerate(order):
        dash = ' stroke-dasharray="5 3"' if i == 1 else ""
        colr = INK if i == 0 else SLATE
        p.append(f'<line x1="{lx}" y1="{TOP - 12}" x2="{lx + 22}" y2="{TOP - 12}" stroke="{colr}" stroke-width="2.5"{dash}/>')
        label = fig.get("series_labels", {}).get(s, s)
        p.append(_text(lx + 28, TOP - 8, label, 11, fill=MUTED))
        lx += 34 + 7 * len(label)
    if lo and hi:
        p.append(f'<rect x="{lx}" y="{TOP - 18}" width="22" height="10" fill="{INK}" fill-opacity="0.12"/>')
        p.append(_text(lx + 28, TOP - 8, fig.get("band_label", "95% interval"), 11, fill=MUTED))
    seen_group = None
    for k, name in enumerate(panels):
        cx = 10 + (k % cols) * (PW + 16)
        cy = TOP + LEG + (k // cols) * (PH + GAP)

        def X(v):
            return cx + PW * ((v - xmin) / ((xmax - xmin) or 1))

        def Y(v):
            return cy + PH - PH * max(0.0, min(1.0, v / ymax))
        g = groups.get(name, "")
        if gcol and g != seen_group:
            if seen_group is not None:
                p.append(f'<line x1="{cx - 8:g}" y1="{cy - 22:g}" x2="{cx - 8:g}" y2="{cy + PH:g}" stroke="{SIGNAL}" stroke-width="2"/>')
            p.append(_text(cx + PW, cy - 6, str(g), 10, "end", fill=SIGNAL, weight="600"))
            seen_group = g
        p.append(f'<rect x="{cx:g}" y="{cy:g}" width="{PW:g}" height="{PH}" fill="none" stroke="{RULE}" stroke-width="1"/>')
        ticks = _ticks(ymax, 2)
        for t in ticks:
            p.append(f'<line x1="{cx:g}" y1="{Y(t):g}" x2="{cx + PW:g}" y2="{Y(t):g}" stroke="{RULE}" stroke-width="0.6"/>')
            if t != ticks[-1] or Y(t) > cy + 12:  # keep the top label clear of the panel title
                p.append(_text(cx + 2, Y(t) - 2, _fmt(t), 9, fill=MUTED))
        p.append(_text(cx, cy - 6, name, 11, weight="500"))
        pr = [r for r in rows if r[pcol] == name]
        if lo and hi:
            band = [r for r in pr if r[scol] == order[0] and r.get(lo, "") != "" and r.get(hi, "") != ""]
            if len(band) > 1:
                up = " ".join(f"{X(_num(r[xcol])):g},{Y(_num(r[hi])):g}" for r in band)
                dn = " ".join(f"{X(_num(r[xcol])):g},{Y(_num(r[lo])):g}" for r in reversed(band))
                p.append(f'<polygon points="{up} {dn}" fill="{INK}" fill-opacity="0.12" stroke="none"/>')
        for i, s in enumerate(order):
            pts = [r for r in pr if r[scol] == s and r[ycol] != ""]
            if not pts:
                continue
            colr = INK if i == 0 else SLATE
            dash = ' stroke-dasharray="5 3"' if i == 1 else ""
            d = " ".join(f"{'M' if j == 0 else 'L'}{X(_num(r[xcol])):g} {Y(_num(r[ycol])):g}" for j, r in enumerate(pts))
            p.append(f'<path d="{d}" fill="none" stroke="{colr}" stroke-width="2"{dash}/>')
            for r in pts:
                p.append(f'<circle cx="{X(_num(r[xcol])):g}" cy="{Y(_num(r[ycol])):g}" r="2" fill="{colr}"/>')
        p.append(_text(cx, cy + PH + 12, str(int(round(xmin))), 9, fill=MUTED))
        p.append(_text(cx + PW, cy + PH + 12, str(int(round(xmax))), 9, "end", fill=MUTED))
    if fig.get("x_label"):
        p.append(_text(W / 2, H - 6, fig["x_label"], 11, "middle", fill=MUTED))
    p.append("</svg>")
    return "".join(p)


# --------------------------------------------------------------- heatmap ----

def heatmap_chart(fig, rows):
    """Rows (fig['row']) by columns (fig['col'], numeric), each cell shaded in Ink
    by fig['value']; a missing cell is left blank (no report). A row whose value
    is blank marks a report that exists but is not used: drawn with a cross and,
    if fig['excluded_label'] is set, a legend entry. A row with a non-blank
    fig['flag'] column is shaded as usual and outlined (dashed Ink), with a
    second legend line, fig['flag_label']. A Signal rule and label mark
    where fig['group'] changes between rows (e.g. a rule period)."""
    rcol, ccol, vcol, gcol = fig["row"], fig["col"], fig["value"], fig.get("group")
    names = list(dict.fromkeys(r[rcol] for r in rows))
    cvals = sorted({int(_num(r[ccol])) for r in rows})
    c0, c1 = min(cvals), max(cvals)
    ncol = c1 - c0 + 1
    vmax = float(fig.get("value_max") or max(_num(r[vcol]) for r in rows if r[vcol] != ""))
    floor = 0.18  # lightest shade, kept clear of the blank (no report) cells
    W, LM, TOP, RH = 720, 96, 40, 18
    CW = (W - LM - 70) / ncol
    H = TOP + RH * len(names) + 64
    cell = {(r[rcol], int(_num(r[ccol]))): _num(r[vcol]) for r in rows if r[vcol] != ""}
    marked = {(r[rcol], int(_num(r[ccol]))) for r in rows if r[vcol] == ""}
    fcol = fig.get("flag")
    flagged = {(r[rcol], int(_num(r[ccol]))) for r in rows if fcol and r.get(fcol, "") not in ("", None)}
    if flagged:
        H += 20
    group = {r[rcol]: r.get(gcol, "") for r in rows} if gcol else {}
    p = [_svg_open_described(W, H, fig)]
    for c in range(c0, c1 + 1):
        if (c - c0) % max(1, ncol // 12) == 0:
            x = LM + (c - c0 + 0.5) * CW
            p.append(_text(x, TOP - 8, str(c), 9, "middle", fill=MUTED))
    prev = None
    for i, name in enumerate(names):
        y = TOP + i * RH
        g = group.get(name, "")
        if gcol and prev is not None and g != prev:
            p.append(f'<line x1="4" y1="{y:g}" x2="{LM + ncol * CW + 4:g}" y2="{y:g}" stroke="{SIGNAL}" stroke-width="2"/>')
            p.append(_text(LM + ncol * CW + 8, y + 12, str(g), 10, fill=SIGNAL, weight="600"))
        if gcol and prev is None:
            p.append(_text(LM + ncol * CW + 8, y + 12, str(g), 10, fill=SIGNAL, weight="600"))
        prev = g
        p.append(_text(LM - 6, y + RH * 0.7, name, 10, "end"))
        for c in range(c0, c1 + 1):
            x = LM + (c - c0) * CW
            if (name, c) in cell:
                p.append(f'<rect x="{x:g}" y="{y + 1:g}" width="{CW - 1:g}" height="{RH - 2}" '
                         f'{_ink_shade(cell[(name, c)], vmax, floor)}/>')
                if (name, c) in flagged:
                    p.append(f'<rect x="{x + 0.8:g}" y="{y + 1.8:g}" width="{CW - 2.6:g}" height="{RH - 3.6:g}" '
                             f'fill="none" stroke="{INK}" stroke-width="1.6" stroke-dasharray="2.5 1.5"/>')
            elif (name, c) in marked:
                p.append(f'<rect x="{x:g}" y="{y + 1:g}" width="{CW - 1:g}" height="{RH - 2}" fill="none" '
                         f'stroke="{MUTED}" stroke-width="0.8"/>')
                p.append(f'<path d="M{x + 2:g} {y + 3:g} L{x + CW - 3:g} {y + RH - 3:g} M{x + CW - 3:g} {y + 3:g} '
                         f'L{x + 2:g} {y + RH - 3:g}" stroke="{MUTED}" stroke-width="0.8"/>')
            else:
                p.append(f'<rect x="{x:g}" y="{y + 1:g}" width="{CW - 1:g}" height="{RH - 2}" fill="none" '
                         f'stroke="{RULE}" stroke-width="0.5"/>')
    ly = TOP + RH * len(names) + 18
    p.append(_text(LM, ly + 9, fig.get("legend_label", "value"), 10, fill=MUTED))
    ticks = _legend_ticks(vmax, 4)
    for k, t in enumerate(ticks):
        x = LM + 150 + k * 52
        p.append(f'<rect x="{x}" y="{ly}" width="18" height="12" {_ink_shade(t, vmax, floor)}/>')
        p.append(_text(x + 22, ly + 10, _fmt(t), 10, fill=MUTED))
    x = LM + 150 + len(ticks) * 52
    p.append(f'<rect x="{x}" y="{ly}" width="18" height="12" fill="none" stroke="{RULE}" stroke-width="0.8"/>')
    p.append(_text(x + 22, ly + 10, fig.get("blank_label", "no report"), 10, fill=MUTED))
    if marked and fig.get("excluded_label"):
        x += 90
        p.append(f'<rect x="{x}" y="{ly}" width="18" height="12" fill="none" stroke="{MUTED}" stroke-width="0.8"/>')
        p.append(f'<path d="M{x + 2} {ly + 2} L{x + 16} {ly + 10} M{x + 16} {ly + 2} L{x + 2} {ly + 10}" '
                 f'stroke="{MUTED}" stroke-width="0.8"/>')
        p.append(_text(x + 22, ly + 10, fig["excluded_label"], 10, fill=MUTED))
    if flagged and fig.get("flag_label"):
        x, y2 = LM + 150, ly + 20
        p.append(f'<rect x="{x}" y="{y2}" width="18" height="12" {_ink_shade(vmax / 4, vmax, floor)}/>')
        p.append(f'<rect x="{x + 0.8}" y="{y2 + 0.8}" width="16.4" height="10.4" fill="none" stroke="{INK}" '
                 f'stroke-width="1.6" stroke-dasharray="2.5 1.5"/>')
        p.append(_text(x + 22, y2 + 10, fig["flag_label"], 10, fill=MUTED))
    if fig.get("x_label"):
        p.append(_text(LM + ncol * CW / 2, H - 8, fig["x_label"], 11, "middle", fill=MUTED))
    p.append("</svg>")
    return "".join(p)


# ----------------------------------------------------------- calibration ----

def calibration_chart(fig, rows):
    """Predicted (fig['x']) against observed (fig['y']) by bin, with the
    45-degree line where they would be equal."""
    xcol, ycol = fig["x"], fig["y"]
    vmax = float(fig.get("axis_max") or max(max(_num(r[xcol]), _num(r[ycol])) for r in rows))
    W, H, LM, BOT, TOP, RM = 720, 400, 60, 50, 20, 250
    side = min(W - LM - RM, H - BOT - TOP)

    def X(v):
        return LM + side * v / vmax

    def Y(v):
        return TOP + side - side * v / vmax
    p = [_svg_open_described(W, H, fig)]
    for t in _ticks(vmax, 4):
        p.append(f'<line x1="{LM}" y1="{Y(t):g}" x2="{LM + side}" y2="{Y(t):g}" stroke="{RULE}" stroke-width="1"/>')
        p.append(_text(LM - 8, Y(t) + 4, _fmt(t), 11, "end", fill=MUTED))
        p.append(_text(X(t), TOP + side + 16, _fmt(t), 11, "middle", fill=MUTED))
    p.append(f'<line x1="{X(0):g}" y1="{Y(0):g}" x2="{X(vmax):g}" y2="{Y(vmax):g}" stroke="{MUTED}" '
             f'stroke-width="1.2" stroke-dasharray="4 4"/>')
    p.append(_text(X(vmax) + 6, Y(vmax) + 4, fig.get("diagonal_label", "predicted = observed"), 11, fill=MUTED))
    for r in rows:
        p.append(f'<circle cx="{X(_num(r[xcol])):g}" cy="{Y(_num(r[ycol])):g}" r="5" fill="{INK}"/>')
    p.append(_text(LM + side / 2, H - 10, fig.get("x_label", xcol), 11, "middle", fill=MUTED))
    p.append(_text(14, TOP + side / 2, fig.get("y_label", ycol), 11, "middle", fill=MUTED).replace(
        "<text ", f'<text transform="rotate(-90 14 {TOP + side / 2:g})" ', 1))
    p.append("</svg>")
    return "".join(p)


# ------------------------------------------------------------------- map ----

def map_chart(fig, rows):
    """A choropleth from pre-projected shapes: rows with kind 'area' carry an SVG
    path (fig['path']) and an optional value (fig['value']; blank = no data,
    drawn in Rule); rows with kind 'track' are points (fig['tx'], fig['ty'])
    joined in order into a Signal line (e.g. a storm track), clipped to the map
    frame; its label sits where the line enters the frame."""
    W, H = int(fig.get("width", 720)), int(fig.get("height", 460))
    vmax = float(fig.get("value_max") or max(_num(r[fig["value"]]) for r in rows
                                             if r.get("kind") == "area" and r[fig["value"]] != ""))
    p = [_svg_open_described(W, H + 40, fig)]
    for r in rows:
        if r.get("kind") != "area":
            continue
        v = r[fig["value"]]
        if v != "":
            p.append(f'<path d="{r[fig["path"]]}" {_ink_shade(_num(v), vmax)} stroke="{PAPER}" stroke-width="0.6"/>')
        else:  # not in the data: white with a Rule outline, distinct from the lightest shade
            p.append(f'<path d="{r[fig["path"]]}" fill="{PAPER}" stroke="{RULE}" stroke-width="0.6"/>')
    track = [(_num(r[fig["tx"]]), _num(r[fig["ty"]])) for r in rows if r.get("kind") == "track"]
    segs = [s for s in (_clip_segment(*a, *b, W, H) for a, b in zip(track, track[1:])) if s]
    if segs:
        d = " ".join(f"M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f}" for x0, y0, x1, y1 in segs)
        p.append(f'<path d="{d}" fill="none" stroke="{SIGNAL}" stroke-width="2.5" stroke-linecap="round"/>')
        ex, ey = segs[0][0], segs[0][1]
        p.append(_text(ex + 8, min(ey, H) - 8, fig.get("track_label", "track"), 11, fill=SIGNAL, weight="600"))
    ly = H + 12
    p.append(_text(10, ly + 10, fig.get("legend_label", "value"), 10, fill=MUTED))
    ticks = _legend_ticks(vmax, 4)
    for k, t in enumerate(ticks):
        x = 190 + k * 58
        p.append(f'<rect x="{x}" y="{ly}" width="18" height="12" {_ink_shade(t, vmax)}/>')
        p.append(_text(x + 22, ly + 10, _fmt(t), 10, fill=MUTED))
    x = 190 + len(ticks) * 58
    p.append(f'<rect x="{x}" y="{ly}" width="18" height="12" fill="{PAPER}" stroke="{RULE}" stroke-width="1"/>')
    p.append(_text(x + 22, ly + 10, fig.get("no_data_label", "not reported"), 10, fill=MUTED))
    p.append("</svg>")
    return "".join(p)


RENDERERS.update({"multiples": multiples_chart, "heatmap": heatmap_chart,
                  "calibration": calibration_chart, "map": map_chart})
