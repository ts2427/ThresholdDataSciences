# fcc_storm_documents.csv

Collected 2026-11-22 from the FCC storm pages (www.fcc.gov/<storm>, linked from
https://www.fcc.gov/past-response-efforts), read in the Claude desktop app's browser
at about one request every 1.5 seconds. No document numbers were guessed or probed:
every link below was printed on an FCC page.

Columns
- storm_page: the FCC page slug (marco-laura covers Marco and Laura; ida covers Ida and Nicholas)
- kind: status_report, activation, area_change or deactivation (from the title)
- role: primary = first attachment on the document page; related_likely_translation = a second
  report document on the same page, probably the Spanish version (verify from the text)
- title, released (as printed on the FCC document page), doc_id, pdf_url, txt_url, source_page

Counts: 316 documents; 179 primary status reports across 21 storm pages.
Includes storms outside the study scope (Nate, Barry, Dorian, Nicholas). Scope is decided in the manifest, not here.
The Florence Sep 20, 2018 page failed once during collection and was re-read by hand (DOC-354198A1).
