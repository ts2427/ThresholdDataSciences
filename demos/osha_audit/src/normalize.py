"""Demo B step 3b: employer-name normalization (PROPOSED — awaiting Tim's
review before it is applied).

normalize_name(raw) applies, in order:
  1. lowercase; unify unicode dashes and apostrophes
  2. "dba": keep the part BEFORE "dba" / "d/b/a" / "doing business as" —
     the legal entity that filed the report (the trade name is kept in a
     separate field for reference)
  3. drop parenthetical text, e.g. "(PSSI)", "(ESG)"
  4. drop store/unit numbers: "#287", "# 0246", "store 517",
     "unit #12", "location 4", "branch 9", "no. 1188"
  5. "&" -> " and "
  6. delete periods and apostrophes (so "U.S." -> "us", "Lowe's" ->
     "lowes"); every other non-alphanumeric character -> space
  7. drop a leading "the"
  8. drop trailing legal suffixes, repeatedly: inc, incorporated, llc,
     l l c, corp, corporation, co, company, ltd, limited, lp, llp, pllc,
     pc, plc
  9. collapse whitespace

The grouping KEY is the normalized name with spaces removed, so "Wal-Mart"
/ "Walmart" and "Cross Cut" / "Cross-Cut" meet; the spaced form is kept for
display. Not done here (left to fuzzy matching in step 3c): aliases and
abbreviations ("USPS" vs "U.S. Postal Service"), and text after " - "
(site descriptors are common, but so are hyphenated legal names).
"""
import re
import unicodedata

SUFFIXES = {"inc", "incorporated", "llc", "corp", "corporation", "co", "company",
            "ltd", "limited", "lp", "llp", "pllc", "pc", "plc"}
_DBA = re.compile(r"\b(?:d\s*/?\s*b\s*/?\s*a|doing business as)\b", re.I)
_PAREN = re.compile(r"\([^)]*\)")
_STORE = re.compile(r"(?:\b(?:store|unit|location|branch|no)\b\.?\s*#?\s*\d+\w*)|(?:#\s*\d+\w*)", re.I)


def split_dba(raw):
    """(legal part, trade name or '')."""
    parts = _DBA.split(raw, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(" ,;-"), parts[1].strip(" ,;-")
    return raw.strip(), ""


def normalize_name(raw, strip_suffixes=True):
    s = unicodedata.normalize("NFKC", str(raw)).lower()
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    s, _ = split_dba(s)
    s = _PAREN.sub(" ", s)
    s = _STORE.sub(" ", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[.'`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"\bl l c\b", "llc", s)
    tokens = s.split()
    if strip_suffixes:
        while len(tokens) > 1 and tokens[-1] in SUFFIXES:
            tokens.pop()
    return " ".join(tokens)


def suffix_tail(raw):
    """The legal-suffix tokens normalize_name strips, in order, e.g.
    ('inc',) or ('co', 'inc'); () if none."""
    full = normalize_name(raw, strip_suffixes=False).split()
    base = normalize_name(raw).split()
    return tuple(full[len(base):])


def name_key(raw):
    """Grouping key: the normalized name without spaces."""
    return normalize_name(raw).replace(" ", "")
