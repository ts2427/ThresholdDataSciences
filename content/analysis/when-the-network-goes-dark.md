---
draft: false
title: "When the Network Goes Dark"
date: "2026-11-22"
updated: "2026-11-23"
summary: "Cell-site outages and recovery in 21 Gulf and Southeast hurricanes, 2017–2026, from FCC reports: half the sites out at the peak were back within a median of 2 days, the reports often end before 90% is back, and cell outages tend to rise and fall with power outages."
method: "County-level FCC DIRS cell-site tables, parsed, checked against their printed totals and a second reading of each PDF, and joined to EAGLE-I power outages, NHC tracks and CDC/ATSDR SVI (OpenFEMA declarations are kept in the published panel as context; no result uses them). Descriptive storm comparisons with county-bootstrap intervals; an exposure model checked for calibration on held-out storms; a discrete-time hazard for waiting time. The analysis plan was committed on November 22, 2026, in the project's private version-controlled repository (commit 9fc17a4), before any recovery outcome was computed; the plan file as committed is published in the data repository with its SHA-256. It is not blind to some figures, which are listed below with every deviation. Associations, not causes."
data_sources:
  - name: "FCC Broadband Data Collection, National Broadband Map public data (provider counts, chapter 13)"
    url: "https://broadbandmap.fcc.gov/data-download"
  - name: "FCC Disaster Information Reporting System, Communications Status Reports (2017–2026)"
    url: "https://www.fcc.gov/disaster-information-reporting-system-dirs-0"
  - name: "ORNL/DOE EAGLE-I recorded electricity outages, 2014–2025 (figshare v4)"
    url: "https://doi.org/10.6084/m9.figshare.24237376"
  - name: "NOAA National Hurricane Center, HURDAT2 and GIS best track"
    url: "https://www.nhc.noaa.gov/data/"
  - name: "CDC/ATSDR Social Vulnerability Index 2022"
    url: "https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html"
  - name: "FEMA OpenFEMA Disaster Declarations Summaries v2"
    url: "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
  - name: "U.S. Census Bureau, ACS 5-year 2022 and 2020 county Gazetteer"
    url: "https://api.census.gov"
  - name: "U.S. Census Bureau, 2022 cartographic boundary file, counties 1:500,000 (Isaias map)"
    url: "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip"
download: "/static/data/hurricane-dirs-county-day.csv"
figures:
  - id: "fig-isaias"
    type: "bar"
    data: "hurricane-isaias-counties.csv"
    x: "county"
    y: "peak_pct_out"
    title: "Isaias: the 15 counties with the highest peak share of sites out"
    caption: "Each county's highest share of cell sites out across Isaias's reports, percent; the 15 highest."
    source: "FCC DIRS Communications Status Reports."
    source_url: ""
    data_public: true
    verified: true
  - id: "fig-peaks"
    type: "interval"
    data: "hurricane-peaks.csv"
    x: "storm"
    y: "peak_pct_out"
    title: "Peak share of cell sites out, by storm"
    caption: "Share of sites served that were out in each storm's report with the most sites out, percent, with 95% county-bootstrap intervals. Storms in date order."
    source: "FCC DIRS Communications Status Reports."
    source_url: ""
    data_public: true
    verified: true
    lo: "ci95_low"
    hi: "ci95_high"
    vertical_labels: true
  - id: "fig-restored"
    type: "interval"
    data: "hurricane-restored.csv"
    x: "storm"
    y: "restored_pct_counties_stay_out"
    title: "How much was back by each storm's last report, under both bounds"
    caption: "Share of the sites out at the peak that were back by the storm's last report, percent. The dot and lower end: counties that leave the reports keep their last reported outages. Upper end: they are counted as restored. Nicole: no report after its peak, so no recovery could be observed. Not shown."
    source: "FCC DIRS Communications Status Reports."
    source_url: ""
    data_public: true
    verified: true
    lo: "low"
    hi: "restored_pct_counties_restored"
    vertical_labels: true
  - id: "fig-causes"
    type: "bar"
    data: "hurricane-causes.csv"
    x: "cause"
    y: "pct_of_sites_out"
    title: "Loss of commercial power is the largest cause the FCC records"
    caption: "Shares of cell sites out, pooled over 17 storms with cause columns, percent. Over-attribution is shown beside the others and never netted against unattributed sites."
    source: "FCC DIRS Communications Status Reports."
    source_url: ""
    data_public: true
    verified: true
  - id: "fig-power"
    type: "column"
    data: "hurricane-power-lags.csv"
    x: "hours_before_report"
    y: "median_rank_correlation"
    title: "Cell outages line up with power outages up to about 12 hours earlier"
    caption: "Median across 20 storms of the within-storm rank correlation between % of customers (meters) without power and % of cell sites out, by how many hours before the report the power value is taken."
    source: "FCC DIRS; ORNL/DOE EAGLE-I."
    source_url: ""
    data_public: true
    verified: true
  - id: "fig-zone"
    type: "bar"
    data: "hurricane-wind-zone.csv"
    x: "wind_zone"
    y: "peak_pct_out"
    title: "Peak share of cell sites out, by wind zone"
    caption: "Sum of county peak sites out over sum of sites served, percent, by the strongest wind radius the county fell inside."
    source: "FCC DIRS; NHC HURDAT2 and GIS best track."
    source_url: ""
    data_public: true
    verified: true
  - id: "fig-distance"
    type: "bar"
    data: "hurricane-distance.csv"
    x: "distance_to_track"
    y: "peak_pct_out"
    title: "Peak share of cell sites out, by distance to the track"
    caption: "Sum of county peak sites out over sum of sites served, percent, by distance from the county's internal point to the storm track."
    source: "FCC DIRS; NHC HURDAT2 and GIS best track; Census Gazetteer."
    source_url: ""
    data_public: true
    verified: true
  - id: "fig-coverage"
    type: "heatmap"
    data: "hurricane-coverage-heatmap.csv"
    x: "day"
    y: "pct_out"
    title: "Every storm's reports, day by day"
    caption: "Each row is a storm, in date order; each cell is one FCC report, by calendar days since the storm's 34-knot winds first reached a study-state county (day 0; see the methods), shaded by the share of sites served that were out. Blank cells: no FCC report that day. Crossed cells: an FCC report that exists but is excluded (Harvey day 9, Laura days 2–4 and Helene days 8–9; listed in the methods). Outlined cell: Laura's report of 2020-08-25, the combined Marco–Laura report, before Laura's winds arrived (shown here as the one exception to keeping it off Laura's timeline; see Laura's note in chapter 3). Rule periods are marked at the right. Late dark cells can reflect a reporting area narrowed to a few hard-hit counties (Laura)."
    source: "FCC DIRS Communications Status Reports."
    source_url: ""
    data_public: true
    verified: true
    row: "storm"
    col: "day"
    value: "pct_out"
    group: "period"
    legend_label: "% of sites out"
    flag: "flag"
    flag_label: "combined Marco–Laura report, before Laura's winds arrived"
    x_label: "Days since 34-kt winds arrived"
    blank_label: "no report"
    excluded_label: "report excluded"
    description: "A grid of storms by days since their 34-knot winds arrived. Darker cells mean a larger share of cell sites out in that day's report; crossed cells are excluded reports; the outlined cell, Laura day -1, is the combined Marco–Laura report, before Laura's winds arrived; rows end where the FCC's reports for that storm end."
  - id: "fig-isaias-map"
    type: "map"
    data: "hurricane-isaias-map.csv"
    x: "county"
    y: "peak_pct_out"
    title: "Isaias: peak share of cell sites out by county, with the storm's track"
    caption: "Each county's highest share of sites out across Isaias's reports, percent. White counties were not in its reports; the lightest grey ones were, with no sites out. The orange line is the NHC best track."
    source: "FCC DIRS; NHC GIS best track; U.S. Census Bureau cartographic boundary file (2022, 1:500,000)."
    source_url: ""
    data_public: true
    verified: true
    value: "peak_pct_out"
    path: "d"
    tx: "x"
    ty: "y"
    width: 720
    height: 439
    legend_label: "peak % of sites out"
    track_label: "Isaias track"
    no_data_label: "not in the reports"
    table_where: ["kind", "area"]
    table_columns: ["county", "fips", "peak_pct_out"]
    description: "A map of the Florida Panhandle, southern Alabama and nearby counties. Counties are shaded by their peak share of cell sites out; the darkest lie near the track, on the coast and inland."
  - id: "fig-curves"
    type: "multiples"
    data: "hurricane-recovery-curves.csv"
    x: "day"
    y: "pct"
    title: "Recovery curves for every storm, under both bounds"
    caption: "Share of the sites out at the peak that were back, percent, by days since the peak. Solid: counties that leave the reports keep their last reported outages, with the 95% county-bootstrap band. Dashed: they are counted as restored. Panels in date order; rule periods marked in orange. Nicole: no report after its peak, so no recovery could be observed. Not shown. Where the band's lower end falls below 0% (Harvey, Milton and Nicholas: resampled counties with more sites out than at the peak), it is drawn from 0; the data table gives the values."
    source: "FCC DIRS Communications Status Reports."
    source_url: ""
    data_public: true
    verified: true
    panel: "storm"
    series: "series"
    series_order: ["stay_out", "restored"]
    series_labels: {"stay_out": "leaving counties still out", "restored": "leaving counties restored"}
    lo: "lo"
    hi: "hi"
    group: "period"
    y_max: 100
    x_label: "Days since the peak"
    description: "Small panels, one per storm, each with two rising lines from 0% at the peak; where the dashed line sits above the solid one, counties left the reports while still out."
  - id: "fig-power-overlay"
    type: "multiples"
    data: "hurricane-power-overlay.csv"
    x: "day"
    y: "pct"
    title: "Power outages and cell outages, storm by storm"
    caption: "Share of electricity customers (meters) without power and share of cell sites out, percent, in each report over the counties matched to EAGLE-I in that report, by days since the storm's 34-knot winds arrived. EAGLE-I ends in 2025, so Isaias is not shown. The matched counties narrow as the FCC's reporting area shrinks (Harvey 31 to 2; Florence 55 to 15; Michael 85 to 13; Laura 94 to 4; Sally 24 to 10; Delta 91 to 8; Zeta 118 to 14; Ida 68 to 7; Ian 54 to 3; Idalia 38 to 6; Francine 43 to 21; Helene 143 to 4 counties, first to last report), so late values describe only the counties still reported. Reports with no power match are left out: one of Laura's reports (its Sep 1, 2020 report, which prints no as-of time)."
    source: "FCC DIRS; ORNL/DOE EAGLE-I."
    source_url: ""
    data_public: true
    verified: true
    panel: "storm"
    series: "series"
    series_order: ["sites", "power"]
    series_labels: {"sites": "% of cell sites out", "power": "% of customers without power"}
    group: "period"
    y_max: 70.0
    x_label: "Days since 34-kt winds arrived"
    table_columns: ["storm", "period", "day", "series", "pct", "counties"]
    description: "Small panels, one per storm, each with a line for cell sites out and one for customers without power. The two lines often move together, but not in every storm: in some the power share rises late as the reporting area narrows to a few hard-hit counties, and in others sites stay out after power is back."
  - id: "fig-calibration"
    type: "calibration"
    data: "hurricane-calibration.csv"
    x: "mean_predicted_pct"
    y: "observed_pct"
    title: "Exposure model: predicted against observed, on held-out storms"
    caption: "Each dot is a tenth of the storm-counties, ordered by predicted peak share: mean predicted against observed peak share of sites out, percent, with each storm held out of the fit. Dots on the dashed line would be perfectly calibrated."
    source: "FCC DIRS; NHC; model in the methods."
    source_url: ""
    data_public: true
    verified: true
    x_label: "Mean predicted peak % out"
    y_label: "Observed peak % out"
    description: "Ten dots near the diagonal at both ends, with the middle deciles scattered on either side."
  - id: "fig-svi"
    type: "interval"
    data: "hurricane-svi-wait.csv"
    x: "svi_quartile"
    y: "median_days"
    title: "Days until a county stayed below 5% of sites out, by SVI quartile"
    caption: "Kaplan-Meier median days since the storm's 34-knot winds arrived, with 95% county-bootstrap intervals. Quartiles of the at-risk counties' SVI 2022 national percentiles."
    source: "FCC DIRS; CDC/ATSDR SVI 2022."
    source_url: ""
    data_public: true
    verified: true
    lo: "ci95_low"
    hi: "ci95_high"
---

## Why this page exists

When a hurricane reaches the Gulf Coast, a working phone is often what people need most, and one of the first things they lose.
{: .page-lede}

During major storms the FCC tracks cell-site outages and publishes a daily report. But it publishes them one PDF at a time, storm by storm, in formats that change from year to year, so nobody can easily see the whole picture.

I put them side by side: 167 FCC reports from 21 hurricanes, 2017–2026, checked line by line against the originals and linked to power-outage, storm-track and social-vulnerability data. The page asks four questions: How much of the network goes dark? How fast does it come back? What takes it down? Who waits longest?

### What I found

- Half of the sites that go dark are typically back within about 2 days.
- Lost power and lost network connections, not damage to the sites themselves, account for most outages, and cell outages tend to rise and fall with power outages.
- Counties with higher social vulnerability did not take measurably longer for cell outages to fall below 5% of sites.
- The FCC's reporting often ended before recovery could be confirmed: only 6 to 11 of 20 storms reached 90% restored within the reports.

Each finding's uncertainty and limits are given in its chapter.

### What version 2 adds

Exploratory: added after version 1 of this page was published. Chapters 10 to 13, the map and the county lookup are new.

- In all 21 storms, the FCC's last public report still showed cell sites out: 1,883 in total. The median share of a storm's peak still out at its last report is 9.0% (20 storms).
- The FCC printed sites operating on backup power for 11 of 21 storms; the most in one report was 1,990 sites, in Helene.
- Where the order could be determined (351 of 499 counties), cell outages fell below 5% of sites first in 158 counties and power outages fell below 5% of customers first in 66; in 127 both fell below 5% in the same report. The two are measured on different scales (cell sites served, electricity meters), so this is not the order in which people got service back.
- In storms from 2022 on, counties served by more mobile providers did not show a consistent difference in how long cell outages took to fall below 5% of sites.

### How to read it

Everything here is descriptive: it shows what happened together, not what caused what. The analysis plan was committed on November 22, 2026, in the project's private version-controlled repository (commit 9fc17a4), before any recovery outcome was computed. The plan file as committed is published in the data repository with its SHA-256, so it can be checked against later changes. It is not blind to some figures, which are listed in the methods. Every number is generated by code, and each chapter states its limits. The data and code are public. It's written for emergency managers, utilities, carriers, regulators, and anyone who has lost signal in a storm.

## Map: where cell sites were out, report by report

Choose a storm and move through its FCC reports to see each county's share of cell sites out. Counties shaded darker had
a larger share out (fixed steps for every storm: 0%, under 5%, 5–15%, 15–30%, 30–50% and 50% or more); hatched light-grey counties were not in that day's report (not
reported, not zero), and counties in the report with no sites out have a faint tint. Hover over or tap a county
for its numbers, and the cause shares where the report gives them. The table under the map lists the same numbers for
the chosen report. Drawn in your browser from the published data for all 21 storms, with county shapes from the
Census Bureau; nothing is loaded from any other site. Laura's report of 2020-08-25 (the combined Marco–Laura report) is not a step on Laura's slider.

Across all 9,870 county-reports, 48.3%
show 0% of sites out and 3.2% show 50% or more.

<div class="storm-map" data-src="/static/data/hurricane-map.json" data-topo="/static/data/hurricane-counties.topo.json" data-scale="steps">
<div class="storm-map-controls">
<div><label for="storm-map-storm">Storm</label>
<select id="storm-map-storm" disabled><option>Loading…</option></select></div>
<div class="storm-map-slider"><label for="storm-map-day">Report</label>
<input id="storm-map-day" type="range" min="0" max="0" step="1" value="0" disabled></div>
<button type="button" class="storm-map-play" aria-pressed="false" disabled>Play</button>
</div>
<p class="storm-map-status" role="status" aria-live="polite"></p>
<figure class="storm-map-figure"><div class="storm-map-svg"></div>
<div class="storm-map-tip" aria-hidden="true" hidden></div></figure>
<details class="fig-data"><summary>View data table for this report</summary><div class="table-scroll storm-map-table"></div></details>
<noscript><p>The map needs JavaScript. The same data is in the <a href="/static/data/hurricane-dirs-county-day.csv">county-report
panel (CSV)</a>.</p></noscript>
</div>
<script src="/static/js/vendor/d3-7.9.0.min.js" defer></script>
<script src="/static/js/vendor/topojson-client-3.1.0.min.js" defer></script>
<script src="/static/js/hurricane-map.js" defer></script>

## 1. The question and the data

**Claim.** The FCC's Disaster Information Reporting System (DIRS) publishes, for each activated storm, a daily county table of cell sites served and out. Of 178 reports in scope, 7 are excluded (they fail validation; listed in the methods) and 4 have county rows only outside the ten study states (Irma, 2017-09-07 to 2017-09-10: Puerto Rico and the U.S. Virgin Islands), leaving 167 reports for 21 storms: 10,030 county-report rows in 814 counties of ten Gulf and Southeast states.

**Exhibit.**

[figure:fig-coverage]

| Storm | Rule period | DIRS activation | Reports used | Counties | Report dates | Reports excluded |
|---|---|---|---|---|---|---|
| Harvey | P0 | 2017-08-25 | 10 | 64 | 2017-08-26 to 2017-09-05 | 1 |
| Irma | P0 | 2017-09-06 | 8 | 90 | 2017-09-11 to 2017-09-18 | 0 |
| Nate | – | 2017-10-08 | 0 | 0 | – | 1 |
| Florence | P0 | 2018-09-12 | 11 | 102 | 2018-09-14 to 2018-09-24 | 0 |
| Michael | P0 | 2018-10-09 | 16 | 110 | 2018-10-11 to 2018-10-26 | 0 |
| Barry | P0 | 2019-07-12 | 2 | 73 | 2019-07-14 to 2019-07-15 | 0 |
| Dorian | P0 | 2019-08-27 | 5 | 132 | 2019-09-03 to 2019-09-07 | 0 |
| Laura | P0 | 2020-08-24 | 12 | 325 | 2020-08-25 to 2020-09-08 | 3 |
| Sally | P0 | 2020-09-14 | 7 | 31 | 2020-09-15 to 2020-09-21 | 0 |
| Delta | P0 | 2020-10-08 | 5 | 110 | 2020-10-10 to 2020-10-14 | 0 |
| Zeta | P0 | 2020-10-28 | 4 | 210 | 2020-10-29 to 2020-11-01 | 0 |
| Ida | P0 | 2021-08-29 | 22 | 101 | 2021-08-30 to 2021-09-20 | 0 |
| Nicholas | P0 | 2021-09-14 | 2 | 14 | 2021-09-15 to 2021-09-16 | 0 |
| Ian | P0 | 2022-09-27 | 13 | 101 | 2022-09-28 to 2022-10-10 | 0 |
| Nicole | P0 | 2022-11-09 | 2 | 34 | 2022-11-10 to 2022-11-11 | 0 |
| Idalia | P0 | 2023-08-29 | 6 | 64 | 2023-08-30 to 2023-09-04 | 0 |
| Beryl | P1 | 2024-07-08 | 6 | 6 | 2024-07-09 to 2024-07-14 | 0 |
| Debby | P1 | 2024-08-04 | 5 | 120 | 2024-08-05 to 2024-08-09 | 0 |
| Francine | P1 | 2024-09-11 | 3 | 45 | 2024-09-12 to 2024-09-14 | 0 |
| Helene | P1 | 2024-09-25 | 22 | 322 | 2024-09-26 to 2024-10-19 | 2 |
| Milton | P1 | 2024-10-07 | 5 | 52 | 2024-10-10 to 2024-10-14 | 0 |
| Isaias | P3 | 2026-10-08 | 3 | 44 | 2026-10-10 to 2026-10-12 | 0 |

Ida, Nicholas share 2 reports, so the "Reports used" column counts those reports for both storms.

**What it means.** The tables combine all providers, so no single company's network is visible. Coverage changes during a storm: counties join and leave the reporting area, and the FCC narrows the area as outages fall. Reporting was voluntary before February 20, 2025 and mandatory after; from June 30, 2026, FCC 26-34 exempts non-facilities-based providers and drops DIRS final reports. So who reports can change between storms. The page groups storms by these rule periods, using each storm's DIRS activation date:

- **P0:** neither rule (DIRS activated before May 1, 2024)
- **P1:** MDRI in force, DIRS voluntary (May 1, 2024 to February 19, 2025)
- **P2:** MDRI and mandatory DIRS (February 20, 2025 to June 29, 2026)
- **P3:** MDRI and mandatory DIRS as modified by FCC 26-34 (from June 30, 2026)

## 2. Anatomy of a storm: Isaias, October 2026

**Claim.** Isaias's first report counted 627 of 4,033 cell sites out (15.5%) across its reporting area; by its last report, 75 (1.8%) were out.

**Exhibit.**

[figure:fig-isaias-map]

[figure:fig-isaias]

| State | Report | Sites out | Sites served | % out |
|---|---|---|---|---|
| Alabama | 2026-10-10 | 195 | 1,117 | 17.5 |
| Alabama | 2026-10-11 | 135 | 1,172 | 11.5 |
| Alabama | 2026-10-12 | 21 | 1,173 | 1.8 |
| Florida | 2026-10-10 | 431 | 2,382 | 18.1 |
| Florida | 2026-10-11 | 263 | 2,382 | 11.0 |
| Florida | 2026-10-12 | 54 | 2,382 | 2.3 |
| Mississippi | 2026-10-10 | 1 | 534 | 0.2 |
| Mississippi | 2026-10-11 | 4 | 534 | 0.7 |
| Mississippi | 2026-10-12 | 0 | 534 | 0.0 |

**What it means.** The five worst-hit counties (Okaloosa, Walton, Holmes, Santa Rosa and Washington) are all in the Florida Panhandle, near the track, on the coast and inland. 31 of Isaias's 44 counties fell inside its 34-knot winds and 3 inside its 64-knot winds; its strongest wind at the point of the track nearest a county was 97 knots. Days are counted from the first time Isaias's 34-kt winds reach a study-state county in its reports. EAGLE-I covers 2014-2025, so storms in 2026 (Isaias) have no power match or overlay until a 2026 release exists.

## 3. How much goes dark

**Claim.** At their peaks, between 0.9% and 28.7% of the cell sites in storms' reporting areas were out; the median across 21 storms is 10.3% (95% interval 3.4 to 12.3). Helene had the most sites out, 4,562 (95% interval 3,541 to 5,675).

**Exhibit.**

[figure:fig-peaks]

| Storm | Period | Peak report | Days since 34-kt winds arrived | Sites out (95% interval) | % out | Sites served | Cable and wireline subscribers out (report area) |
|---|---|---|---|---|---|---|---|
| Harvey | P0 | 2017-08-29 | 4.1 | 365 (192 to 732) | 4.7 | 7,805 | 283,593 |
| Irma | P0 | 2017-09-11 | 2.0 | 3,973 (2,462 to 6,039) | 27.4 | 14,502 | 7,597,945 |
| Florence | P0 | 2018-09-15 | 2.2 | 1,278 (846 to 1,794) | 10.7 | 11,923 | not printed |
| Michael | P0 | 2018-10-11 | 1.4 | 1,357 (824 to 2,050) | 18.8 | 7,212 | not printed |
| Barry | P0 | 2019-07-14 | 2.1 | 90 (52 to 131) | 1.7 | 5,169 | not printed |
| Dorian | P0 | 2019-09-06 | 3.8 | 281 (130 to 512) | 3.4 | 8,167 | not printed |
| Laura | P0 | 2020-08-27 | 1.1 | 513 (261 to 869) | 1.6 | 32,136 | 192,915 |
| Sally | P0 | 2020-09-17 | 2.5 | 454 (145 to 849) | 17.1 | 2,659 | 156,147 |
| Delta | P0 | 2020-10-10 | 1.1 | 674 (471 to 913) | 5.6 | 12,051 | 304,992 |
| Zeta | P0 | 2020-10-29 | 1.0 | 1,555 (982 to 2,324) | 10.3 | 15,073 | 362,327 |
| Ida | P0 | 2021-08-30 | 1.4 | 1,824 (1,097 to 2,646) | 28.1 | 6,492 | not printed |
| Nicholas | P0 | 2021-09-15 | 1.8 | 128 (24 to 299) | 2.4 | 5,249 | not printed |
| Ian | P0 | 2022-09-29 | 1.6 | 1,552 (893 to 2,325) | 10.9 | 14,188 | 525,966 |
| Nicole | P0 | 2022-11-11 | 2.7 | 103 (55 to 181) | 0.9 | 11,450 | 55,372 |
| Idalia | P0 | 2023-08-31 | 1.7 | 157 (98 to 224) | 1.9 | 8,268 | 57,715 |
| Beryl | P1 | 2024-07-09 | 1.5 | 1,335 (192 to 3,291) | 28.7 | 4,656 | 803,501 |
| Debby | P1 | 2024-08-06 | 2.0 | 119 (78 to 169) | 0.9 | 13,465 | 22,422 |
| Francine | P1 | 2024-09-12 | 0.9 | 255 (139 to 393) | 9.3 | 2,731 | 135,980 |
| Helene | P1 | 2024-09-28 | 2.6 | 4,562 (3,541 to 5,675) | 12.1 | 37,717 | 1,199,087 |
| Milton | P1 | 2024-10-10 | 0.9 | 1,953 (1,145 to 3,152) | 12.3 | 15,877 | 1,273,354 |
| Isaias | P3 | 2026-10-10 | 1.0 | 627 (312 to 977) | 15.5 | 4,033 | 45,760 |

Days count from day 0: the first time the storm's 34-knot (tropical-storm-force) winds reach any study-state county in its reports, from the NHC best-track wind radii. Every storm has 34-knot radii at that time, so none uses the fallback (its first landfall in the study states).

**What it means.** Peaks are shares of each storm's own reporting area, which ranges from a few counties to hundreds, so a small share can hide a large count and the reverse. Laura's peak may be understated: its reports of 2020-08-28, 2020-08-29 and 2020-08-30, after the peak report of 2020-08-27, are excluded. Laura's report of 2020-08-25 is the FCC's combined report for Marco and Laura, keyed to Laura; it falls 0.9 days before Laura's 34-knot winds reached a study-state county, so its outages are likely Marco's. It stays in the published panel, flagged pre_onset_likely_marco. It is left out of anything that places it on Laura's timeline (peak timing, recovery, waiting times, rule periods, the power overlay chart), with one exception: the coverage heatmap shows it as a marked (outlined) cell. It is kept where only same-time comparisons are made (the power-cell correlations). Beryl's peak share comes from 6 counties. Michael's reports print 261 sites served in Jefferson County, Florida, against a median of 40 in later storms' reports: an apparent FCC denominator error, kept as printed. Without it, Michael's peak is 19.3%. Cable and wireline subscribers out are printed for the whole report area, with no county detail.

## 4. How fast it comes back

**Claim.** Half of the sites out at a storm's peak were back within a median of 2 days (95% interval from 2, with no upper limit identified because of censoring; 1 of 20 storms never reached half while their reports ran). Only 6 to 11 of 20 storms reached 90% restored before their reports ended: 6 if counties that leave the reports are counted as still out, 11 if they are counted as restored. The FCC's reporting area narrows as outages fall, so a county leaving the reports is consistent with recovery but does not prove it.

**Exhibit.**

[figure:fig-curves]

[figure:fig-restored]

| Storm | Sites out at peak | Days to 50% | Days to 90% (leaving counties still out) | Days to 90% (leaving counties restored) | Site-days lost, peak to last report |
|---|---|---|---|---|---|
| Harvey | 365 | 4 | not reached by day 7 | not reached by day 7 | 1,474 |
| Irma | 3,973 | 3 | not reached by day 7 | not reached by day 7 | 13,145 |
| Florence | 1,278 | 3 | 7 | 6 | 3,533 |
| Michael | 1,357 | 2 | 12 | 11 | 4,706 |
| Barry | 90 | 1 | not reached by day 1 | not reached by day 1 | 58 |
| Dorian | 281 | 1 | not reached by day 1 | not reached by day 1 | 187 |
| Laura | 513 | 7 | not reached by day 12 | not reached by day 12 | 3,833 |
| Sally | 454 | 1 | 3 | 3 | 481 |
| Delta | 674 | 2 | not reached by day 4 | 3 | 1,396 |
| Zeta | 1,555 | 2 | not reached by day 3 | 2 | 2,774 |
| Ida | 1,824 | 2 | 8 | 8 | 6,704 |
| Nicholas | 128 | not reached by day 1 | not reached by day 1 | not reached by day 1 | 114 |
| Ian | 1,552 | 2 | 10 | 6 | 4,744 |
| Nicole (note) | 103 | – | – | – | – |
| Idalia | 157 | 3 | not reached by day 4 | 3 | 361 |
| Beryl | 1,335 | 3 | not reached by day 5 | not reached by day 5 | 3,142 |
| Debby | 119 | 1 | not reached by day 3 | 2 | 183 |
| Francine | 255 | 1 | not reached by day 2 | 2 | 193 |
| Helene | 4,562 | 3 | 20 | 9 | 22,594 |
| Milton | 1,953 | 3 | not reached by day 4 | not reached by day 4 | 4,771 |
| Isaias | 627 | 2 | not reached by day 2 | not reached by day 2 | 725 |

Note. Nicole: no report after its peak, so no recovery could be observed.

**What it means.** Where it is seen, recovery to half takes from 1 to 7 days. The last stretch to 90% is not observed in 14 of 20 storms if leaving counties are counted as still out, or 9 if they are counted as restored, because the reports stop. The FCC's order FCC 26-34 (adopted May 20, 2026; in effect from its Federal Register publication on June 30, 2026) ended the requirement for providers to file a DIRS final report within 24 hours of deactivation. A time is the first report from which the share restored stays past the threshold in every later report; the true time falls after the report before. Site-days lost (median 2,124, range 58 to 22,594, 20 storms) count only to each storm's last report. These medians, ranges and counts leave out Nicole (note above).

## 5. Why sites go dark

**Claim.** In the FCC's cause columns, loss of commercial power accounts for 59.2% of cell sites out (95% interval 52.5 to 64.6), loss of transport (backhaul) 29.1%, and damage to the site 6.6%, pooled over 17 storms' reports (each site counts once for every report in which it is out). 5.4% have no cause given, and causes exceed sites out by 0.4%, consistent with some sites counted under more than one cause.

**Exhibit.**

[figure:fig-causes]

| Storm | Power % | Transport % | Damage % | No cause given % | Over-attributed % |
|---|---|---|---|---|---|
| Barry | 72.2 | 25.2 | 0.9 | 1.7 | 0.0 |
| Dorian | 61.0 | 30.2 | 5.7 | 4.5 | 1.3 |
| Laura | 35.4 | 53.8 | 6.8 | 4.2 | 0.2 |
| Sally | 54.4 | 37.8 | 4.5 | 3.5 | 0.2 |
| Delta | 46.1 | 13.8 | 37.7 | 3.0 | 0.6 |
| Zeta | 45.9 | 18.5 | 33.9 | 2.0 | 0.3 |
| Ida | 54.6 | 32.4 | 14.8 | 0.3 | 2.1 |
| Nicholas | 37.1 | 35.8 | 27.5 | 0.0 | 0.4 |
| Ian | 57.2 | 36.9 | 5.9 | 0.0 | 0.0 |
| Nicole | 57.6 | 27.1 | 10.8 | 4.4 | 0.0 |
| Idalia | 65.0 | 22.5 | 7.8 | 4.6 | 0.0 |
| Beryl | 80.3 | 5.1 | 0.8 | 13.9 | 0.0 |
| Debby | 41.6 | 13.9 | 6.4 | 40.4 | 2.2 |
| Francine | 85.7 | 7.2 | 2.0 | 5.2 | 0.0 |
| Helene | 59.9 | 32.1 | 1.0 | 7.0 | 0.1 |
| Milton | 68.3 | 23.9 | 1.2 | 6.6 | 0.0 |
| Isaias | 55.2 | 37.2 | 1.8 | 5.8 | 0.0 |

**What it means.** Every share is a share of all sites out, not only of those with a cause. Causes exceeding sites out are read as consistent with sites out for more than one cause, and are not treated as an FCC error. Reports for Idalia (2023) and Beryl (2024) say so: "The number of total cell sites out may differ from the sum of numbers of cell sites out by cause. This is due to sites being out due to multiple causes or because providers are still assessing the causes of some sites being out of service." For other reports that reading is an inference. Harvey, Irma, Florence and Michael print no cause columns; they are left out, not counted as zero. As a check, converted to the attributed-only base of Olukola et al. (2026), who use 23 days of cause data from 24 reports where this page uses 22, this page's Helene shares are damage 1.1%, power 64.4% and transport 34.5%, against their 1.1%, 63.2% and 35.7%.

## 6. The power coupling

**Claim.** Within a storm, county-reports with a higher share of electricity customers without power tend to have a higher share of cell sites out: the median rank correlation across 20 storms is 0.61 (95% interval 0.47 to 0.67). Cell outages line up about as closely with power outages 6 hours earlier (median correlation 0.62) as with power outages at the same time (0.61), and less closely with power outages 24 hours earlier (0.35).

These correlations describe how the share of electricity customers without power and the share of cell sites out move together across county-reports within a storm. Both may follow the storm's path and strength, so the correlation does not show how much one drives the other.

**Exhibit.**

[figure:fig-power-overlay]

[figure:fig-power]

| Storm | Rank correlation (95% interval) | County-reports | EAGLE-I coverage flags |
|---|---|---|---|
| Harvey | 0.45 (0.25 to 0.64) | 220 | coverage unknown 220 |
| Irma | 0.70 (0.59 to 0.79) | 369 | coverage unknown 369 |
| Florence | 0.67 (0.54 to 0.76) | 353 | ok 353 |
| Michael | 0.59 (0.51 to 0.66) | 627 | ok 588, low coverage 39 |
| Barry | 0.48 (0.30 to 0.63) | 130 | low coverage 130 |
| Dorian | 0.55 (0.43 to 0.64) | 257 | ok 257 |
| Laura | 0.41 (0.22 to 0.56) | 512 | ok 263, low coverage 249 |
| Sally | 0.76 (0.58 to 0.84) | 109 | ok 88, low coverage 21 |
| Delta | 0.58 (0.46 to 0.69) | 181 | ok 148, low coverage 33 |
| Zeta | 0.69 (0.61 to 0.75) | 297 | ok 259, low coverage 38 |
| Ida | 0.68 (0.53 to 0.77) | 604 | low coverage 579, ok 25 |
| Nicholas | 0.36 (−0.28 to 0.84) | 22 | ok 18, low coverage 4 |
| Ian | 0.66 (0.52 to 0.75) | 423 | ok 423 |
| Nicole | 0.33 (0.10 to 0.54) | 60 | ok 60 |
| Idalia | 0.39 (0.21 to 0.54) | 128 | coverage unknown 128 |
| Beryl | 0.63 (0.52 to 0.97) | 22 | coverage unknown 22 |
| Debby | 0.41 (0.30 to 0.51) | 275 | coverage unknown 275 |
| Francine | 0.65 (0.47 to 0.76) | 87 | coverage unknown 87 |
| Helene | 0.66 (0.58 to 0.73) | 1,303 | coverage unknown 1,303 |
| Milton | 0.87 (0.81 to 0.91) | 219 | coverage unknown 219 |

Note. Laura's correlation includes its report of 2020-08-25, the combined Marco–Laura report: same-time co-movement of power and cell outages doesn't depend on which storm caused the outage.

**What it means.** EAGLE-I 'customers' are electricity meters, not people or households. EAGLE-I covers 2014-2025, so storms in 2026 (Isaias) have no power match or overlay until a 2026 release exists. Coverage is flagged on every result: "low coverage" means the state's EAGLE-I covered share was below 0.75 that year, and 2017, 2023 and 2024 have no published coverage.

## 7. Exposure

**Claim.** Counties inside a storm's 64-knot winds had a peak of 32.3% of cell sites out (95% interval 26.6 to 38.1); outside its 34-knot winds, 0.7% (95% interval 0.5 to 1.6).

**Exhibit.**

[figure:fig-zone]

[figure:fig-distance]

**What it means.** With wind zone in the model, the intervals for distance and for the storm's intensity include no association (model in the methods). Here a storm's peak share pools each county's own peak report, so it can differ from the single-report peak in chapter 3. Held out of the fit, with misses of 5 percentage points or more listed, storms' pooled peak shares were higher than predicted for Ida (28.4% observed, 9.1% predicted), Helene (13.5% observed, 8.2% predicted) and Irma (27.0% observed, 17.9% predicted); and lower than predicted for Idalia (2.3% observed, 8.1% predicted), Nicholas (2.5% observed, 15.4% predicted) and Nicole (1.2% observed, 10.0% predicted). Flooding, road access and fiber cuts are possible unmeasured factors; this design cannot tell whether they, or something else, account for the gaps.

## 8. Who waits longest

**Claim.** In this data, counties with higher social vulnerability did not take measurably longer for cell outages to fall below 5% of sites. The estimates rule out a large delay for the most vulnerable quartile (a rate of recovery more than 11% slower), though they can't rule out a smaller one. For the most vulnerable quartile, the 95% interval for the hazard ratio runs from 0.90 to 1.46: a rate of falling below 5% more than 11% lower than the least vulnerable quartile's is outside it; a smaller shortfall, or a rate up to 45% higher, is not.

**Exhibit.**

[figure:fig-svi]

| SVI quartile | Storm-counties | SVI range | Median days (95% interval) | Censored | Below 5% by day 3 / 7 / 14 |
|---|---|---|---|---|---|
| Q1 (least) | 204 | 0.013 to 0.615 | 4.9 (4.6 to 5.6) | 46 | 23% / 65% / 88% |
| Q2 | 203 | 0.617 to 0.786 | 4.9 (4.4 to 5.5) | 56 | 25% / 65% / 85% |
| Q3 | 204 | 0.787 to 0.902 | 4.6 (4.1 to 5.1) | 51 | 24% / 71% / 92% |
| Q4 (most) | 202 | 0.903 to 1.000 | 5.1 (4.6 to 5.4) | 45 | 14% / 67% / 90% |

Holding wind zone, distance, track intensity and the storm fixed, the hazard ratios for reaching below 5% (above 1 is sooner) are 0.94 (0.73 to 1.20) for the second quartile, 1.21 (0.95 to 1.54) for the third and 1.14 (0.90 to 1.46) for the most vulnerable.

Day 0 was redefined twice after results were seen (methods). The second- to fourth-quartile hazard ratios were 0.97 (0.76 to 1.24), 1.22 (0.97 to 1.55), 1.16 (0.91 to 1.47) under the original rule (earliest landfall nearest a county); 0.96 (0.75 to 1.23), 1.22 (0.96 to 1.55), 1.16 (0.91 to 1.48) under the first correction (first study-state landfall or closest approach). The headline's wording is the same under all three rules; only its bound moves: "more than 10% slower" under the original rule and "more than 9% slower" under the first correction, and "more than 11% slower" now.

**What it means.** Associations only: these results describe how long counties in each SVI quartile took to fall below 5% of sites out. They do not show why, and say nothing about anyone's intent. What the data can't rule out:

- SVI is correlated with rurality, terrain and network density; any of these, or other differences between counties, may be associated with both SVI and restoration times.
- Public DIRS tables combine all providers, so differences between providers' networks in different counties cannot be seen.
- Counties that leave the reports while still out are censored; if leaving the reports differs by SVI quartile, the comparison can shift (see the best and worst cases).
- Wind zone, distance and track-point wind do not capture flooding, road access or fiber cuts.

Sensitivity display, not a finding: if counties that leave the reports while still out are counted as having fallen below 5% at their next unreported report, the third and fourth quartiles reach it sooner (hazard ratios 1.35 [1.07, 1.71] and 1.32 [1.06, 1.65]). The difference disappears if those counties are instead kept at risk to the storm's last report (1.04 [0.84, 1.29] and 1.02 [0.81, 1.29]).

## 9. Did the rules help?

**Claim.** The public reports can't yet show whether the FCC's 2024–2025 rules coincided with any change in recovery: one rule period has no storm, another has only Isaias, and the sites-served counts shift within storms by as much as 31%.

**Exhibit.**

| Storm | Period | Peak % out | Days to 50% | Days to 90% (still out) | Days to 90% (restored) | Site-days lost | Strongest wind at nearest track point (kt) | Counties inside 64 kt |
|---|---|---|---|---|---|---|---|---|
| Harvey | P0 | 4.7 | 4 | not reached by day 7 | not reached by day 7 | 1,474 | 115 | 5 |
| Irma | P0 | 27.4 | 3 | not reached by day 7 | not reached by day 7 | 13,145 | 103 | 21 |
| Florence | P0 | 10.7 | 3 | 7 | 6 | 3,533 | 90 | 11 |
| Michael | P0 | 18.8 | 2 | 12 | 11 | 4,706 | 140 | 20 |
| Barry | P0 | 1.7 | 1 | not reached by day 1 | not reached by day 1 | 58 | 65 | 4 |
| Dorian | P0 | 3.4 | 1 | not reached by day 1 | not reached by day 1 | 187 | 115 | 7 |
| Laura | P0 | 1.6 | 7 | not reached by day 12 | not reached by day 12 | 3,833 | 130 | 9 |
| Sally | P0 | 17.1 | 1 | 3 | 3 | 481 | 95 | 2 |
| Delta | P0 | 5.6 | 2 | not reached by day 4 | 3 | 1,396 | 90 | 4 |
| Zeta | P0 | 10.3 | 2 | not reached by day 3 | 2 | 2,774 | 100 | 15 |
| Ida | P0 | 28.1 | 2 | 8 | 8 | 6,704 | 130 | 12 |
| Nicholas | P0 | 2.4 | not reached by day 1 | not reached by day 1 | not reached by day 1 | 114 | 65 | 2 |
| Ian | P0 | 10.9 | 2 | 10 | 6 | 4,744 | 135 | 16 |
| Nicole (note) | P0 | 0.9 | – | – | – | – | 65 | 2 |
| Idalia | P0 | 1.9 | 3 | not reached by day 4 | 3 | 361 | 113 | 3 |
| Beryl | P1 | 28.7 | 3 | not reached by day 5 | not reached by day 5 | 3,142 | 78 | 3 |
| Debby | P1 | 0.9 | 1 | not reached by day 3 | 2 | 183 | 70 | 2 |
| Francine | P1 | 9.3 | 1 | not reached by day 2 | 2 | 193 | 90 | 3 |
| Helene | P1 | 12.1 | 3 | 20 | 9 | 22,594 | 120 | 25 |
| Milton | P1 | 12.3 | 3 | not reached by day 4 | not reached by day 4 | 4,771 | 105 | 8 |
| Isaias | P3 | 15.5 | 2 | not reached by day 2 | not reached by day 2 | 725 | 97 | 3 |

| Rule period | Storms | Peak % out | Days to 50% | Days to 90% (still out) | Days to 90% (restored) | Site-days lost | Strongest wind (kt) |
|---|---|---|---|---|---|---|---|
| P0: neither rule (DIRS activated before May 1, 2024) | 15 | 5.6 (0.9 to 28.1) | 2 (1 to 7; 1 censored) | no median (censored) (3 to 12; 9 censored) | no median (censored) (2 to 11; 6 censored) | 2,124 (58 to 13,145) | 103 (65 to 140) |
| P1: MDRI in force, DIRS voluntary (May 1, 2024 to February 19, 2025) | 5 | 12.1 (0.9 to 28.7) | 3 (1 to 3) | no median (censored) (20 to 20; 4 censored) | no median (censored) (2 to 9; 2 censored) | 3,142 (183 to 22,594) | 90 (70 to 120) |
| P2: MDRI and mandatory DIRS (February 20, 2025 to June 29, 2026) | 0 | no storm | no storm | no storm | no storm | no storm | no storm |
| P3: MDRI and mandatory DIRS as modified by FCC 26-34 (from June 30, 2026) | 1 | 15.5 (Isaias) | 2 (Isaias) | not reached (Isaias) | not reached (Isaias) | 725 (Isaias) | 97 (Isaias) |

Note. Nicole: no report after its peak, so no recovery could be observed. It is counted in the peak and wind columns only.

Medians, with the range of observed values in parentheses; censored storms are counted separately, and a median is given only when censoring cannot change it.

The plan's red flags (any one rules out the plan's "coincided with" wording for the rule periods):

- **Dropping any one storm reverses the order of the periods: triggered.** Dropping Isaias leaves P3 with no storm.
- **The order depends on 50% versus 90%, or on the treatment of censoring: triggered.** A median cannot be given for every period for time to 90% (leaving counties still out) and time to 90% (leaving counties restored).
- **Recovery was already shortening across P0: not triggered.**
- **Sites-served counts jump at a rule date, or move more than 10% within a storm: triggered.** Ida: sites served over its always-listed counties moves by 12%; Helene: sites served over its always-listed counties moves by 31%; Michael: sites served over its always-listed counties moves by 13%; Zeta: sites served over its always-listed counties moves by 15%.
- **Activations end sooner, or with more sites still out, in one period: not triggered.**
- **Wind or peak outage has no overlap across periods: not triggered.**

**What it means.** At least one of the plan's red flags is triggered, so this chapter makes no statement about whether recovery changed after the rules. It shows each storm and each period's median and range, and lists the flags. With few storms per period, this is association, not proof. Rule periods: MDRI from May 1, 2024; mandatory DIRS from February 20, 2025 (DA 25-74); FCC 26-34's changes from June 30, 2026 (Federal Register publication). Checked 2026-11-22.

## 10. What the public record misses

*Exploratory: added after version 1 of this page was published.*

**Claim.** In all 21 storms, the FCC's last public report still showed cell sites out: 1,883 in total.

Still out in the FCC's last report: a median of 9.0% of the storm's peak sites out (20 storms). Upper bound, if every county that left the reports while still out had stayed out: a median of 16.9%.

**Exhibit.**

| Storm | Last report | Sites still out | Peak sites out | Share of peak still out | Counties still out, of those listed | Upper bound: if every county that left the reports while still out had stayed out (share of peak) |
|---|---|---|---|---|---|---|
| Harvey | 2017-09-05 | 70 | 365 | 19.2% | 10 of 13 | 113 (31.0%) |
| Irma | 2017-09-18 | 437 | 3,973 | 11.0% | 41 of 67 | 465 (11.7%) |
| Florence | 2018-09-24 | 57 | 1,278 | 4.5% | 19 of 48 | 76 (5.9%) |
| Michael | 2018-10-26 | 45 | 1,357 | 3.3% | 6 of 21 | 50 (3.7%) |
| Barry | 2019-07-15 | 25 | 90 | 27.8% | 11 of 73 | 25 (27.8%) |
| Dorian | 2019-09-07 | 91 | 281 | 32.4% | 22 of 64 | 112 (39.9%) |
| Laura | 2020-09-08 | 91 | 513 | 17.7% | 5 of 5 | 231 (45.0%) |
| Sally | 2020-09-21 | 21 | 454 | 4.6% | 4 of 13 | 23 (5.1%) |
| Delta | 2020-10-14 | 28 | 674 | 4.2% | 6 of 9 | 238 (35.3%) |
| Zeta | 2020-11-01 | 68 | 1,555 | 4.4% | 15 of 20 | 874 (56.2%) |
| Ida | 2021-09-20 | 16 | 1,824 | 0.9% | 6 of 12 | 64 (3.5%) |
| Nicholas | 2021-09-16 | 101 | 128 | 78.9% | 12 of 14 | 101 (78.9%) |
| Ian | 2022-10-10 | 21 | 1,552 | 1.4% | 3 of 3 | 158 (10.2%) |
| Nicole | 2022-11-11 | 103 | 103 | 100.0% | 20 of 34 | 103 (100.0%) |
| Idalia | 2023-09-04 | 8 | 157 | 5.1% | 4 of 13 | 69 (43.9%) |
| Beryl | 2024-07-14 | 207 | 1,335 | 15.5% | 3 of 3 | 219 (16.4%) |
| Debby | 2024-08-09 | 37 | 119 | 31.1% | 15 of 75 | 83 (69.7%) |
| Francine | 2024-09-14 | 18 | 255 | 7.1% | 10 of 30 | 33 (12.9%) |
| Helene | 2024-10-19 | 23 | 4,562 | 0.5% | 8 of 16 | 434 (9.5%) |
| Milton | 2024-10-14 | 341 | 1,953 | 17.5% | 31 of 52 | 341 (17.5%) |
| Isaias | 2026-10-12 | 75 | 627 | 12.0% | 11 of 44 | 75 (12.0%) |

Note. Nicholas: its 2 reports are shared with Ida, so its record is short.

Note. Nicole: its last report is its peak, so the share still out is 100% by construction.

**Sensitivity.** Without reports carrying a serious validation flag: Harvey's last report without a serious flag is 2017-09-02, with 193 sites out (52.9% of its peak). Irma, Barry, Nicholas and Francine cannot be shown, because every one of their reports carries a serious flag. Every other storm is unchanged.

**What it means.** "Still out in the FCC's last report" counts sites at the moment the public reporting stopped; it does not say how long they stayed out afterwards. The FCC's order FCC 26-34 (adopted May 20, 2026; in effect from its Federal Register publication on June 30, 2026) ended the requirement for providers to file a DIRS final report within 24 hours of deactivation. The upper bound assumes every county that left the reports while still out stayed out, which the reports cannot confirm.

## 11. Sites on backup power

*Exploratory: added after version 1 of this page was published.*

**Claim.** The FCC printed sites operating on backup power for 11 of 21 storms: in every report for Ian, Nicole, Idalia, Beryl, Debby, Francine, Helene, Milton and Isaias, and in one report each for Laura and Delta. It did not print them for Harvey, Irma, Florence, Michael, Barry, Dorian, Sally, Zeta, Ida and Nicholas.

**Exhibit.**

| Storm | Reports with backup power | Most sites on backup power in one report | Report (days since 34-kt winds arrived) | Sites served in the counties reporting it | Share of those sites served |
|---|---|---|---|---|---|
| Ian | 13 of 13 | 527 | 2022-09-29 (day 1.6) | 14,188 | 3.7% |
| Nicole | 2 of 2 | 126 | 2022-11-10 (day 1.7) | 11,162 | 1.1% |
| Idalia | 6 of 6 | 162 | 2023-08-31 (day 1.7) | 8,268 | 2.0% |
| Beryl | 6 of 6 | 490 | 2024-07-09 (day 1.5) | 4,656 | 10.5% |
| Debby | 5 of 5 | 221 | 2024-08-06 (day 2.0) | 13,465 | 1.6% |
| Francine | 3 of 3 | 215 | 2024-09-12 (day 0.9) | 2,731 | 7.9% |
| Helene | 22 of 22 | 1,990 | 2024-09-28 (day 2.6) | 37,717 | 5.3% |
| Milton | 5 of 5 | 716 | 2024-10-11 (day 1.9) | 15,878 | 4.5% |
| Isaias | 3 of 3 | 469 | 2026-10-11 (day 1.9) | 4,088 | 11.5% |

Note. Laura: its one report with backup power prints it for 3 of 38 counties, so it is left out of comparisons.

Note. Delta: its one report with backup power prints it for 19 of 110 counties, so it is left out of comparisons.

Note. Laura's report of 2020-08-25, kept off Laura's timeline (the combined Marco–Laura report), also prints backup power for 52 counties, with 0 sites on backup power.

**Sensitivity.** With every county in the report as the denominator (printed value or not): Laura 1.8%; Delta 0.7%. Every other storm prints the column for all its counties, so its share is unchanged.

**What it means.** These are sites operating on backup power as the FCC reports them; they say nothing about how long backup lasts or what followed. Counts come first: a share can rise when the reporting area narrows even as the count falls. The column was printed only for the storms named above, so the storms are not compared across rule periods.

## 12. Which comes back first: power or cell service?

*Exploratory: added after version 1 of this page was published.*

**Claim.** Where the order could be determined (351 of 499 counties, as defined), cell outages fell below 5% first in 158 counties and power outages first in 66; in 127 both fell below 5% in the same report. Where both fell below 5% (296 counties), the median gap is 0 days. For the other 148 counties (29.7%, 95% interval 16.6% to 47.6%), the order can't be determined because a county left the reports, or its power record ended, first.

The two thresholds are on different scales: cell's 5% is of sites served, and power's 5% is of EAGLE-I meters, so "cell first" doesn't mean phone service returned before household power.

**Exhibit.**

| Order | Counties | Share (95% storm-bootstrap interval) |
|---|---|---|
| Power fell below 5% first | 66 | 13.2% (5.7% to 18.8%) |
| Same report | 127 | 25.5% (22.0% to 30.6%) |
| Cell fell below 5% first | 158 | 31.7% (21.4% to 41.0%) |
| Undetermined (censoring) | 148 | 29.7% (16.6% to 47.6%) |

| Sensitivity display | Counties (storms) | Power first | Same report | Cell first | Undetermined |
|---|---|---|---|---|---|
| Both thresholds at 10% | 353 (18) | 13.9% | 20.1% | 48.2% | 17.8% |
| First crossing instead of staying below | 499 (19) | 12.4% | 26.3% | 32.9% | 28.5% |
| Without low- and unknown-coverage EAGLE-I counties | 219 (9) | 11.9% | 26.0% | 27.4% | 34.7% |
| Without reports with a serious flag | 296 (15) | 12.5% | 21.6% | 27.0% | 38.9% |

By rule period, shown and not compared: P0: 335 counties in 14 storms; power first 11.3%, same report 24.5%, cell first 32.8%, undetermined 31.3%; P1: 164 counties in 5 storms; power first 17.1%, same report 27.4%, cell first 29.3%, undetermined 26.2%.

**What it means.** Factors this data doesn't measure, any of which could bear on the order: portable cell sites brought in after the storm, generators placed at cell sites, service carried by other networks (roaming), the order in which crews restore lines and repairs to the network connections that link sites (backhaul). Storms without EAGLE-I data (Isaias) are not included, and Nicholas has no county at or above 5% of sites out. "Same report" means within one report interval, not at the same moment.

## 13. Do counties with more mobile providers recover differently?

*Exploratory: added after version 1 of this page was published.*

**Claim.** In storms from 2022 on, counties served by more mobile providers did not show a consistent difference in how long cell outages took to fall below 5% of sites. One grouping suggests a faster fall for counties with four or more providers, but that association does not hold when the count is used directly or when flagged reports are left out, and some other coverage measures point the other way.

Provider counts describe reported coverage (mobile providers covering at least half the county's area, in the FCC's Broadband Data Collection release before the storm), not which networks were out. No provider is named.

**Exhibit.**

| Mobile providers covering at least half the county's area | Storm-counties (all) | Storm-counties at risk | Median days to stay below 5% (95% interval) | Censored | Hazard ratio (95% interval; above 1 = sooner) |
|---|---|---|---|---|---|
| 2 or fewer | 228 | 127 | 5.6 (4.6 to 9.6 days) | 37 | reference |
| 3 | 386 | 156 | 4.6 (4.6 to 5.6 days) | 37 | 1.14 (0.85 to 1.54) |
| 4 or more | 174 | 50 | 4.6 (3.6 to 6.5 days) | 7 | 1.50 (1.01 to 2.23) |

| Sensitivity display | Hazard ratios (95% interval) |
|---|---|
| Provider count as a number | per provider: 1.06 (0.92 to 1.22) |
| Mobile, any coverage, count as a number | per provider: 0.70 (0.55 to 0.88) |
| Including storms before 2022 (network data from after the storm) | 3 providers: 1.08 (0.89 to 1.31); 4 or more providers: 1.36 (1.03 to 1.80) |
| Without reports with a serious flag | 3 providers: 1.12 (0.70 to 1.81); 4 or more providers: 1.15 (0.67 to 2.00) |
| Fixed, any service, near-universal providers excluded | 5 to 6 providers: 0.91 (0.62 to 1.32); 7 or more providers: 0.65 (0.45 to 0.95) |
| Fixed, any service | 10 to 11 providers: 0.94 (0.66 to 1.34); 12 or more providers: 0.66 (0.45 to 0.96) |
| Fixed, at least half of locations | 5 providers: 1.15 (0.81 to 1.63); 6 or more providers: 1.02 (0.71 to 1.45) |
| Fixed, at least half of locations, near-universal providers excluded, count as a number | per provider: 0.80 (0.68 to 0.94) |

Groups were fixed from the counts alone, before any recovery data was joined: whole values as close to thirds as ties allow, no group under 20% of storm-counties. Fixed broadband is shown only as sensitivity displays; rows marked "near-universal providers excluded" leave out near-universal providers (likely satellite or national fixed-wireless; this file doesn't identify technology). The hazard model covers 8 of the 9 storms (262 counties); a storm whose effect cannot be estimated stays in the raw table. Every main storm's release is within 12 months before its day 0, so the planned 'release within 12 months' display would equal the main analysis.

**What it means.** Association only: these counts describe reported coverage before the storm, not which networks were out or how they were restored.

## Look up a county

Choose any of the 814 counties in the FCC's reports to see each storm's share of the county's cell sites out, report
by report, by days since the storm's 34-knot winds first reached a study-state county. Points are the FCC's reports;
lines join only consecutive reports of that storm at most 1.5 days apart, so a missing or excluded report leaves a gap. Built in the browser from the published data, with nothing loaded
from any other site. Laura's report of 2020-08-25 (the combined Marco–Laura report) is left off Laura's line.

<div class="county-lookup" data-src="/static/data/hurricane-county-lookup.json">
<label for="county-lookup-select">County</label>
<select id="county-lookup-select" disabled><option value="">Loading counties…</option></select>
<p class="county-lookup-status" role="status" aria-live="polite"></p>
<div class="county-lookup-panels"></div>
<details class="fig-data"><summary>View data table</summary><div class="table-scroll county-lookup-table"></div></details>
<noscript><p>The lookup needs JavaScript. The same data is in the <a href="/static/data/hurricane-dirs-county-day.csv">county-report panel
(CSV)</a>.</p></noscript>
</div>
<script src="/static/js/hurricane-county-lookup.js" defer></script>

## Methods, data and licenses

**Reading the reports.** Each FCC report is read from its text file or, when that is incomplete, its PDF, and every county row is checked against a second reading of the PDF. County rows must sum to the report's printed totals; a report that fails after one round of parser fixes is excluded with its reason. Counties are mapped to FIPS codes with a checked exception list. The storm key is the NHC ID plus the DIRS activation date.

**Times and censoring.** A county or storm reaches a threshold at the first report from which it stays past it in every later report that includes it; the true time lies after the report before. A county that leaves the reports while still out is censored, not recovered. Days count from day 0: the first time the storm's 34-knot (tropical-storm-force) winds reach any study-state county in its reports, from the NHC best-track wind radii. Every storm has 34-knot radii at that time, so none uses the fallback (its first landfall in the study states).

**Exposure model (chapter 7), checked for calibration.** A binomial model of each county's peak share of sites out on wind zone, distance to the track and the storm's intensity at the nearest track point, with storm-clustered intervals. Odds ratios: inside 64-knot winds 47.9 (20.7 to 111.1), 50-64 knots 23.0 (11.7 to 45.3), 34-50 knots 7.5 (4.4 to 12.8), log distance 0.87 (0.68 to 1.12), per 10 knots 1.07 (0.90 to 1.28). Calibration on storms held out of the fit one at a time: slope 0.87 (0.48 to 1.26; 1 is ideal), calibration-in-the-large −0.01 (−0.35 to 0.33; 0 is ideal), mean absolute error 9.2 percentage points.

| Decile of predicted share | Storm-counties | Mean predicted % | Observed % |
|---|---|---|---|
| 1 | 215 | 0.6 | 1.2 |
| 2 | 215 | 0.8 | 0.5 |
| 3 | 215 | 1.7 | 7.7 |
| 4 | 215 | 4.0 | 4.6 |
| 5 | 215 | 4.9 | 5.4 |
| 6 | 215 | 5.4 | 4.5 |
| 7 | 215 | 6.1 | 2.3 |
| 8 | 215 | 10.1 | 10.8 |
| 9 | 215 | 16.8 | 13.6 |
| 10 | 215 | 30.9 | 30.3 |

[figure:fig-calibration]


**Waiting-time model (chapter 8).** A discrete-time hazard with a complementary log-log link over the intervals between a county's reports (interval censoring), with exposure, storm fixed effects and county-clustered intervals: 2,761 intervals, 605 events, 465 counties, 18 storms (two storms whose fixed effect cannot be estimated stay in the raw tables). The worst-case sensitivity display is fitted by Newton's method because the default fitter (IRLS) did not converge; the model and its likelihood are the same. SVI quartiles are of the at-risk storm-counties' national percentiles; on the national cut points only 19 storm-counties fall in the lowest quartile.

**Sensitivity displays.** Each chapter's results in `results.json` include the plan's sensitivity displays: dropping one storm at a time; holding each county's sites served at its peak value; best and worst cases for censored counties; with and without low-coverage EAGLE-I counties; with and without flagged reports, and without reports with a serious flag; without the report kept by the state_total_missing rule; and EAGLE-I with a missing record treated as zero.

**What the FCC's numbers measure.** Each FCC report carries this caveat: "The number of cell site outages in a specific area does not necessarily correspond to the availability of wireless service to consumers in that area." So the counts here describe the network, not how many people lost service.

**EAGLE-I denominators.** EAGLE-I's modeled customer count is below EAGLE-I's own recorded outages in 230 of 2,106 storm-counties (for example, Henderson County, North Carolina: 24 modeled customers, 131,460 customers out, 49,494 households). Those storm-counties are left out of every % of customers result; using households as the denominator instead is shown as a sensitivity.

**Mobile and fixed providers (chapter 13).** Provider counts come from the FCC's Broadband Data Collection public data (National Broadband Map, "Provider Summary by Geography Type"), downloaded through the FCC's Public Data API with an account and token, at most one call every 6.5 seconds (the API allows 10 per minute). Each storm uses the latest release on or before its day 0. The files are the FCC's current revisions of those releases (the 2022-06-30 release revised May 10, 2024; the 2023-06-30 release revised December 24, 2025; the 2024-06-30 release revised July 27, 2026; the 2026-06-30 release revised November 10, 2026), so the counts include the FCC's later corrections. Only counts are kept: no provider is named or identified.

**Validation.** Every in-scope report was checked against its own printed totals: 134 flagged, 36 ok, 7 excluded, 1 known FCC inconsistency. Flags on the reports used, by type (a report can carry several):

| Flag | Kind | Reports |
|---|---|---|
| County rows in the table but not in the report's list | serious | 34 |
| Stated headline differs from the computed share (computed used) | serious | 11 |
| County rows outside the FCC notice's area | serious | 10 |
| No totals printed (every row confirmed) | serious | 3 |
| One state printed no total (its rows all confirmed) | serious | 1 |
| Causes short of sites out (some sites with no cause) | benign | 84 |
| Causes exceed sites out (confirmed in the PDF) | benign | 35 |
| County name spelling variant | benign | 31 |
| County listed twice in the report's list | benign | 22 |
| County not in the list (checked exception) | benign | 3 |
| Known FCC inconsistency in the headline | benign | 1 |
| Causes exceed sites out (checked exception) | benign | 1 |

The known FCC inconsistency: Helene, 2024-10-01 (DOC-406055A1), whose headline states 21.7% of sites out against 14.49% computed from its own totals; the computed share is used.

Each report's flags and reasons are in the snapshot's [`output/validation_dirs.csv`](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/hurricane_resilience/output/validation_dirs.csv). Excluded reports:

| Report | Storm | Date | Reason |
|---|---|---|---|
| DOC-346478A1 | Harvey | 2017-09-03 | Texas rows broken across lines in both the .txt and the PDF (Matagorda, San Patricio not confirmed); no Texas total |
| DOC-347137A1 | Nate | 2017-10-09 | No headline percent printed (and no totals) |
| DOC-366519A1 | Laura | 2020-08-28 | San Augustine, Texas row not confirmed by the second reading |
| DOC-366524A1 | Laura | 2020-08-29 | Maryland served does not reconcile (5,521 vs 6,522 printed); San Augustine not confirmed; names with backquotes not matched |
| DOC-366526A1 | Laura | 2020-08-30 | San Augustine, Texas row not confirmed by the second reading |
| DOC-406144A1 | Helene | 2024-10-03 | FCC inconsistency: Hamilton row prints transport 0, Florida total prints 1 |
| DOC-406197A1 | Helene | 2024-10-04 | Washington County, Tennessee row not confirmed by the second reading |

**Deviations from the analysis plan**, each logged in `docs/decisions.md` before it was run:

- *2026-11-22.* DEVIATION from the plan (Validation: 'every report in scope must pass step 4 ... a failure stops the build'): the 7 reports in manifest/excluded_reports.csv are not used in steps 9-10, and the build does not stop on them. Nate's only report is among them, so Nate has no chapter 3 row; Laura loses Aug 28-30, 2020 and Harvey Sep 3, 2017. Each storm's results say which of its reports were excluded (The stopping rule of 2026-11-22 (one round of parser fixes, then exclude with reason). Logged before running step 9)
- *2026-11-22.* DEVIATION (Scope and keys: days since landfall): Isaias 2026's GIS best track has no landfall marker, so its reference time is the track time closest to the nearest of its study counties, flagged landfall_source = 'closest approach (no landfall marker)'. For every other storm the reference is the earliest HURDAT2 landfall that is the nearest landfall to at least one of its counties (so Harvey's Barbados landfall is not used) (No landfall time exists for Isaias in the approved sources. Logged before running) *Superseded: day 0 is now the first time 34-knot winds reach a study-state county (2026-11-23 corrections).*
- *2026-11-22.* DEVIATION (Unit: each report's as-of time): Laura's Sep 1, 2020 report prints no as-of time; for the time axis it is placed at 12:00 Eastern on its report date and flagged as_of_imputed. It is not used for EAGLE-I matching (already no_as_of_time) (One report of 167; noon is the most common printed time. Logged before running)
- *2026-11-22.* DEVIATION, made AFTER seeing the chapter 3 result: the flagged-reports display (plan item 5) dropped the peak day of most storms and left 9 storms, so it says little. Added display 5b, which drops only reports with a serious flag; item 5 is kept as well. Serious: headline_mismatch, state_total_missing, no_printed_totals, outside_notice_area, table_not_in_list. Benign: causes short of sites out, spelling variants (FCC spelling, inside_spelling_variant), over-attribution confirmed by the second reading. Also classified: 'in table, not in the report's county list' = serious (the names check's form of table_not_in_list); 'listed more than once by the FCC' = benign; entries on the checked exception lists (cause, county-list and headline) = benign. An unknown flag type stops step 10 (Decided after seeing chapter 3; disclosed as such)
- *2026-11-22.* DEVIATION (reporting rules: 'longer gaps are never interpolated'): site-days lost, from the peak to the storm's last report, is the trapezoid sum of the main curve, with bounds from holding each snapshot's value until the next (upper) and taking the next value early (lower). Across a gap longer than one day the value is the midpoint of those bounds, not a drawn curve, and each storm reports its number of such gaps. Site-days after the last report are not counted, so this is a lower bound on the storm's total (A sum over time needs a rule between snapshots; the bounds carry the uncertainty. Logged before running)
- *2026-11-22.* DEVIATION (Power: 'use the coverage and modeled-customer files'): EAGLE-I's modeled customer counts (MCC.csv) are below EAGLE-I's own recorded customers out in 127 counties of the panel (e.g. Henderson County, NC: 24 modeled customers, 71,171 out, 49,494 households; Buncombe, NC: 32,499 modeled, 104,956 out), and one MCC row has an 11-digit FIPS. Step 6 now flags each storm-county whose highest customers out in that storm's window exceeds its MCC count (eaglei_mcc_flag = mcc_below_observed_outages, or no_mcc); chapter 6 leaves those out of every % of customers result and says how many. Sensitivity display: ACS 2022 households as the denominator for every county. 'Customers' means meters throughout (A share above 100% cannot be a share of customers; MCC stays the plan's denominator where it is plausible. Found while preparing chapter 6, before any chapter 6 result; logged before running)
- *2026-11-22.* DEVIATION in definition (plan: 'by SVI 2022 quartile', scale not stated): quartiles are of the at-risk storm-counties' SVI 2022 national percentiles (RPL_THEMES, US-ranked), so each holds about a quarter of them. On the national cut points (0.25/0.5/0.75) only 19 of the 813 fall in the lowest quartile; the national-cut version is a sensitivity display. Decided after seeing only these counts, before any chapter 8 outcome (A comparison group of 19 counties would make the hazard ratios unstable. Logged before running)
- *2026-11-22.* DEVIATION (page exhibits): superseded the same day by the new exhibits (next list): the heatmap, map and small-multiple charts on this page replace the tables this deviation planned
- *2026-11-22.* DEVIATION (Validation: 'each reason from validation_dirs.csv stated in the page's methods'): the page gives a table of flag types with the number of reports carrying each, names the known FCC inconsistency (Helene Oct 1, 2024: headline 21.7% stated vs 14.49% computed), and links the per-report reasons in the snapshot's validation_dirs.csv (Independent check, finding 15)

**Decisions on the exhibits**, logged before the charts were built:

- *2026-11-22.* New exhibits: recovery curves for every storm under both bounds (small multiples, with the bootstrap band), a coverage heatmap of every storm's reports by day since landfall, power and cell outages by storm (small multiples), a calibration plot for the exposure model, and an Isaias county map with the best track. Four chart types (multiples, heatmap, calibration, map) are appended to the site's figures.py; the existing types are unchanged and every Medicaid and OSHA figure is snapshot-tested before and after. Ink and Slate for data, Signal only for rule-period markers and the Isaias track; each chart has a title, a text description and a data table. Supersedes the single-series part of the exhibit deviation above for these five exhibits *Superseded: day 0 is now the first time 34-knot winds reach a study-state county (2026-11-23 corrections).*
- *2026-11-22.* The Isaias map draws counties from the Census 2022 cartographic boundary file (1:500,000), simplified at 0.004 degrees and projected equirectangularly at the area's mean latitude; shading uses each county's peak share from results.json, and the track is the NHC GIS best track stored in results.json (chapter 2). The heatmap places each report at its rounded day since landfall, and step 11 stops if two reports of a storm round to the same day (Choices for the new exhibits. Logged before building) *Superseded: day 0 is now the first time 34-knot winds reach a study-state county (2026-11-23 corrections).*

**Corrections**, made after results or an independent check were seen, also logged:

- *2026-11-22.* CORRECTION (medians with censoring, chapters 4 and 9): a median across storms is reported only when it is the same with each censored storm at its censoring time and with it above every time; otherwise 'no median (censored)'. Ranges cover observed times only, with censored storms counted separately. Replaces the earlier rule that placed censored storms above every observed time (which ranked storms censored at day 1 above Michael's 12 days) (Independent check, 2026-11-22, finding 2)
- *2026-11-22.* CORRECTION to the EAGLE-I denominator deviation above: the final counts are 230 of 2,106 storm-counties, and Henderson County, NC's highest customers out in Helene's window is 131,460; the '127 counties' and '71,171' in that entry were counted at matched report times before the flag was made per storm-county (Independent check, 2026-11-22, finding 4)
- *2026-11-22.* CORRECTION to the first chapter 3 deviation above: the excluded reports also remove Helene's Oct 3 and Oct 4, 2024 reports, besides Laura's Aug 28-30, 2020 and Harvey's Sep 3, 2017 (Independent check, 2026-11-22, finding 16)
- *2026-11-22.* CORRECTION to the heatmap entry above: each report is placed at its calendar day since landfall (report date minus the landfall date in Eastern time), not its rounded fractional day, because two Harvey reports rounded to the same day; the stop on a collision stays (Found while building, before the figure was shown) *Superseded: day 0 is now the first time 34-knot winds reach a study-state county (2026-11-23 corrections).*
- *2026-11-23.* CORRECTION (time origin; made after seeing results): day 0 for every storm is the earlier of (a) its first HURDAT2 landfall in the ten study states while at tropical-storm strength or above (status TS or HU; a landfall point counts as in the study states when it lies within 25 km of a study-state county in the Census 2022 cartographic boundary file) and (b) its closest approach to the study-state counties (the track time nearest any county in its reports, by Census Gazetteer internal points). Replaces the earlier rule (earliest landfall nearest to some county), which counted Laura from western Cuba and Dorian from Grand Bahama. Effects: Laura counts from Louisiana; Ian from the Dry Tortugas; Irma from the Florida Keys; Dorian from its closest approach off North Carolina (Sep 6, 2019 09:15 UTC, before its Cape Hatteras landfall), so its Florida reports of Sep 3-5 fall before day 0; Isaias unchanged. Sally's Sep 12, 2020 landfall near Miami was as a tropical depression and is not counted. Chapters 1, 2, 3, 6 and 8 are rerun; chapter 8 also reports its model under the previous origin, and the page shows both if the hazard ratios or headline change (Second independent check, finding 4; the rule's two refinements: rule as written for Dorian, and tropical storm or stronger only) *Superseded by the second time-origin correction below.*
- *2026-11-23.* CORRECTION (Nicole; made after seeing results): Nicole is left out of every time and site-days summary in chapters 4 and 9 (medians, ranges, counts of storms reaching 50% and 90%, drop-one displays and the period red flags that use times), because its last report is its peak and no recovery could be observed. It stays in the peak tables, with the footnote "Nicole: no report after its peak, so no recovery could be observed." (Second independent check, finding 8)
- *2026-11-23.* CORRECTION (time origin, second correction; made after seeing results): the 'closest approach' part of the earlier 2026-11-23 rule was ambiguous. 'closest approach' picks a single moment, which for Dorian is off North Carolina, after Florida had been affected. Day 0 is now the first time the storm's 34-kt wind radii reach any study-state county in its reports: the earliest first_34kt_utc from step 7 (best-track points interpolated to 15 minutes, quadrant radii, Census Gazetteer internal points). Fallback, for a storm with no 34-kt radii reaching a county: its first landfall in the study states (tropical storm or stronger). No storm uses the fallback (every storm has 34-kt radii at that time; no radii are missing near its counties before it). One report still falls before day 0: Laura's Aug 25, 2020 report, the combined Marco and Laura report keyed to Laura, 0.9 days before Laura's 34-kt winds reach a county. Chapters 1, 2, 3, 6 and 8 are rerun; chapter 8 also reports its model under both earlier rules, and the page gives one line on them. Page labels say 'days since 34-kt winds arrived'
- *2026-11-23.* CORRECTION (Laura's Aug 25, 2020 report; made after seeing results): the report (DOC-366394A1) stays in the panel, flagged time_flag = 'pre_onset_likely_marco': it is the FCC's combined report for Marco and Laura, keyed to Laura, and falls 0.9 days before Laura's 34-kt winds reach a study-state county, so its outages are likely Marco's. It is left out of every time-based result: chapter 3 timing, chapter 4, chapter 8 and chapter 9 (those chapters run on the panel without flagged reports). Step 9 stops if any other report falls before day 0 without a flag. Laura's peak and recovery figures are checked to be unchanged
- *2026-11-23.* CORRECTION (rule for time-flagged reports, refining the entry above): Laura's Aug 25, 2020 combined Marco-Laura report stays out of anything that places it on Laura's timeline, with one exception, the coverage heatmap, which shows it as a marked cell; it stays in wherever only same-time comparisons are made. So: out of chapter 3 timing, chapters 4, 8 and 9 (as before) and the chapter 6 power-overlay chart (its day -1 point is dropped); kept in the chapter 1 heatmap (the one exception) as a marked cell, labeled 'combined Marco-Laura report, before Laura's winds arrived'; kept in the chapter 6 power-cell correlations, with a footnote that same-time co-movement doesn't depend on which storm caused the outage. Laura's note in chapter 3 states the rule.
- *2026-11-23.* CORRECTION (V2-1 page text; made after seeing results): the headline covers every storm (21 storms and 1,883 sites still out; it had covered 19 storms and 1,679 sites, leaving out Nicholas and Nicole), and the median (9.0%) and the upper bound (16.9%) leave out only Nicole, whose share is 100% by construction (the chapter 4 rule), keeping Nicholas with its footnote: 20 storms (correction of an ambiguous instruction)
- *2026-11-23.* CORRECTION (V2-3 wording in chapter 12 and the opening; made after seeing results): the earlier sentence ('the share of cell sites out more often fell below 5% before, or in the same report as, the share of customers without power') grouped the 127 same-report counties with 'cell first'; grouped the other way the claim reverses. Now count-based: cell first 158, power first 66, same report 127, of the 351 counties where the order could be determined; the median gap where both fell below 5% (296 counties) is 0 days (Final independent check, finding 4)
- *2026-11-23.* CORRECTION (chapter 5 not rerun after the day-0 correction; found by the public repository's reproduction test): chapter 5's per-report timeline (chapter_5 > storms > by_report > days_since_landfall, 124 values) still used day 0 under the original rule, because only chapters 3, 4, 8 and 9 were rerun when day 0 was corrected on 2026-11-23. Chapter 5 rerun under the current day 0: those 124 values change and nothing else in results.json does (checked field by field). No page text, table or figure uses them (chapter 5 shows pooled cause shares only), so no number, table or figure on the page changes; this entry is the only addition. The v1 fingerprint for chapter_5 is updated; every other v1 key keeps its fingerprint. Version 1 result changed with approval

**Seen before the plan was committed.** The analysis plan was committed on November 22, 2026, in the project's private version-controlled repository (commit 9fc17a4), before any recovery outcome was computed. The plan file as committed is published in the data repository with its SHA-256, so it can be checked against later changes. It is not blind to some figures, as listed below. From the plan:

> This plan was drafted, and revised, after outcome figures had been seen. **It is not blind to the reports below.** These were seen during data preparation and validation:
> - **Isaias, Oct 12, 2026:** every county row, all totals, the subscriber count, and the prior day's overall and state percents (so the one-day recovery).
> - **Michael, Oct 20, 2018:** every county row, the total, the subscriber count, the prior day's percent, and the four-day fall from 12.7% to 5.5%.
> - **Helene, Sep 30, Oct 1, 2 and 6, 2024:** every state total with causes and backup power, headlines, subscriber counts, prior-day percents (so the state recovery paths from Sep 29 to Oct 6), and some county rows.
> - **Debby, Aug 5, 2024, and Ian, Sep 28, 2022:** totals with causes, headlines, subscriber counts, and some county rows.
> - **Fiona, Sep 24 and 26, 2022 (out of scope):** totals, headlines, subscriber counts, and some county rows.
> - **All reports with cause columns:** how many rows and sites had no cause, and the largest gaps.
> - **Secondhand:** news and search summaries of Isaias outages (about 18% of sites out in Florida, 17% in Alabama, over 600 sites); a 3.6% Connecticut figure for Isaias 2020; the span of report dates for several 2017–2024 storms, which hints at recovery length; Helene's 4,562 sites out on Sep 28, 2024 and the pooled cause shares in Olukola et al. (both in the project docs).
> - **Storm strength:** landfall category for Michael and Isaias, and wind speed for Isaias.
> - **Not seen (when the plan was first committed):** EAGLE-I, SVI or county exposure data, any computed recovery time, and county tables from any other report.
> - **Seen after the plan was committed, before chapter 3 was computed (added 2026-11-22):** during data preparation and validation (steps 3-8), these were seen: every report's parsed county rows and totals, step 4's console output with each report's computed and stated overall % out (so each storm's day-by-day overall % out), the validation summaries (status by storm; cause-gap counts), Helene's Sep 28 rows summing to 4,562 sites out, EAGLE-I match rates and state coverage by storm, the count of counties inside each storm's 34- and 64-kt radii and the median distance to track, FEMA declared-county counts by storm, and Michael's 261 sites served in Jefferson County, FL. Not seen: any computed peak by storm as defined in ch. 3, recovery times, site-days lost, cause shares by day, the power coupling, or any SVI breakdown.
> - **The author, Timothy D. Spivey, in his own words:** "The author works in telecommunications operations on the Gulf Coast, has general professional familiarity with storm restoration from that work, and lived through several of these storms locally. No non-public or employer data was used in this project. Beyond the items listed above, the author has seen only what was reported during data preparation and validation: the full Isaias Oct 12 county table, the cause-gap counts for the ten validation reports, and the report date range for each storm, which hints at how long recovery took."

**Data and licenses.** The cleaned county-report panel (DIRS fields only, with `out_unattributed` and `out_overattributed` kept apart) is published under CC BY 4.0: [download the CSV](/static/data/hurricane-dirs-county-day.csv). The code is MIT-licensed. FCC DIRS reports and NHC tracks are public. EAGLE-I is CC BY 4.0 ([doi:10.1038/s41597-024-03095-5](https://doi.org/10.1038/s41597-024-03095-5); dataset [doi:10.6084/m9.figshare.24237376](https://doi.org/10.6084/m9.figshare.24237376); 2025 release [doi:10.13139/ORNLNCCS/3012826](https://doi.org/10.13139/ORNLNCCS/3012826)); its "customers" are electricity meters. CDC/ATSDR SVI 2022, Census ACS 2022 and the Census 2022 cartographic boundary file (map only; [https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip](https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip), downloaded 2026-11-23) are public with attribution. FEMA OpenFEMA Disaster Declarations Summaries v2 (https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries), accessed 2026-11-23 01:14:00–01:14:43 UTC (November 22, 2026, 8:14 p.m. Eastern): This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s). The published panel keeps a column for whether a county had a FEMA declaration for that storm, as context for reuse; no result on this page uses it. poweroutage.us is not used. The Olukola et al. (2026) dataset is used only as a check and is not redistributed. FCC Broadband Data Collection public data (National Broadband Map, [https://broadbandmap.fcc.gov/data-download](https://broadbandmap.fcc.gov/data-download)) were obtained through the FCC's Public Data API under the FCC API terms of service accepted for the account, and are used for provider counts only; no provider is named and the files are not redistributed. The map is drawn with D3 and topojson-client (ISC licence), served from this site. Code was written with the help of an AI coding assistant; every number on this page is generated by that code from public data and was checked independently against its sources. Independent analysis using public data. Views are my own and not those of any employer.

**Disclosure.** The author works in the telecommunications industry. This analysis was done independently, on personal time, using only publicly available government data. It uses no employer data or confidential information, and the views are the author's alone. The author has no financial interest in any FCC proceeding.

## Related work

- Olukola, O., Addeh, O. D., Konan, E. A., & Rahimi, N. (2026). The towers were standing: A cause decomposition of cellular outages during Hurricane Helene. arXiv:2609.10944. A cause decomposition of Helene's cell-site outages from the same FCC reports; this page uses it as a check on chapter 5.
- U.S. Government Accountability Office (2017). Telecommunications: FCC should improve monitoring of industry efforts to strengthen wireless network resiliency (GAO-18-198).
- U.S. Government Accountability Office (2021). Telecommunications: FCC assisted in Hurricane Maria network restoration, but a clarified disaster response role and enhanced communication are needed (GAO-21-297).
- Federal Communications Commission, Public Safety and Homeland Security Bureau (2018). 2017 Atlantic Hurricane Season Impact on Communications: Report and Recommendations (DOC-353805A1).
- Peskin, A. H. (2025). Cellular network outage reporting and restoration during disasters (CRS Report R48776). Congressional Research Service.
- Gallagher, J. C., & Peskin, A. H. (2024). Restoration of cell phone services: Hurricane Helene (CRS In Focus IF12779). Congressional Research Service.

## Sources

- Brelsford, C., et al. (2024). A dataset of recorded electricity outages by United States county 2014–2022. *Scientific Data*, 11, 271. [https://doi.org/10.1038/s41597-024-03095-5](https://doi.org/10.1038/s41597-024-03095-5)
- Olukola, O., Addeh, O. D., Konan, E. A., & Rahimi, N. (2026). The towers were standing: A cause decomposition of cellular outages during Hurricane Helene. arXiv:2609.10944. [https://doi.org/10.48550/arXiv.2609.10944](https://doi.org/10.48550/arXiv.2609.10944)
- Federal Communications Commission. Disaster Information Reporting System, Communications Status Reports, 2017–2026; FCC 22-50 (Mandatory Disaster Response Initiative, adopted June 27, 2022; compliance from May 1, 2024, per the FCC's MDRI page, https://www.fcc.gov/node/254876, accessed November 23, 2026); FCC 24-5 and DA 25-74 (mandatory DIRS from February 20, 2025; Federal Register 2025-00495); FCC 26-34 (adopted May 20, 2026; Federal Register 2026-13155, 91 FR 39516, June 30, 2026).
- National Hurricane Center. HURDAT2 (1851–2025) and GIS best track for AL092026.
- Federal Communications Commission. Broadband Data Collection, National Broadband Map public data, Provider Summary by Geography Type (releases of June 30, 2022, 2023, 2024 and 2026); Public Data API specification, revision 1.7 (June 8, 2026).
- CDC/ATSDR Social Vulnerability Index 2022; U.S. Census Bureau, ACS 5-year 2022, 2020 Gazetteer and 2022 cartographic boundary file (counties, 1:500,000); FEMA OpenFEMA Disaster Declarations Summaries v2.
## If this were your data

The same approach turns scattered public status reports into a checked panel and answers how much went dark, how fast it came back, and what moved with it, with the uncertainty and the limits stated next to each number.

