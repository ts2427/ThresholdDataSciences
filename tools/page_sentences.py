"""The sentences of a built analysis page, for checking that a restructure moves text without rewriting it.

  python tools/page_sentences.py dist/analysis/<slug>/index.html > sentences.txt

Reads the page's <article>, drops scripts, styles and chart SVGs (their axis labels are not prose), and splits the
text into sentences at ". ", "? " and "! " followed by a capital letter or a quote. Used by tests/test_page_tabs.py
and for the before/after diff of the tab restructure (2026-11-28).
"""
import html
import re
import sys
from collections import Counter
from pathlib import Path


def article_text(page: str) -> str:
    a = page[page.index("<article"):page.rindex("</article>")]
    a = re.sub(r"(?s)<(script|style|svg|nav)\b.*?</\1>", " ", a)  # navigation is compared separately, not as prose
    a = re.sub(r'(?s)<details class="toc-mobile.*?</details>', " ", a)
    a = re.sub(r'(?s)<div class="tab-bar.*?</div>', " ", a)
    a = re.sub(r"<(br|/p|/li|/h[1-6]|/td|/th|/tr|/summary|/figcaption|/caption|/div|/section|/details)\b[^>]*>", "\n", a)
    a = re.sub(r"<[^>]+>", " ", a)
    return html.unescape(a)


def sentences(page: str) -> Counter:
    out = Counter()
    for block in article_text(page).split("\n"):
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        for s in re.split(r"(?<=[.?!])\s+(?=[A-Z\"“(*])", block):
            s = s.strip()
            if s:
                out[s] += 1
    return out


if __name__ == "__main__":
    for s, n in sorted(sentences(Path(sys.argv[1]).read_text(encoding="utf-8")).items()):
        print(f"{n}\t{s}")
