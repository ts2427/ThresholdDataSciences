r"""Demo B step 3e (fallback, Tim 2026-11-19): report counts next to national
headcounts for the top 10 resolved employers — an ILLUSTRATION that larger
employers file more reports. Not a rate comparison and not a safety ranking:
headcounts are national (or company-wide), reports cover federal-OSHA
jurisdictions only, and the headcount is one fiscal year (2024) while
reports span 2015–2025. No rates are computed.

Each headcount is parsed from a verbatim quote, and the quote is checked to
appear in the stored filing (data/raw/filings/, see manifest), so no figure
is typed by hand.

    .venv\Scripts\python -m osha_audit.src.headcounts
"""
import html
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pypdf

from osha_audit.src.naive import save_results

ROOT = Path(__file__).resolve().parents[2]
FIL = ROOT / "data/raw/filings"
FIG = ROOT / "results/figures"
INK, MUTED, RULE = "#0F2338", "#51626F", "#C9D1D8"

# employer label (as resolved) -> filing, verbatim quote(s), the phrase(s) to
# parse (summed), scope note
SOURCES = [
    ("U.S. Postal Service", "usps_fy2024_10k.pdf", "U.S. Postal Service, FY2024 Form 10-K",
     ["our workforce consisted of approximately 639,000 employees, substantially all of whom reside in the U.S."],
     ["639,000"], "Total (substantially all U.S.)", "Sept 30, 2024"),
    ("Walmart", "wmt.htm", "Walmart Inc., Form 10-K, fiscal 2025",
     ["approximately 1.6 million associates in the U.S."], ["1.6 million"], "U.S. associates", "Jan 31, 2025"),
    ("UPS", "ups.htm", "United Parcel Service, Inc., Form 10-K, 2024",
     ["of which 406,000 are in the U.S."], ["406,000"], "U.S. employees (excl. temporary seasonal)", "FY2024"),
    ("Lowe's Home Centers, LLC", "low.htm", "Lowe's Companies, Inc., Form 10-K, fiscal 2024",
     ["Lowe's employed approximately 161,000 full-time associates and 109,000 part-time associates, primarily in the United States and India."],
     ["161,000", "109,000"], "Total full- + part-time (mainly U.S.; no U.S. split)", "Jan 31, 2025"),
    ("Publix Super Markets, Inc.", "pub.htm", "Publix Super Markets, Inc., Form 10-K, 2024",
     ["more than 255,000 employees at the end of 2024"], ["255,000"], "Total (stated as 'more than')", "Dec 28, 2024"),
    ("Tyson Foods, Inc.", "tsn.htm", "Tyson Foods, Inc., Form 10-K, fiscal 2024",
     ["Approximately 120,000 team members were employed in the United States"], ["120,000"],
     "U.S. team members (all Tyson entities)", "Sept 28, 2024"),
    ("Kroger", "kr.htm", "The Kroger Co., Form 10-K, fiscal 2024",
     ["Kroger employed over 409,000 full- and part-time employees."], ["409,000"], "Total (stated as 'over')", "Feb 1, 2025"),
    ("Target Corporation", "tgt.htm", "Target Corporation, Form 10-K, fiscal 2024",
     ["we employed approximately 440,000 full-time, part-time, and seasonal team members."], ["440,000"],
     "Total incl. seasonal", "Feb 1, 2025"),
    ("Walt Disney Parks and Resorts U.S., Inc.", "dis.htm", "The Walt Disney Company, Form 10-K, fiscal 2024",
     ["approximately 171,000 were employed in the U.S."], ["171,000"],
     "Disney company-wide U.S. — NO parks figure is published; not comparable", "Sept 28, 2024"),
    ("American Airlines", "aal.htm", "American Airlines Group Inc., Form 10-K, 2024",
     ["we had approximately 133,300 active full-time equivalent employees"], ["133,300"],
     "Group total, full-time equivalents", "Dec 31, 2024"),
]


def parse_count(phrase):
    """'1.6 million' -> 1600000; '639,000' -> 639000."""
    m = re.fullmatch(r"([\d.,]+)\s*(million)?", phrase.strip())
    if not m:
        raise ValueError(f"cannot parse {phrase!r}")
    v = float(m.group(1).replace(",", ""))
    return int(round(v * 1_000_000)) if m.group(2) else int(v)


def filing_text(path):
    if path.suffix == ".pdf":
        t = "".join(p.extract_text() or "" for p in pypdf.PdfReader(path).pages[:60])
    else:
        t = html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8", errors="replace")))
    t = t.replace("’", "'").replace("‘", "'")     # curly apostrophes in filings
    return re.sub(r"\s+", " ", t.replace("\xa0", " "))


def headcount_table():
    rows = []
    for label, f, source, quotes, phrases, scope, as_of in SOURCES:
        text = filing_text(FIL / f)
        for q in quotes:
            if q not in text:
                raise ValueError(f"quote not found in {f}: {q[:60]}")
        for ph in phrases:
            if not any(ph in q for q in quotes):
                raise ValueError(f"phrase {ph!r} not inside the quote for {label}")
        rows.append({"employer": label, "headcount": sum(parse_count(p) for p in phrases),
                     "scope": scope, "as_of": as_of, "source": source, "quote": " … ".join(quotes),
                     "comparable": "parks figure is published" not in scope and "NO parks" not in scope})
    return pd.DataFrame(rows)


def main():
    res = pd.read_csv(ROOT / "data/interim/osha_resolved.csv", dtype=str, keep_default_na=False)
    g = res.groupby("employer_label")
    rep = pd.DataFrame({"reports": g.size(),
                        "federalstate0_reports": g.FederalState.agg(lambda s: int((s == "0").sum()))})
    top10 = rep.sort_values("reports", ascending=False).head(10)
    hc = headcount_table()
    if set(hc.employer) != set(top10.index):
        raise ValueError(f"headcount list does not match top 10: {set(top10.index) ^ set(hc.employer)}")
    t = hc.merge(top10, left_on="employer", right_index=True).sort_values("reports", ascending=False)
    t["reports_excl_federalstate0"] = t.reports - t.federalstate0_reports
    FIG.mkdir(parents=True, exist_ok=True)
    t.drop(columns="quote").to_csv(FIG / "b_headcount_illustration.csv", index=False)
    plot(t, FIG / "b_headcount_illustration.png")
    save_results("step3e_headcounts", {
        "table": t.to_dict(orient="records"),
        "caveats": ["headcounts are national or company-wide; reports cover federal-OSHA jurisdictions only",
                    "headcount is one fiscal year (2024); reports span 2015-2025",
                    "not a rate comparison and not a safety ranking; no rates computed",
                    "Disney: no parks headcount is published; company-wide U.S. figure shown, not comparable",
                    "American Airlines figure is full-time equivalents; others are people"]})
    return t


def plot(t, path):
    c = t[t.comparable]
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.grid(color=RULE, linewidth=0.8); ax.set_axisbelow(True)
    ax.scatter(c.headcount / 1000, c.reports, color=INK, s=28, zorder=3)
    for r in c.itertuples():
        ax.annotate(r.employer.replace(", Inc.", "").replace(", LLC", "").replace(" Corporation", ""),
                    (r.headcount / 1000, r.reports), xytext=(5, 4), textcoords="offset points",
                    fontsize=7.8, color=INK)
    ax.set_xscale("log"); ax.set_yscale("log")
    from matplotlib.ticker import FuncFormatter, NullFormatter
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        axis.set_minor_formatter(NullFormatter())
    ax.set_xticks([100, 200, 400, 800, 1600]); ax.set_yticks([100, 200, 400, 800, 1600])
    ax.set_xlabel("National or company-wide headcount, fiscal 2024 (thousands, log scale)", color=MUTED, fontsize=9)
    ax.set_ylabel("Severe-injury reports filed, 2015–2025 (log scale)", color=MUTED, fontsize=9)
    ax.set_title("Illustration only: bigger employers tend to file more reports, and industry matters too", color=INK, fontsize=10.5, loc="left")
    fig.text(0.01, 0.01, "Headcounts are national; reports cover federal-OSHA states only. Not a rate "
             "comparison or a safety ranking. Disney omitted (no parks headcount published).",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    t = main()
    print(t.drop(columns=["quote", "source"]).to_string(index=False))
