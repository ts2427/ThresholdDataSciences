# Demo B write-up requirements (Tim, 2026-11-19)

Carried into the site page when Tim says go. Numbers are pulled from
`results/osha_audit.json`, never typed.

1. **Coverage up front:** federal-OSHA jurisdictions only; state-plan states
   are not included (OSHA's wording in docs/sources.md).
2. **Frame everything as "reports filed".** Never "most dangerous
   employers"; no ranking is a safety ranking.
3. **Duplicates as a range, with the reason.** Report the same-employer
   duplicate count as a range — strict / proposed / loose
   (`step3a_rule.sensitivity`: 16 / 42 / 73 pairs) — and say why: the count
   depends on the matching rule. The final figure is the proposed rule
   after hand confirmation (`step3a_final`).
4. **Say plainly that duplicates are a minor issue here**: the final removed
   count out of all reports (e.g. "42 of 105,996"), and that the larger
   distortion is in employer names.
5. **The 2020 dip in reports reflects the pandemic, not a safety trend.**
6. **State totals reflect federal-OSHA coverage and workforce size, not
   relative safety.**
7. **Report counts track company size; a count ranking is not a safety
   ranking** — step 3e shows this with data.
8. **The 2,492 `FederalState = 0` rows appear as a separate line in every
   table** (count from code, not typed).
9. **Merged duplicates keep the lowest UPA but the higher hospitalization
   and amputation counts from either row.**
10. **`share_pct` values are percentages; label them "% of reports" on the
    page.**
11. **List the uncertain duplicate merges:** pairs 3 (XPO Logistics,
    5/3/2019) and 17 (VA John D. Dingell Medical Center, 5/2/2019), merged
    as judgment calls (same machine or door, same day, different finger
    recorded); and the 3 pairs kept apart as two workers. Report the final
    count (`step3a_final.rows_removed`) against the 16 / 42 / 73 range.
12. **Employer counts depend on the definition.** Report distinct employers
    both ways (`step3b_final.narrow_rule.by_name` and
    `.by_name_and_state`) and say: "How many employers filed reports
    depends on the definition — identical names in different states are
    usually different small firms, but the same company for national
    employers."
13. **State the entity principle:** "Names that refer to the same operating
    employer merge (store formats and locations, acronyms); separate legal
    operating companies stay separate (FedEx Freight vs FedEx; subsidiaries
    vs parents)."
14. **Matcher quality, stated plainly** (numbers from
    `step3d_estimate`): the matcher is precise but conservative — precision
    `main.precision` (Wilson 95% interval), recall `main.recall` (stratified
    bootstrap 95% interval). Say the rule was not tuned on these labels.
    Say where the misses are, as the labels show it: in the band just above
    the threshold, nearly all misses are typos inside common words that the
    distinctive-part check rejects ("Manufacturin", "Distibution",
    "Serive"); but the larger estimated share is pairs scoring just under
    the overall threshold (85–92), a mix of typos and variants such as "+"
    vs "and" — and that share rests on few labeled matches, so it is
    uncertain. (Tim's original wording, "most misses are typos inside common
    words that the distinctive-part check rejects", is not supported by the
    weighted estimate; see docs/decisions.md.)
15. **Missed matches overstate the distinct-employer count** by at most
    `overstatement.max_overstatement_pct` (95% interval
    `max_overstatement_pct_ci95`); report the sensitivity row with the 13
    judgment calls flipped, and the 80–85 limitation (0 of 50; recall at the
    Wilson upper bound).
16. **Label source (Tim, final):** "Accuracy figures are illustrative: they
    were estimated against match labels drafted by an AI model. In client
    work, labels are checked by hand."
17. **Step 3e is an illustration, not a comparison.** State that headcounts
    are national (or company-wide) while reports cover federal-OSHA states
    only, that headcounts are one fiscal year while reports span 2015–2025,
    so this is not a rate comparison and not a safety ranking. Give each
    headcount's source and year. Say plainly that the association is loose
    (industry and how much of a workforce sits in federal-OSHA states both
    matter). Disney: no parks headcount is published.
