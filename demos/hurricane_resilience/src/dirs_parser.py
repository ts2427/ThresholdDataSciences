"""Parse FCC DIRS Communications Status Reports (text) into county rows and report totals.

The county cell-site table has, per row: State, County, Cell Sites Served, Cell Sites Out, % Out,
and (in most years) Out due to Damage, Out due to Transport, Out due to Power, Sites on Backup Power.
Layouts vary by year, so this parser is deliberately tolerant:
  * a county row = a known state name or upper-case postal code, a county name, then 2 to 8 numeric tokens
    (Sally 2020 prints only sites served and out; pct_printed says whether the % column was printed)
  * a name wrapped onto the line above (indented capitals, e.g. "EAST BATON" over "LA ROUGE ...") is joined
  * a TOTAL whose numbers sit on a later line is joined. After rows from more than one state, a TOTAL that equals
    the last state's rows is that state's total (Helene Sep 28, 2024 prints no Georgia TOTAL); one that equals all
    the rows is an overall total (overall_totals, Harvey 2017)
  * a wrapped name may also sit unindented above its row in PDF text ("EAST BATON" over "LA ROUGE ...", 2019-2020)
  * page footers ("As prepared by the Federal Communications Commission: <date> <time>", "Pa ge | 3") are removed
  * a percent after "more than", "less than", "over" or "under" is not the headline
  * a bare "TOTAL" or "TOTAL -" row belongs to the state of the county rows above it
  * a table with no State column (Debby 2024) takes the state from the report's county list, and only
    when no row in the report carries a state and the list names exactly one
  * the "% Out" column is detected by its percent sign, not by position
  * report-level text such as "1.8% of cell sites ... are out of service" and
    "... cable and wireline subscribers out of service: 82,858" is captured separately
Checked cell by cell against the eight in-scope seed reports (Michael, Ian, Debby, Helene, Isaias). Others are
not yet validated. Compare to the PDF by eye when adjusting the patterns. Every change needs a test.
"""
from __future__ import annotations

import re
from datetime import datetime
from dataclasses import dataclass, field

STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas",
    "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming", "Puerto Rico", "U.S. Virgin Islands", "Virgin Islands",
    "Guam", "American Samoa", "Northern Mariana Islands",
]
_CODES = ("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
          "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY PR VI VI GU AS MP").split()
# "VI" appears twice because STATES lists both names of the Virgin Islands; the first name wins.
CODE_TO_STATE = dict(reversed(list(zip(_CODES, STATES, strict=True))))
# Codes are case-sensitive so that words such as "in", "or" and "me" never start a row.
_STATE_RE = ("|".join(sorted((re.escape(s) for s in STATES), key=len, reverse=True))
             + "|(?-i:" + "|".join(CODE_TO_STATE) + ")")
_NUM = r"-?[\d,]+(?:\.\d+)?%?"
ROW_RE = re.compile(rf"^\s*(?P<state>{_STATE_RE})\s+(?P<county>[A-Za-z][A-Za-z .'\-]*?)\s+(?P<nums>(?:{_NUM}\s+){{1,7}}{_NUM})\s*$",
                    re.IGNORECASE)
TOTAL_ROW_RE = re.compile(rf"^\s*TOTAL\s+(?:-\s+)?(?P<nums>(?:{_NUM}\s+){{1,7}}{_NUM})\s*$")
FOOTER_RE = re.compile(r"As prepared by the Federal Communications Commission:\s*\w+\s+\d{1,2},?\s*\d{4}\s*"
                       r"(?:\d{1,2}:\d{2}\s*[ap]\.m\.\s*[A-Z]{3})?|Pa ge \| \d+")
TOTAL_ALONE_RE = re.compile(r"^\s*TOTAL\s*(?:-\s*)?$")
NUMBERS_ONLY_RE = re.compile(rf"^\s*(?P<nums>(?:{_NUM}\s+){{1,7}}{_NUM})\s*$")
THRESHOLD_RE = re.compile(r"(?:more|less|fewer)\s+than\s*$|\b(?:over|under|above|below)\s*$", re.IGNORECASE)
WRAPPED_NAME_RE = re.compile(r"^\s*(?P<prefix>[A-Z][A-Z.']*(?: [A-Z][A-Z.']*){0,3})\s*$")  # capitals only
HEADER_WORDS = {"STATE", "STATES", "COUNTY", "COUNTIES", "AFFECTED", "CELL", "SITES", "SERVED", "OUT", "PERCENT",
                "TOTAL", "DUE", "DAMAGE", "TRANSPORT", "POWER", "BACKUP", "BACK-UP", "NUMBER", "OF"}


def is_name_prefix(prefix: str) -> bool:
    """A line of capitals that can start a wrapped county name: not a state, a state code or table header words."""
    words = set(prefix.split())
    return prefix.title() not in STATES and prefix not in CODE_TO_STATE and not words & HEADER_WORDS
NO_STATE_ROW_RE = re.compile(r"^\s*(?P<county>[A-Z][A-Za-z .'\-]*?)\s+"
                             r"(?P<nums>[\d,]+\s+[\d,]+\s+\d+(?:\.\d+)?%(?:\s+[\d,]+){4})\s*$")
TOTAL_WORDS = re.compile(r"\b(total|totals|all counties|overall)\b", re.IGNORECASE)
CABLE_RE = re.compile(r"(?P<n>\d[\d,]+)\s+(?:\([^)]*\)\s+)?(?:(?:cable|wireline)[a-z/\s]*?\s+)?"
                      r"subscribers?[^.\n]*out\s+of\s+service"
                      r"|subscribers?[^.\n]*out of service[^.\n\d]*(?P<n2>[\d,]{2,})", re.IGNORECASE)
PCT_SITES_RE = re.compile(r"(?P<pct>\d+(?:\.\d+)?)\s*%\s*(?:\([^)]*\)\s*)?(?:of\s+)?(?:the\s+)?cell\s+sites", re.IGNORECASE)

# The report's own county list: "Florida: Bay, Calhoun, ..., and Washington." ahead of the 911 section.
_STATE_BY_LOWER = {s.lower(): s for s in STATES}
_STATE_RE_PLAIN = "|".join(sorted(map(re.escape, STATES), key=len, reverse=True))
LIST_START_RE = re.compile(r"^\s*(?P<state>" + "|".join(sorted(map(re.escape, STATES), key=len, reverse=True))
                           + r")\s*:\s*(?P<names>\S.*)$", re.IGNORECASE)
LIST_SECTION_END_RE = re.compile(r"911\s+Services")
NOT_A_LIST_LINE_RE = re.compile(r"^(?:The|On|In|\d+)\s")  # a sentence or a footnote
LAST_NAME_RE = re.compile(r"^[A-Z][\w'\-]*(?: [A-Z][\w'\-]*){0,2}\.$")  # e.g. "Rosa."


@dataclass
class ParsedReport:
    rows: list[dict] = field(default_factory=list)
    state_totals: list[dict] = field(default_factory=list)
    pct_sites_out: float | None = None
    cable_wireline_subs_out: int | None = None
    warnings: list[str] = field(default_factory=list)
    overall_totals: list[dict] = field(default_factory=list)  # a TOTAL covering several states' rows
    county_list: list[dict] = field(default_factory=list)  # as listed by the report, not from the table
    as_of_date: str | None = None  # "as of September 28, 2024, at 9:00 a.m. EDT": the snapshot time, ISO date
    as_of_time: str | None = None  # 24-hour "HH:MM"
    as_of_tz: str = ""  # as printed (EDT, EST) or "" when not printed


AS_OF_RE = re.compile(r"\bas of\s+(?:(?P<date>[A-Z][a-z]+\.? \d{1,2},? \d{4}),?\s+(?:at\s+)?)?"
                      r"(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>[ap])\.?\s*m\b\.?\s*(?P<tz>[ECMP][DS]T\b)?",
                      re.IGNORECASE)
LATE_LIST_RE = re.compile(r"following (?:counties|parishes)[^.]{0,80}?(?:are|is) in the current geographic area")
_STATE_BY_LOWER["virgin islands"] = "U.S. Virgin Islands"  # the tables print VI


def parse_county_list(text: str) -> list[dict]:
    """The report's own county list, normally before the 911 section; Laura 2020 prints it after the tables."""
    found = _scan_county_list(LIST_SECTION_END_RE.split(text, maxsplit=1)[0])
    if not found:
        late = LATE_LIST_RE.search(text)
        if late:
            found = _scan_county_list(text[late.end():])
    return found


def _clean_names(names: str) -> list[str]:
    names = re.sub(r"\s*\([^)]*\)", "", names)  # "Jackson (Eastern Band of Cherokee Indians and Jackson)"
    raw = [" ".join(p.split()) for p in names.rstrip(".").split(",")]
    parts, i = [], 0
    while i < len(raw):
        p = re.sub(rf"^(?:{_STATE_RE_PLAIN})\s*:\s*", "", raw[i], flags=re.IGNORECASE)
        if p in ("St", "and St") and i + 1 < len(raw):  # the FCC sometimes types "St, Martin"
            p = f"St. {raw[i + 1]}"
            i += 1
        parts.append(p)
        i += 1
    parts = [re.sub(r"^and ", "", p) for p in parts if p]
    if parts and " and " in parts[-1] and parts[-1] != "King and Queen":  # "A and B" with no comma
        parts[-1:] = parts[-1].rsplit(" and ", 1)
    return [p for p in parts if p]


def _scan_county_list(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines()]
    found = []
    for i, line in enumerate(lines):
        start = LIST_START_RE.match(line)
        if not start:
            continue
        names = start.group("names")
        for following in lines[i + 1:]:
            if names.endswith(".") and not re.search(r"\bSt\.$", names):
                break
            unfinished = names.endswith(",") or re.search(r"(?:\band|\bSt\.)$", names)
            if not following:
                if unfinished:
                    continue
                break
            if LIST_START_RE.match(following):
                break
            more_names = not NOT_A_LIST_LINE_RE.match(following) and (
                "," in following or LAST_NAME_RE.match(following))
            if not (unfinished or more_names):
                break
            names += " " + following
        state = _STATE_BY_LOWER[start.group("state").lower()]
        found += [{"state": state, "county": p} for p in _clean_names(names)]
    return found


def _to_num(tok: str) -> float:
    return float(tok.replace(",", "").replace("%", ""))


def _row_from_tokens(state: str, county: str, toks: list[str]) -> dict | None:
    pct_idx = [i for i, t in enumerate(toks) if t.endswith("%")]
    nums = [_to_num(t) for t in toks]
    if pct_idx:
        i = pct_idx[0]
        if i < 2:
            return None
        served, out, pct = nums[i - 2], nums[i - 1], nums[i]
        rest = [n for j, n in enumerate(nums) if j > i]
        printed = True
    else:
        served, out = nums[0], nums[1]
        pct = 100 * out / served if served else None
        rest = nums[2:]
        printed = False
    row = {"state": state.title() if state.isupper() else state, "county": county.strip(),
           "sites_served": served, "sites_out": out, "pct_out": pct, "pct_printed": printed,
           "out_damage": None, "out_transport": None, "out_power": None, "on_backup_power": None}
    for key, val in zip(["out_damage", "out_transport", "out_power", "on_backup_power"], rest):
        row[key] = val
    return row


def parse_text(text: str) -> ParsedReport:
    rep = ParsedReport()
    text = FOOTER_RE.sub(" ", text)
    rep.county_list = parse_county_list(text)
    m = AS_OF_RE.search(" ".join(text.split()))
    if m:
        hour = int(m.group("h")) % 12 + (12 if m.group("ap").lower() == "p" else 0)
        rep.as_of_time = f"{hour:02d}:{m.group('m') or '00'}"
        rep.as_of_tz = (m.group("tz") or "").upper()
        if m.group("date"):
            rep.as_of_date = datetime.strptime(re.sub(r"[.,]", "", m.group("date")), "%B %d %Y").date().isoformat()
    for m in PCT_SITES_RE.finditer(text):
        if not THRESHOLD_RE.search(text[max(0, m.start() - 20):m.start()]):
            rep.pct_sites_out = float(m.group("pct"))
            break
    m = CABLE_RE.search(text)
    if m:
        rep.cable_wireline_subs_out = int((m.group("n") or m.group("n2")).replace(",", ""))
    table_rows = []  # county rows since the last total
    lines = text.splitlines()
    listed_states = {c["state"] for c in rep.county_list}
    only_state = None  # set only for a table with no State column
    if len(listed_states) == 1 and not any(ROW_RE.match(line) for line in lines):
        [only_state] = listed_states
    prefix = None  # first words of a name the table wrapped onto the line above
    total_pending = False  # a TOTAL line whose numbers come on a later line
    for line in lines:
        if total_pending:
            if not line.strip():
                continue
            numbers = NUMBERS_ONLY_RE.match(line)
            total_pending = False
            if numbers:
                line = "TOTAL " + numbers.group("nums")
        if TOTAL_ALONE_RE.match(line):
            total_pending = True
            continue
        wrapped = WRAPPED_NAME_RE.match(line)
        if wrapped and is_name_prefix(wrapped.group("prefix")):
            prefix = wrapped.group("prefix")
            continue
        held, prefix = prefix, None
        total = TOTAL_ROW_RE.match(line)
        if total:
            states = list(dict.fromkeys(r["state"] for r in table_rows))
            row = _row_from_tokens(states[-1], "TOTAL", total.group("nums").split()) if states else None
            if row and len(states) > 1:
                last = sum(r["sites_served"] for r in table_rows if r["state"] == states[-1])
                every = sum(r["sites_served"] for r in table_rows)
                if abs(every - row["sites_served"]) < 0.5 and abs(last - row["sites_served"]) >= 0.5:
                    row["states"] = "; ".join(sorted(states))
                    rep.overall_totals.append(row)
                else:  # the last state's own total; step 4 says if it does not add up
                    rep.state_totals.append(row)
            elif row:
                rep.state_totals.append(row)
            else:
                rep.warnings.append(f"total with no county rows above it, or unreadable: {line.strip()}")
            table_rows = []
            continue
        m = NO_STATE_ROW_RE.match(line) if only_state else ROW_RE.match(line)
        if not m:
            continue
        toks = m.group("nums").split()
        state = only_state or CODE_TO_STATE.get(m.group("state"), m.group("state"))
        county = f"{held} {m.group('county').strip()}" if held else m.group("county")
        row = _row_from_tokens(state, county, toks)
        if row is None:
            rep.warnings.append(f"unparsed row: {line.strip()}")
            continue
        if row["sites_out"] > row["sites_served"]:
            rep.warnings.append(f"out > served: {line.strip()}")
        if TOTAL_WORDS.search(row["county"]):
            rep.state_totals.append(row)
        else:
            rep.rows.append(row)
            table_rows.append(row)
    if not rep.rows:
        rep.warnings.append("no county rows found")
    return rep


def reconcile(rep: ParsedReport, tol: float = 0.5) -> list[str]:
    """County rows must add up to each stated state total (when the report gives one)."""
    issues = []
    for t in rep.state_totals:
        rows = [r for r in rep.rows if r["state"].lower() == t["state"].lower()]
        for col in ["sites_served", "sites_out"]:
            s = sum(r[col] for r in rows)
            if abs(s - t[col]) > tol:
                issues.append(f"{t['state']} {col}: counties sum to {s:,.0f}, report says {t[col]:,.0f}")
    return issues
