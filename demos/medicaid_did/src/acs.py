"""Published ACS 1-year table C27016 (used to validate the PUMS panel, 2017–2019) (coverage by income-to-poverty ratio by age):
variable selection from each year's own labels, and state-year aggregation.

Low-income adults = 19–64, income under 138% of poverty
  = "Under 1.00" + "1.00 to 1.37" of poverty threshold.
All adults = 19–64 summed over every income bin (universe: civilian
  noninstitutionalized people for whom poverty status is determined).

Margins of error (90%, as published) for sums and ratios use the Census
Bureau's standard approximations (ACS General Handbook, ch. 8):
  MOE(sum)   = sqrt(sum of MOE^2)
  MOE(ratio) = sqrt(MOE_num^2 + p^2 * MOE_den^2) / den   (proportion formula;
               falls back to the ratio formula if the term under the root is
               negative)
"""
import math
import re

LOW_INCOME_BINS = ("Under 1.00", "1.00 to 1.37")
ALL_BINS = ("Under 1.00", "1.00 to 1.37", "1.38 to 1.99", "2.00 to 3.99", "4.00 and over")


def _norm(label):
    """'Estimate!!Total:!!Under 1.00 of poverty threshold:!!19 to 64 years:'
    and the older colon-free style both become a tuple of parts."""
    return tuple(p.strip().rstrip(":").strip() for p in label.split("!!"))


def select_vars(group_vars):
    """From a Census group-metadata 'variables' dict, return
    {bin: {'total': code, 'uninsured': code}} for the 19–64 rows of every
    income bin. Raises if any bin is missing or ambiguous, so a change in
    the table's layout in some year cannot slip through."""
    out = {}
    for code, meta in group_vars.items():
        if not re.fullmatch(r"C27016_\d{3}E", code):
            continue
        parts = _norm(meta["label"])
        if len(parts) < 4 or parts[0] != "Estimate" or parts[1] != "Total":
            continue
        m = re.match(r"(.+?) of poverty threshold( and over)?$", parts[2])
        if not m or parts[3] != "19 to 64 years":
            continue
        # "4.00 of poverty threshold and over" (2017+) == "4.00 and over"
        b = m.group(1) + (m.group(2) or "")
        kind = {4: "total"}.get(len(parts))
        if len(parts) == 5 and parts[4] == "No health insurance coverage":
            kind = "uninsured"
        if kind is None:
            continue
        slot = out.setdefault(b, {})
        if kind in slot:
            raise ValueError(f"ambiguous {kind} for bin {b}: {slot[kind]} and {code}")
        slot[kind] = code
    missing = [b for b in ALL_BINS if set(out.get(b, {})) != {"total", "uninsured"}]
    if missing:
        raise ValueError(f"C27016 19-64 rows missing for bins: {missing}")
    return {b: out[b] for b in ALL_BINS}


def moe_sum(moes):
    return math.sqrt(sum(float(m) ** 2 for m in moes))


def moe_proportion(num, den, moe_num, moe_den):
    p = num / den
    under = moe_num ** 2 - p ** 2 * moe_den ** 2
    if under < 0:
        under = moe_num ** 2 + p ** 2 * moe_den ** 2
    return math.sqrt(under) / den


def state_year_rates(rows, varmap):
    """rows: list of dicts from the API (NAME, state, <codes>E, <codes>M).
    Returns list of dicts with population, uninsured, rate and rate MOE for
    the low-income and all-adults groups. Rates are proportions (0–1)."""
    out = []
    for r in rows:
        rec = {"state": r["NAME"], "fips": r["state"]}
        for group, bins in (("lowinc", LOW_INCOME_BINS), ("all", ALL_BINS)):
            pop = sum(float(r[varmap[b]["total"]]) for b in bins)
            un = sum(float(r[varmap[b]["uninsured"]]) for b in bins)
            mpop = moe_sum(r[varmap[b]["total"][:-1] + "M"] for b in bins)
            mun = moe_sum(r[varmap[b]["uninsured"][:-1] + "M"] for b in bins)
            rec[f"{group}_pop"] = pop
            rec[f"{group}_uninsured"] = un
            rec[f"{group}_rate"] = un / pop
            rec[f"{group}_rate_moe90"] = moe_proportion(un, pop, mun, mpop)
        out.append(rec)
    return out
