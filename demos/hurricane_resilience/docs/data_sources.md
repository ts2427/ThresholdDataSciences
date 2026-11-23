# Data sources

Status: VERIFIED = confirmed in research (Nov 16, 2026); CHECK = confirm on first download.

| Source | Access | Format | Coverage | Terms | Notes | Status |
|---|---|---|---|---|---|---|
| FCC DIRS Communications Status Reports | Index: https://www.fcc.gov/past-response-efforts ; storm pages (e.g. https://www.fcc.gov/helene); files at https://docs.fcc.gov/public/attachments/DOC-xxxxxxA1.pdf and .txt | PDF + TXT, no API | 2017–2026 | US government work, no copyright | FCC site may block automated browsing: build the manifest by hand from storm pages; direct docs.fcc.gov downloads usually work | VERIFIED |
| FCC DIRS rules | FCC 21-34, 22-50 (MDRI), 24-5 (mandatory DIRS), DA 25-74 (effective Feb 20, 2025), 26-34 (2026 streamlining) | PDF | 2021–2026 | Public | For regime flags and the policy timeline | VERIFIED |
| ORNL/DOE EAGLE-I | Scientific Data paper doi:10.1038/s41597-024-03095-5; figshare doi:10.6084/m9.figshare.24237376; 2025 release doi:10.13139/ORNLNCCS/3012826 | CSV per year (~10.8 GB total) | 2014–2025 | Figshare CC BY 4.0; ORNL "free to use and reuse", attribution requested | Filter to Gulf/Southeast states on read; coverage rises over time; use coverage/quality files | VERIFIED |
| poweroutage.us | — | — | — | Personal, non-commercial only; bans redistributing summaries | DO NOT USE | VERIFIED (exclude) |
| NHC HURDAT2 | https://www.nhc.noaa.gov/data/ | Text | 1851–2025 | Public domain | 2026 storms (Isaias) not in HURDAT2 until post-season; use GIS best track | VERIFIED |
| NHC GIS best track / swaths | https://www.nhc.noaa.gov/gis/ (archive by storm ID) | Shapefile / KMZ | ~2017+ swaths | Public domain | Convert KMZ with geopandas | VERIFIED (shapefile zip, accessed 2026-11-22) |
| OpenFEMA Disaster Declarations Summaries v2 | https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries | JSON/CSV, no key | 1953–present | Must display: "This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s)."; cite endpoint and access date | Clean FIPS | VERIFIED |
| CDC/ATSDR SVI 2022 | ATSDR SVI data download page (mirrors on Zenodo/Harvard Dataverse) | CSV | County, tract | Public, attribution requested | Latest = 2022 (ACS 2018–2022) | VERIFIED |
| Census ACS 5-year | https://api.census.gov | JSON | County | Public domain | Households, 65+, broadband subscription; needs free API key | VERIFIED (accessed 2026-11-22) |
| FCC Broadband Map county summaries | https://broadbandmap.fcc.gov/data-download | CSV | Twice yearly | Availability data free; location Fabric is licensed (don't use) | Cable vs fiber vs FWA mix | CHECK |
| Olukola et al. (2026) Helene DIRS dataset | arXiv:2609.10944 | — | Helene only | Paper CC BY-NC-ND 4.0; dataset license unconfirmed | Validation only, do not redistribute (e.g., 4,562 sites out on Sept 28, 2024) | VERIFIED (validation) |

## Access log (every file's URL and SHA-256 is in manifest/downloads.csv)

| Accessed | Source | What | Notes |
|---|---|---|---|
| 2026-11-22 | ORNL/DOE EAGLE-I, figshare doi:10.6084/m9.figshare.24237376 v4 (published 2026-02-25), CC BY 4.0 | eaglei_outages_2017.csv to 2024.csv, coverage_history.csv, MCC.csv, DQI.csv (8.94 GB) | API record read for the file list, sizes and MD5s (manifest/eaglei_files.csv); each file matched its MD5. Stored in EAGLEI_RAW_DIR outside the project; only the filtered extract is in data/interim. 2025 not downloaded (no in-scope storm needs it) |
| 2026-11-22 | Census Bureau, www2.census.gov | national_county2020.txt; 2020 Gazetteer counties (internal points) | robots.txt: no rule for general clients |
| 2026-11-22 | NHC, www.nhc.noaa.gov | data index page; HURDAT2 hurdat2-1851-2025-092326.txt; GIS best-track archive page and al092026_best_track.zip (Isaias 2026) | robots.txt allows all; public domain |
| 2026-11-22 | Census ACS 5-year 2022, api.census.gov | households, 65+, broadband subscription, all counties (one request) | robots.txt: no rules; key from .env, logged as key=REDACTED |
| 2026-11-22 | OpenFEMA | nothing | www.fema.gov/robots.txt returned 403; no FEMA request made. Waiting for the author |
| 2026-11-22 | FCC Broadband Map | nothing | broadbandmap.fcc.gov/robots.txt returned 403; no request made. Waiting for the author |
| 2026-11-22 | CDC/ATSDR SVI 2022 | download page only | the page has no direct file link (interactive tool); no file URL constructed. Waiting for the author |
| 2026-11-22 (20:14 EST; 2026-11-23 01:14:00-01:14:43 UTC) | OpenFEMA Disaster Declarations Summaries v2, https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries | 12 pages of declarations since 2017-08-01 (data/raw/fema/declarations_000-011.json) | Through the documented API (author's decision). Required attribution, as worded on FEMA's terms page (fema.gov/about/openfema/terms-conditions), checked by the author on 2026-11-22 so fema.gov was not fetched: "This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s)." |
| 2026-11-22 | U.S. Census Bureau cartographic boundary file, counties, 2022, 1:500,000 (https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip) | data/raw/census/cb_2022_us_county_500k.zip (11.7 MB) | One download approved by the author for the Isaias county map; same terms (robots.txt allows; generic User-Agent; SHA-256 in manifest/downloads.csv) |


## V2-5 access check (FCC Broadband Data Collection public data API), 2026-11-23

Documentation reads only; nothing downloaded into data/. Generic User-Agent (public-records-archiver/1.0), at least 3 seconds between requests, stopped at the first refusal.

- 2026-11-23 ~14:57 UTC, https://help.bdc.fcc.gov/robots.txt: 200 (no general disallow on help articles).
- 2026-11-23 ~14:57 UTC, https://help.bdc.fcc.gov/hc/en-us/articles/6789299021723-Key-Reference-Documents: 200. Lists the Public Data API Specifications (https://us-fcc.box.com/v/bdc-public-data-api-spec) and Swagger (https://us-fcc.box.com/v/bdc-public-data-api-swagger), both hosted on box.com.
- 2026-11-23 14:57 UTC, https://www.fcc.gov/general/api-terms-service: 403. Stopped here, as the download terms require; not retried and no header changed. The box.com specification documents were not requested.

- 2026-11-23 15:13 UTC, https://us-fcc.box.com/robots.txt: 200 (general agents: everything disallowed except listed paths, including /v/ and /shared/).
- 2026-11-23 15:13 UTC, the two shared-link pages (/v/bdc-public-data-api-spec, /v/bdc-public-data-api-swagger): 200.
- 2026-11-23 15:13 UTC, the two documents through box's allowed /shared/static/ links (not the disallowed index.php route), saved to data/raw/bdc/docs/ and logged in manifest/downloads.csv with SHA-256: bdc-public-data-api-specifications.pdf (24 pages, dated June 8, 2026, revision 1.7) and bdc-public-data-api-swagger.yaml (version 1.2.0). Approved by Tim, 2026-11-23.
- What they say: every call needs the headers username and hash_value (an API token generated in a FCC User Registration account, which requires accepting the FCC API terms of service); every endpoint is limited to 10 calls per minute; tokens can be revoked by the FCC at any time. Host: https://bdc.fcc.gov.
- 2026-11-23, https://bdc.fcc.gov/api/public/map/listAsOfDates: 401 (unauthorized). Stopped; no retry.
- 2026-11-23, bdc.fcc.gov listing calls (listAsOfDates; listAvailabilityData for 2022-06-30, 2022-12-31, 2023-06-30, 2024-06-30, 2024-12-31, 2026-06-30): 200; responses in data/raw/bdc/listings/ with SHA-256 in manifest/downloads.csv. No data file downloaded.

## V2-6 libraries, 2026-11-23

- D3 7.9.0 and topojson-client 3.1.0 (ISC): npm registry metadata and tarballs (https://registry.npmjs.org), dist files from jsDelivr (https://cdn.jsdelivr.net/npm/), each verified against the npm SHA-512 integrity; vendored into the site at static/js/vendor/ with their licences.

## Phase C rule checks, 2026-11-23

- Primary FCC texts read from docs.fcc.gov (URLs found by search, not guessed), saved to data/raw/rules/ and logged with SHA-256: FCC-26-34A1.txt (adopted May 20, 2026; paras. 26 and 41 on the final report); FCC-22-50A1_Rcd.pdf (adopted June 27, 2022); DA-24-380A1.pdf (fetched as the MDRI compliance notice, but it is an order extending comment dates; not cited).
- 2026-11-23: Creative Commons, CC BY 4.0 legal code, https://creativecommons.org/licenses/by/4.0/legalcode.txt (one request, generic User-Agent), saved to data/raw/licenses/ and logged in manifest/downloads.csv; used for LICENSE-DATA.md in the public data repository.
