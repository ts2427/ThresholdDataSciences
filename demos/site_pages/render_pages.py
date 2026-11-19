r"""Render the two demo pages for the site (published: draft: false), with every
number pulled from results/*.json, and copy the figure CSVs into the site's
content/data/. Follows the site's analysis format
(content/analysis/example-analysis.md) and the write-up requirements in
docs/writeup_requirements_demo_a.md and _demo_b.md.

    .venv\Scripts\python -m site_pages.render_pages

Figures: every figure CSV is checked value by value against results/*.json
(site_pages/verify_figures.py); a figure is declared verified: true only if
every value matches, otherwise verified: false and the mismatch is printed.
The demonstration tag comes from the site's analysis template, not the body.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent
ANALYSIS = SITE / "content/analysis"
DATA = SITE / "content/data"
DATE = "2026-11-19"
TAG = "DEMONSTRATION · PUBLIC DATA · NOT CLIENT WORK"


def pp(x, d=1):
    return f"{x:.{d}f}".replace("-", "−")


def ci(lo, hi, d=1):
    return f"{pp(lo, d)} to {pp(hi, d)}"


def sci(x):
    """4.74e7 -> '4.7 × 10⁷' (superscript exponent)."""
    m, e = f"{x:.1e}".split("e")
    sup = str(int(e)).translate(str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹"))
    return f"{m} × 10{sup}"


def n(x):
    return f"{int(round(x)):,}"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


# ------------------------------------------------------------------ Demo A --

def demo_a():
    r = json.loads((ROOT / "results/medicaid_did.json").read_text(encoding="utf-8"))
    m, nvc = r["step2_main"], r["naive_vs_careful"]
    h, eq = m["headline"], m["equal_weights"]
    tw = m["twfe"]
    ev = pd.DataFrame(m["event_study"]["pop"])
    e0 = ev.set_index("e").loc[0, "att"]
    pre = m["pretest"]["pop"]
    allc = m["pretest_investigation"]["all_cells_test"]
    bd = {b["target"]: b["breakdown_Mbar"] for b in m["honestdid_breakdown"]}
    pt, pci = nvc["point"], nvc["ci95"]
    treated = next(x for x in m["robustness"] if x["check"] == "Equal state weights")["treated_states"]
    c2015 = pd.DataFrame(m["pretest_investigation"]["cells"])
    c2015 = c2015[(c2015.group == 2015) & (c2015.z.abs() > 1.96)].sort_values("e")
    cells_2015 = "; ".join(f"e = {int(r.e)}: {pp(r.att)} points (z = {pp(r.z)})" for r in c2015.itertuples())
    bench = m["benchmarks"]
    sec = m["secondary_overall"]

    # figure CSVs (copied from results; values unchanged)
    fe = pd.read_csv(ROOT / "results/figures/a_event_study.csv")
    fe = fe.assign(year_relative_to_expansion=fe.e.astype(int),
                   estimate_pp=fe.att.round(2), ci95_low=fe.lo.round(2), ci95_high=fe.hi.round(2))
    fe[["year_relative_to_expansion", "estimate_pp", "ci95_low", "ci95_high"]].to_csv(
        DATA / "medicaid-event-study.csv", index=False)
    fb = pd.read_csv(ROOT / "results/figures/a_naive_vs_careful.csv")
    fb = pd.DataFrame({"comparison": ["No comparison group", "Comparison states", "Net of comparison"],
                       "decline_pp": (-fb.pp).round(1), "change_pp": fb.pp.round(2),
                       "ci95_low": fb.lo.round(2), "ci95_high": fb.hi.round(2)})
    fb.to_csv(DATA / "medicaid-naive-vs-careful.csv", index=False)

    rob = "\n".join(
        f"| {x['check']}{' (added after seeing results)' if x['added'] != 'pre-specified' else ''} "
        f"| {pp(x['att'])} | {ci(x['lo'], x['hi'])} |" for x in m["robustness"])

    body = f"""---
draft: false
title: "Did Medicaid expansion reduce uninsurance among low-income adults?"
date: {DATE}
updated: {DATE}
summary: "A worked example of a staggered difference-in-differences analysis on public Census data: Medicaid expansion lowered the uninsured rate among adults under 138% of the poverty line by about {pp(-h['att'])} percentage points (95% interval {pp(-h['hi'])} to {pp(-h['lo'])})."
method: >-
  Callaway–Sant'Anna difference-in-differences (R did 2.5.1), states that
  expanded in 2014, 2015, 2016 or 2019 compared with states not yet treated
  and never treated, 2009–2019, doubly robust, weighted by each state's
  low-income adult population, standard errors clustered by state with a
  multiplier bootstrap. The analysis plan, including the headline estimand,
  robustness checks and benchmarks, was written and committed before any
  estimator was run. Sensitivity to pre-trend violations: HonestDiD
  relative-magnitudes bounds.
data_sources:
  - name: "U.S. Census Bureau, American Community Survey 1-year Public Use Microdata Sample, 2009–2019 and 2021–2024 (Census Data API)"
    url: "https://api.census.gov/data/2019/acs/acs1/pums"
  - name: "KFF State Health Facts, Status of State Action on the Medicaid Expansion Decision (November 2026)"
    url: "https://www.kff.org/health-reform/state-indicator/state-activity-around-expanding-medicaid-under-the-affordable-care-act/"
  - name: "U.S. Census Bureau, ACS table C27016 (used to check the microdata, 2017–2019)"
    url: "https://api.census.gov/data/2019/acs/acs1/groups/C27016.html"
download: "/static/data/medicaid-event-study.csv"
figures:
  - id: fig-1
    type: interval
    data: medicaid-event-study.csv
    x: year_relative_to_expansion
    y: estimate_pp
    lo: ci95_low
    hi: ci95_high
    signal_before: 0
    x_label: "Years relative to expansion (−1 = reference year)"
    title: "Uninsurance fell after expansion and kept falling"
    caption: "Change in the uninsured rate among adults 19–64 under 138% of the poverty line, expansion states vs. comparison states, percentage points, with 95% intervals. Year −1 is the reference. Later years rest on fewer states: year 5 is the 2014 states only."
    source: "ACS 1-year PUMS via the Census Data API; expansion dates from KFF."
    source_url: ""
    data_public: true
    verified: VERIFY_medicaid-event-study.csv
  - id: fig-2
    type: column
    data: medicaid-naive-vs-careful.csv
    x: comparison
    y: decline_pp
    title: "Without a comparison group, the effect looks {pt['naive_change'] / pt['adjusted_change']:.1f} times larger"
    caption: "Fall in the uninsured rate, 2013 to the 2016–2019 average, percentage points: the {nvc['treated_states']} states that expanded in 2014; the {nvc['comparison_states']} states that had not expanded by 2019; and the first net of the second. 95% intervals in the data table."
    source: "ACS 1-year PUMS via the Census Data API."
    source_url: ""
    data_public: true
    verified: VERIFY_medicaid-naive-vs-careful.csv
---

## Question

When a state expanded Medicaid to adults with incomes under 138% of the
poverty line, did fewer of those adults go without health insurance — and
by how much, compared with what would have happened anyway?

## Data

The uninsured rate among adults aged 19–64 with incomes under 138% of the
poverty line, for every state and DC, from the Census Bureau's American
Community Survey microdata, 2009–2019 (with 2021–2024 for a secondary
look; 2020 had no standard 1-year release). I built the rate from person
records rather than the published table because the table changes its age
band in 2017; the two agree closely where they overlap. Expansion dates
come from KFF; a state counts as treated in the year its expansion took
effect if that was on or before July 1.

## Design

I compared how the uninsured rate changed in states that expanded with how
it changed, over the same years, in states that had not yet expanded.

## Result

**Expansion lowered the uninsured rate among low-income adults by
{pp(-h['att'])} percentage points (95% interval {pp(-h['hi'])} to {pp(-h['lo'])}).**

[figure:fig-1]

The comparison group matters more than the method. Between 2013 and the
2016–2019 average, the uninsured rate in the {nvc['treated_states']} states that expanded in 2014
fell by {pp(-pt['naive_change'])} points (95% interval {pp(-pci['naive_change'][1])} to {pp(-pci['naive_change'][0])}).
But it fell by {pp(-pt['comparison_change'])} points in states that did not expand, because
the rest of the Affordable Care Act arrived everywhere at once. Net of
that, the change is {pp(pt['adjusted_change'])} points ({ci(pci['adjusted_change'][0], pci['adjusted_change'][1])}).

[figure:fig-2]

The simple comparison gives {pp(pt['adjusted_change'])} points because it looks only at the
2014 states two to five years in, when the effect had grown; averaged over
every expanding state and every year after expansion, including the first,
smaller year ({pp(e0)} points), the effect is {pp(h['att'])} points — the headline.

A simpler regression (two-way fixed effects) gives almost the same answer,
which is expected here: {nvc['treated_states']} of the {treated} states that expanded by 2019 did so
together in 2014, so there are few staggered comparisons for it to get wrong.

| Estimate (percentage points) | Population-weighted | Equal state weights |
|---|---|---|
| Callaway–Sant'Anna | {pp(h['att'])} ({ci(h['lo'], h['hi'])}) | {pp(eq['att'])} ({ci(eq['lo'], eq['hi'])}) |
| Two-way fixed effects | {pp(tw['pop']['att'])} ({ci(tw['pop']['lo'], tw['pop']['hi'])}) | {pp(tw['equal']['att'])} ({ci(tw['equal']['lo'], tw['equal']['hi'])}) |

**Checks.** The result holds when I change the sample:

| Check | Estimate | 95% interval |
|---|---|---|
{rob}

Dropping the five states that already covered this group before 2014
makes the effect larger; using all adults 19–64, most of whom were never
eligible, makes it much smaller. Two rows were added after I saw the
results, and are labeled so.

**Before expansion.** The pre-specified test that the four pre-expansion
estimates are jointly zero does not reject (p = {pre['p']:.2f}). The estimator's
built-in test, which stacks every pre-period cell, returns p = {pre['did_Wpval']:.0f}, but it is
unusable here: its covariance matrix has a condition number of about
{sci(allc['condition_number'])} because the 2015, 2016 and 2019 groups have two or three states
each. Looked at one group at a time, the 2014 states are flat before
expansion, but the 2015 states (Indiana, New Hampshire, Pennsylvania) were
already drifting ({cells_2015}). Dropping them leaves the
result unchanged.

**How much a pre-trend could matter.** Moderate robustness — the average
effect stays clear of zero unless the post-expansion violation exceeds
{bd['avg_post']:g} times the largest pre-period deviation.

**Against published estimates.** Two published studies of the second year
of expansion found {pp(bench[0]['estimate_pp'])} points ({bench[0]['study']}; National Health Interview
Survey, U.S. citizens 19–64 under 138% of poverty) and about
{pp(bench[1]['estimate_pp'])} points ({bench[1]['study']}; ACS, low-educated adults 19–64). My
second-year estimate is {pp(m['e1'])} points. Both figures come from the studies'
abstracts and use different populations, so the comparison is approximate.

Over the full 2009–2024 period the estimate is {pp(sec['att'])} points, but those later
years are confounded by the 2020–2023 rule that kept Medicaid enrollees
covered in every state and by the 2023–24 unwinding, so I treat them as
context, not as the result.

## What this does not show

- **Who gained coverage.** This is a state-level rate; it does not say
  which people gained coverage or whether their health changed.
- **Clean timing everywhere.** Several states covered some low-income adults
  before 2014, and some expanded partway through a year; the robustness
  rows bound these choices but cannot remove them.
- **Recent years.** After 2019 the comparison is confounded by pandemic-era
  continuous enrollment, its unwinding, and Georgia's limited Pathways
  program (from July 2023).

## Reproduce it

The code, the analysis plan (committed before any estimate was run), the
decision log and the results files are at
[https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/medicaid_did](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/medicaid_did); the run instructions are in the
[demos README](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos).

## If this were your data

The same design answers "did our change work?" for a price, a policy or a
program rolled out to some places or groups before others: it separates
the change you made from everything else that moved at the same time, and
says how sure you can be.
"""
    (ANALYSIS / "medicaid-expansion-uninsured.md").write_text(body, encoding="utf-8")


# ------------------------------------------------------------------ Demo B --

def demo_b():
    r = json.loads((ROOT / "results/osha_audit.json").read_text(encoding="utf-8"))
    nv, a3, s3a = r["step2_naive"], r["step3a_final"], r["step3a_rule"]["sensitivity"]
    b3 = r["step3b_final"]["narrow_rule"]
    est, ft = r["step3d_estimate"], r["final_tables"]
    mn, sens, ov = est["main"], est["sensitivity_judgment_calls_flipped"], est["overstatement"]
    lim = est["limitation_80_85"]
    w = pd.DataFrame(ft["waterfall"])
    ba = pd.DataFrame(ft["before_after"])
    fs0 = ft["federalstate0_line"]
    hc = pd.DataFrame(r["step3e_headcounts"]["table"])
    res = pd.read_csv(ROOT / "data/interim/osha_resolved.csv", dtype=str, keep_default_na=False)
    yr = pd.to_datetime(res.EventDate, format="mixed").dt.year.value_counts().sort_index()

    lv, ls = w.employers_by_name.tolist(), w.employers_by_name_and_state.tolist()
    names = ["Duplicates removed", "Names normalized", "Fuzzy matching", "National aliases"]
    wf = [{"step": "Raw employer names", "value": lv[0], "kind": "start",
           "employers_by_name_after": lv[0], "employers_by_name_and_state_after": ls[0]}]
    wf += [{"step": names[i - 1], "value": lv[i] - lv[i - 1], "kind": "step",
            "employers_by_name_after": lv[i], "employers_by_name_and_state_after": ls[i]}
           for i in range(1, len(lv))]
    wf += [{"step": "Employers (final)", "value": lv[-1], "kind": "end",
            "employers_by_name_after": lv[-1], "employers_by_name_and_state_after": ls[-1]}]
    pd.DataFrame(wf).to_csv(DATA / "osha-employer-waterfall.csv", index=False)

    ba_rows = "\n".join(
        f"| {x['rank']} | {x['naive_employer']} | {n(x['naive_reports'])} | {x['resolved_employer']} | "
        f"{n(x['resolved_reports'])} | {x['resolved_pct_of_reports']:.2f} | {x['resolved_raw_variants']} | "
        f"{x['resolved_states']} |" for x in ba.to_dict(orient="records"))
    hc_rows = "\n".join(
        f"| {x['employer']} | {n(x['reports'])} | {n(x['headcount'])} | {x['scope']} | {x['source']} ({x['as_of']}) |"
        for x in hc.to_dict(orient="records"))
    final_by_name = int(w.employers_by_name.iloc[-1])
    final_by_state = int(w.employers_by_name_and_state.iloc[-1])

    body = f"""---
draft: false
title: "Who files the most severe-injury reports? It depends on how you count employers"
date: {DATE}
updated: {DATE}
summary: "A worked data audit of OSHA's Severe Injury Reports: the raw file lists {n(nv['distinct_raw_employer_names'])} employer names; after removing duplicates, normalizing names and matching variants, it is about {n(final_by_name)} employers, and the top of the ranking changes completely. Counts of reports filed are not a safety ranking."
method: >-
  Step by step, each step's effect reported: same-incident duplicates
  removed by a stated rule and confirmed by hand; employer names normalized
  (case, punctuation, legal suffixes, "dba", store numbers); fuzzy entity
  resolution (rapidfuzz) blocked by state, with cross-state matching only
  for employers present in five or more states and a hand-approved list of
  national aliases; matcher precision and recall estimated from a
  stratified sample of 300 labeled candidate pairs.
data_sources:
  - name: "U.S. Department of Labor, OSHA, Severe Injury Reports, January 2015 to November 2025"
    url: "https://www.osha.gov/severe-injury-reports"
  - name: "OSHA State Plans (jurisdiction)"
    url: "https://www.osha.gov/stateplans"
  - name: "Company Form 10-K filings (SEC EDGAR) and the U.S. Postal Service FY2024 Form 10-K (headcounts)"
    url: "https://www.sec.gov/edgar/search/"
download: "/static/data/osha-employer-waterfall.csv"
figures:
  - id: fig-1
    type: waterfall
    data: osha-employer-waterfall.csv
    x: step
    y: value
    title: "Most of the distortion is in the names, not the duplicates"
    caption: "Distinct employers in OSHA's Severe Injury Reports, counted by name: the raw count, the change at each audit step, and the final count. The data table also gives the count by name and state after each step."
    source: "OSHA Severe Injury Reports, January 2015 – November 2025."
    source_url: "https://www.osha.gov/severe-injury-reports"
    data_public: true
    verified: VERIFY_osha-employer-waterfall.csv
---

## Question

Which employers file the most severe-injury reports with OSHA — and can
you trust the obvious way of counting them?

## Data

OSHA's Severe Injury Reports: {n(nv['reports'])} reports of amputations, in-patient
hospitalizations and losses of an eye, January 2015 to November 2025.
**They cover federal-OSHA jurisdictions only; states with their own
OSHA-approved State Plans are not included.** {n(fs0['naive_federalstate0_reports'])} reports carry the file's
undocumented `FederalState = 0` flag, mostly in State Plan states; they
appear as a separate line wherever they matter. Reports dipped from
{n(yr.get(2019, 0))} in 2019 to {n(yr.get(2020, 0))} in 2020, which reflects the pandemic, not a safety trend.
Everything below counts **reports filed**.

## Design

I counted reports by employer the obvious way, then repeated the count after
each cleaning step, measuring what each step changed.

## Result

**Counted by the raw employer field, the file lists {n(nv['distinct_raw_employer_names'])} employers; after
cleaning it is {n(final_by_name)} by name, or {n(final_by_state)} if identical names in different states
count separately.** How many employers filed reports depends on the
definition — identical names in different states are usually different
small firms, but the same company for national employers.

[figure:fig-1]

**Duplicates are a minor issue here.** No row is an exact copy of another. A
stated rule found same-incident pairs filed twice by the same employer;
depending on how strict the rule is, {s3a['strict']['same_employer_pairs']} to {s3a['loose']['same_employer_pairs']} pairs qualify ({s3a['proposed']['same_employer_pairs']}
under the rule I used), because the count depends on the matching rule.
After checking each one by hand, {a3['rows_removed']} of {n(a3['reports_before'])} reports were merged. Two
merges were judgment calls (XPO Logistics, 5/3/2019; VA John D. Dingell
Medical Center, 5/2/2019: same machine or door and day, a different finger
recorded), and three pairs were kept apart as two workers. A merged report
keeps the lowest report number and the higher injury counts of the two.

**The larger distortion is in employer names.** Normalizing case,
punctuation, legal suffixes, "dba" and store numbers removes
{n(w.employers_by_name.iloc[1] - w.employers_by_name.iloc[2])} names; fuzzy matching removes {n(w.employers_by_name.iloc[2] - w.employers_by_name.iloc[3])} more; a short, hand-approved list of
national aliases (USPS for U.S. Postal Service, store formats such as
Walmart Supercenter) removes {n(w.employers_by_name.iloc[3] - w.employers_by_name.iloc[4])}. Names that refer to the same operating
employer merge (store formats and locations, acronyms); separate legal
operating companies stay separate (FedEx Freight vs FedEx; subsidiaries vs
parents).

| Rank | Raw employer field | Reports | Resolved employer | Reports | % of reports | Name variants | States |
|---|---|---|---|---|---|---|---|
{ba_rows}
| — | `FederalState = 0` reports | {n(fs0['naive_federalstate0_reports'])} | `FederalState = 0` reports | {n(fs0['resolved_federalstate0_reports'])} | — | — | — |

The raw top 15 is really six organizations: the Postal Service alone fills
five places under five spellings.

**How good is the matching?** The matcher is precise but conservative.
Of 150 merges it made, {mn['precision_k_n'][0]} were right: precision {pct(mn['precision'])} (95% Wilson
interval {pct(mn['precision_ci95_wilson'][0])} to {pct(mn['precision_ci95_wilson'][1])}). It finds an estimated {pct(mn['recall'])} of true
matches (95% stratified-bootstrap interval {pct(mn['recall_ci95_stratified_bootstrap'][0])} to {pct(mn['recall_ci95_stratified_bootstrap'][1])}). In the band just
above the threshold, nearly all misses are typos inside common words that
the distinctive-part check rejects ("Manufacturin", "Distibution",
"Serive"); but the larger estimated share is pairs scoring just under the
threshold, a mix of typos and variants such as "+" vs "and" — and that
share rests on few labeled matches, so it is uncertain. The missed matches
mean the employer count above is overstated by at most about
{ov['max_overstatement_pct']:.1f}% ({ov['max_overstatement_pct_ci95'][0]:.1f}–{ov['max_overstatement_pct_ci95'][1]:.1f}%). If every judgment-call label flipped, recall would be
{pct(sens['recall'])}. In the lowest score band none of 50 sampled pairs matched; if
the true rate there were at its upper 95% bound, recall would be
{pct(lim['recall_if_at_wilson_upper'])}. The rule was not tuned on these labels.
Accuracy figures are illustrative: they were estimated against match
labels drafted by an AI model. In client work, labels are checked by hand.

**A count ranking is not a safety ranking.** Report counts track how big an
employer is, among other things. As an illustration only, here are the
ten largest filers next to their own reported headcounts. Headcounts are
national (or company-wide) and for one fiscal year; the reports cover
federal-OSHA states only and span 2015–2025. So this is not a rate
comparison and not a safety ranking. The association is loose: industry,
and how much of a workforce sits in federal-OSHA states, matter too.

| Employer | Reports, 2015–2025 | Headcount | What the headcount covers | Source |
|---|---|---|---|---|
{hc_rows}

## What this does not show

- **Which employers are safer.** Counts reflect size, industry and
  federal-OSHA coverage; State Plan states are missing entirely, and state
  totals reflect coverage and workforce size, not relative safety.
- **A complete entity map.** The matcher misses some true matches and keeps
  subsidiaries apart from parents by design; other definitions would give
  other counts.
- **Unreported injuries.** The file holds what employers reported.

## Reproduce it

The audit code, the decision log (including every hand-review decision) and
the results files are at
[https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/osha_audit](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/osha_audit); the run instructions are in the
[demos README](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos). The label files themselves are not published.

## If this were your data

Before a number like "reports per employer" drives a decision, I would find
out what it is actually counting: the duplicates, the spellings, the
definitions and the coverage — and say how much each one moves the answer.
"""
    (ANALYSIS / "osha-severe-injury-reports-audit.md").write_text(body, encoding="utf-8")


def apply_verification():
    from site_pages.verify_figures import verify_all
    results = verify_all(DATA)
    for page in ("medicaid-expansion-uninsured.md", "osha-severe-injury-reports-audit.md"):
        path = ANALYSIS / page
        text = path.read_text(encoding="utf-8")
        for name, bad in results.items():
            text = text.replace(f"verified: VERIFY_{name}",
                                "verified: true    # every value checked against results/*.json"
                                if not bad else "verified: false   # mismatch with results/*.json")
        if "VERIFY_" in text:
            raise SystemExit(f"{page}: unresolved verification marker")
        path.write_text(text, encoding="utf-8")
    return results


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    demo_a()
    demo_b()
    for name, bad in apply_verification().items():
        print(f"{name}: {'verified, every value matches' if not bad else 'MISMATCH'}")
        for b in bad:
            print("   ", b)
    print("wrote", ANALYSIS / "medicaid-expansion-uninsured.md")
    print("wrote", ANALYSIS / "osha-severe-injury-reports-audit.md")
