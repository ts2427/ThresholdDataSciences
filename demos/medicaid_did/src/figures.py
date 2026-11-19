r"""Demo A step 4: figure CSVs and preview PNGs. Every plotted value is read
back from the exported CSV, so the figure and the data file cannot
disagree. Palette from the site (Ink, Muted, Rule; Signal once per chart).

    .venv\Scripts\python -m medicaid_did.src.figures
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "results/figures"
INK, MUTED, RULE, SIGNAL = "#0F2338", "#51626F", "#C9D1D8", "#C7621B"


def export_event_study(results, path):
    """Population-weighted event study, e = -5..5, with 95% pointwise and
    uniform intervals; e = -1 is the reference (0 by construction)."""
    ev = pd.DataFrame(results["step2_main"]["event_study"]["pop"])
    ev = ev[["e", "att", "se", "lo", "hi", "lo_uniform", "hi_uniform"]].copy()
    ev.loc[ev.e == -1, ["lo", "hi", "lo_uniform", "hi_uniform"]] = 0.0
    ev["att"] = ev["att"].fillna(0.0)
    ev.to_csv(path, index=False)
    return ev


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=RULE, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_event_study(csv_path, png_path):
    ev = pd.read_csv(csv_path)
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
    _style(ax)
    ax.axhline(0, color=MUTED, linewidth=0.9)
    ax.axvline(-0.5, color=SIGNAL, linewidth=1.6)          # the single Signal mark
    ax.text(-0.45, ev.hi.max() + 0.3, "expansion takes effect", color=SIGNAL, fontsize=8.5, va="bottom")
    ax.vlines(ev.e, ev.lo, ev.hi, color=INK, linewidth=1.6)
    ax.plot(ev.e, ev.att, "o", color=INK, markersize=5.5)
    ref = ev[ev.e == -1]
    ax.plot(ref.e, ref.att, "o", mfc="white", mec=INK, markersize=5.5)
    ax.set_xticks(ev.e)
    ax.set_xlabel("Years relative to expansion (−1 = reference year)", color=MUTED, fontsize=9)
    ax.set_ylabel("Change in uninsured rate (percentage points)", color=MUTED, fontsize=9)
    ax.set_title("Uninsured rate among low-income adults, expansion vs. comparison states",
                 color=INK, fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)


def plot_naive_vs_careful(yearly_csv, bars_csv, png_path, n_treated, n_comparison):
    y = pd.read_csv(yearly_csv)
    b = pd.read_csv(bars_csv)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.4), dpi=150,
                                 gridspec_kw={"width_ratios": [1.05, 1]})
    for ax in (a1, a2):
        _style(ax)
    for grp, color, label in (("treated", INK, f"Expanded in 2014 ({n_treated} states)"),
                              ("comparison", MUTED, f"Not expanded through 2019 ({n_comparison} states)")):
        s = y[y.group == grp]
        a1.plot(s.year, s.rate_pct, "-o", color=color, markersize=3.5, linewidth=1.6, label=label)
    a1.axvline(2013.5, color=SIGNAL, linewidth=1.6)
    a1.set_ylim(0, None)
    a1.set_ylabel("Uninsured, adults 19–64 under 138% FPL (%)", color=MUTED, fontsize=9)
    a1.legend(frameon=False, fontsize=8.5, labelcolor=INK, loc="lower right")
    a1.set_title("Both groups fell after 2013", color=INK, fontsize=10.5, loc="left")
    labels = ["Before vs. after,\nno comparison", "Comparison states'\nown change", "Before vs. after,\nnet of comparison"]
    ys = list(range(len(b)))[::-1]                 # first row on top
    colors = [MUTED, RULE, INK]
    a2.barh(ys, b.pp, color=colors, height=0.55)
    a2.errorbar(b.pp, ys, xerr=[b.pp - b.lo, b.hi - b.pp], fmt="none", ecolor=INK,
                capsize=4, linewidth=1.1)
    for yv, v, lo, hi in zip(ys, b.pp, b.lo, b.hi):
        a2.text(lo - 0.6, yv, f"{v:.1f}  ({lo:.1f} to {hi:.1f})", ha="right", va="center",
                color=INK, fontsize=8.5)
    a2.axvline(0, color=MUTED, linewidth=0.9)
    a2.set_yticks(ys)
    a2.set_yticklabels(labels, fontsize=8.5, color=MUTED)
    a2.set_xlim(b.lo.min() - 13, 1)
    a2.grid(axis="y", visible=False)
    a2.grid(axis="x", color=RULE, linewidth=0.8)
    a2.set_xlabel("Change, 2013 to 2016–19 average (percentage points)", color=MUTED, fontsize=9)
    ratio = b.pp.iloc[0] / b.pp.iloc[2]
    a2.set_title(f"No comparison group: {ratio:.1f}× too large", color=INK, fontsize=10.5, loc="left")
    fig.tight_layout()
    fig.savefig(png_path)
    plt.close(fig)


def main():
    res = json.loads((ROOT / "results/medicaid_did.json").read_text(encoding="utf-8"))
    FIG.mkdir(parents=True, exist_ok=True)
    export_event_study(res, FIG / "a_event_study.csv")
    plot_event_study(FIG / "a_event_study.csv", FIG / "a_event_study.png")
    nvc = res["naive_vs_careful"]
    plot_naive_vs_careful(FIG / "a_before_after_yearly.csv", FIG / "a_naive_vs_careful.csv",
                          FIG / "a_naive_vs_careful.png", nvc["treated_states"], nvc["comparison_states"])
    # TWFE vs CS table (not a figure)
    m = res["step2_main"]
    pd.DataFrame([
        {"estimator": "Naive two-way fixed effects", "weights": "population", **{k: m["twfe"]["pop"][k] for k in ("att", "lo", "hi")}},
        {"estimator": "Naive two-way fixed effects", "weights": "equal", **{k: m["twfe"]["equal"][k] for k in ("att", "lo", "hi")}},
        {"estimator": "Callaway–Sant'Anna", "weights": "population", **{k: m["headline"][k] for k in ("att", "lo", "hi")}},
        {"estimator": "Callaway–Sant'Anna", "weights": "equal", **{k: m["equal_weights"][k] for k in ("att", "lo", "hi")}},
    ]).to_csv(FIG / "a_twfe_vs_cs_table.csv", index=False)


if __name__ == "__main__":
    main()
