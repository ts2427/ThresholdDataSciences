"""Read an FCC DIRS public notice: which counties it adds to a storm's reporting area, removes from it,
or sets as a state's whole remaining area. Lists repeated for the MDRI are ignored.

A notice prints counties as "State: A, B, and C". What a list means comes from the words just before it:
  * "remains activated in the following ..."                         -> remain (the state's area is now this list)
  * "has deactivated ...", "announces the deactivation of ..."       -> remove
  * "counties of interest", "additional counties", "is activated in",
    "expand ...", "extend ..."                                       -> add
  * a sentence about the MDRI that does not mention DIRS             -> ignored
  * lists that follow one another with nothing between them share the same meaning
An opening such as "DIRS deactivated in Alabama and Mississippi" ends those whole states ("some counties"
and "most counties" end nothing by themselves). A deactivation notice with no lists ends the states named in
its title, or the whole storm. An unexplained gap between lists (a footnote) keeps the previous list's meaning.
FCC spellings are kept as printed ("Point Coupee"); matching them to other spellings happens later.
Checked against the 98 notices for the in-scope storms on 2026-11-22; anything unreadable is reported, not guessed.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from dirs_parser import STATES

_STATE_ALT = "|".join(re.escape(s) for s in sorted(STATES, key=len, reverse=True))
LABEL_RE = re.compile(rf"(?<![A-Za-z])(?:State of |Commonwealth of )?(?P<state>{_STATE_ALT})(?:\s*\(no change\))?\s*:\s*",
                      re.I)
END_RE = re.compile(r"(?<!\bSt)(?<!\bSte)(?<!\bFt)\.(?=\s|$)|\s+(?=(?:The (?:FCC|Commission|Federal|Public|following)|For|"
                    r"Communications|Upon|Further|DIRS|In DIRS|Facilities|Providers|PSHSB|This|At the|All FCC|Please|"
                    r"Reports|Additionally|In addition|See|A map)\b)")
# A footnote the FCC prints inside a list where a page breaks ("Gilchrist, 1 DIRS is a voluntary ... crisis. 2Glades")
BOILERPLATE_RE = re.compile(r"\d*\s*DIRS is a voluntary, web-based system.*?during times of crisis\.\s*\d*")
OPENING_RE = re.compile(r"DIRS deactivated (?P<what>.*?)(?=\.|DIRS remains|At the request|$)")
SINGLE_RE = re.compile(rf"to include (?P<county>[A-Z][A-Za-z.' -]+?) County in (?:the State of )?(?P<state>{_STATE_ALT})")

MDRI_RE = re.compile(r"MDRI|Mandatory Disaster Response", re.I)
DIRS_RE = re.compile(r"\bDIRS\b|Disaster Information Reporting|data collection", re.I)
REMAIN_RE = re.compile(r"remains? activ", re.I)
DEACT_RE = re.compile(r"\bhas deactivated|\bdeactivates\b|announces? (?:the )?(?:partial )?deactivation|"
                      r"deactivation of the (?:DIRS|Disaster)", re.I)
ADD_RE = re.compile(r"includ|additional|of interest|is activated in|expand|extend", re.I)

TITLE_STATES = {"carolinas": ["North Carolina", "South Carolina"], "usvi": ["U.S. Virgin Islands"],
                "ga.": ["Georgia"], "ala.": ["Alabama"]}
_CANON = {s.lower(): s for s in STATES}


@dataclass
class Op:
    action: str  # add | remove | remain | end
    state: str  # "*" for the whole storm
    counties: list[str] = field(default_factory=list)


@dataclass
class Notice:
    ops: list[Op] = field(default_factory=list)
    unread: bool = False


def canonical_state(name: str) -> str:
    return _CANON[name.lower()]


def split_names(content: str) -> list[str]:
    parts = [p.strip() for p in content.split(",")]
    names, i = [], 0
    while i < len(parts):
        p = parts[i]
        if p in ("St", "Ft") and i + 1 < len(parts):  # the FCC sometimes types "St, Martin"
            p = f"{p}. {parts[i + 1]}"
            i += 1
        names.append(p)
        i += 1
    names = [re.sub(r"^and\s+", "", n).strip().rstrip(".").strip() for n in names]
    names = [re.sub(r"\s*\(\d+\)$", "", n) for n in names]  # footnote markers, e.g. "Washington (3)"
    if names and " and " in names[-1] and names[-1] != "King and Queen":
        names[-1:] = names[-1].rsplit(" and ", 1)
    return [n for n in names if n and n[0].isalpha()]


def opening_ends(text: str) -> list[Op]:
    """Whole states ended by an opening such as "DIRS deactivated in Alabama and Mississippi"."""
    m = OPENING_RE.search(text)
    if not m:
        return []
    ended = []
    for part in re.split(r",\s*|\s+and\s+", m.group("what")):
        part = re.sub(r"^(?:for\s+)?(?:all counties\s+)?(?:in\s+)?", "", part.strip())
        if re.search(r"\b(?:some|most|counties)\b", part):
            continue
        near = difflib.get_close_matches(part.lower(), list(_CANON), n=1, cutoff=0.85)  # the FCC wrote "Mississipi"
        if near:
            ended.append(Op("end", _CANON[near[0]]))
    return ended


def classify(lead: str, kind: str, title: str) -> str | None:
    """The meaning of a list, from the text between the previous list and this one."""
    sentence = re.split(r"(?<!\bSt)\.\s+", lead)[-1]
    if MDRI_RE.search(sentence) and not DIRS_RE.search(sentence):
        return "ignore"
    if REMAIN_RE.search(sentence[-250:]):
        return "remain"
    window = lead[-600:]
    if DEACT_RE.search(window):
        return "remove"
    if ADD_RE.search(window):
        return "add"
    if kind == "activation":
        return "add"
    if kind == "deactivation":
        return "remove"
    if re.search(r"extend|expand", title, re.I):
        return "add"
    return None


def read_notice(text: str, kind: str, title: str = "") -> Notice:
    text = re.sub(r"\s+", " ", text.replace("﻿", ""))
    text = BOILERPLATE_RE.sub(" ", text)
    labels = list(LABEL_RE.finditer(text))
    notice, previous_end, previous_class = Notice(), 0, None
    for n, label in enumerate(labels):
        stop = labels[n + 1].start() if n + 1 < len(labels) else len(text)
        content = text[label.end():stop]
        end = END_RE.search(content)
        if end:
            content = content[:end.start()]
        lead = text[previous_end:label.start()]
        meaning = previous_class if not lead.strip(" ,;.") and previous_class else classify(lead, kind, title)
        if meaning is None and previous_class:  # e.g. a footnote printed between two lists
            meaning = previous_class
        previous_end, previous_class = label.end() + len(content), meaning
        names = split_names(content)
        if not names or meaning == "ignore":
            continue
        if meaning is None:
            notice.unread = True
            continue
        notice.ops.append(Op(meaning, canonical_state(label.group("state")), names))
    notice.ops = opening_ends(text) + notice.ops
    for m in SINGLE_RE.finditer(text):
        notice.ops.append(Op("add", canonical_state(m.group("state")), [m.group("county").strip()]))
    if not notice.ops and kind == "deactivation":
        states = [canonical_state(s) for s in re.findall(_STATE_ALT, title, re.I)]
        for word, named in TITLE_STATES.items():
            if word in title.lower():
                states += named
        notice.ops = [Op("end", s) for s in states] or [Op("end", "*")]
    if not notice.ops:
        notice.unread = True
    return notice
