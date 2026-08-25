#!/usr/bin/env python3
"""Run axe-core (WCAG 2.x A/AA rules) against the built site.

Serves dist/ locally, drives headless Chrome via Selenium, injects
tools/axe.min.js, and reports violations per page. Exit code 1 on any
violation. (Equivalent role to pa11y/axe-cli; used because this machine has
Python + Chrome but no Node.)
"""

import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

HERE = Path(__file__).parent
DIST = HERE.parent / "dist"
PORT = 8799

PAGES = [
    "/",
    "/threshold-effects/",
    "/threshold-effects/no-011/",
    "/threshold-effects/no-001/",
    "/analysis/",
    "/research/",
    "/advisory/",
    "/about/",
    "/contact/",
    "/privacy/",
    "/404.html",
]


def serve():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main():
    axe_src = (HERE / "axe.min.js").read_text(encoding="utf-8")
    httpd = serve()

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")
    driver = webdriver.Chrome(options=opts)

    total = 0
    try:
        for path in PAGES:
            driver.get(f"http://127.0.0.1:{PORT}{path}")
            driver.execute_script(axe_src)
            result = driver.execute_async_script(
                "var done = arguments[arguments.length - 1];"
                "axe.run(document, {runOnly: {type: 'tag', values:"
                " ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa',"
                "  'best-practice']}})"
                ".then(function(r){ done(JSON.stringify("
                "  r.violations.map(function(v){ return {id: v.id,"
                "    impact: v.impact, help: v.help,"
                "    nodes: v.nodes.map(function(n){return n.target.join(' ');})"
                "  };}))); });"
            )
            violations = json.loads(result)
            if violations:
                total += len(violations)
                print(f"\n{path} — {len(violations)} violation(s):")
                for v in violations:
                    print(f"  [{v['impact']}] {v['id']}: {v['help']}")
                    for n in v["nodes"][:5]:
                        print(f"      {n}")
            else:
                print(f"{path} — clean")
    finally:
        driver.quit()
        httpd.shutdown()

    print(f"\n{'FAIL' if total else 'PASS'}: {total} violation(s) across "
          f"{len(PAGES)} pages (axe-core, WCAG 2.0/2.1/2.2 A+AA + best-practice).")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
