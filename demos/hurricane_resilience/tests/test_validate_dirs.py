"""Step 4: one test for every way a report can fail, be flagged, or be excused."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from carried import add_unattributed  # noqa: E402
from dirs_parser import parse_text  # noqa: E402

step4 = importlib.import_module("04_validate_dirs")

# Verbatim from the Isaias report of 2026-10-12 (Alabama only).
REPORT = """Alabama: Baldwin, Butler, Choctaw, Clarke, Conecuh, Covington, Crenshaw, Escambia,
Geneva, Mobile, Monroe, and Washington.
911 Services
The following table provides information on cell sites out of service by county. Overall, there is
1.8% (down from 9.8% yesterday) of the cell sites in the affected area reported in the DIRS as
being out of service.
AL BALDWIN 294 1 0.3% 0 0 1 24
AL BUTLER 51 0 0% 0 0 0 10
AL CHOCTAW 41 0 0% 0 0 0 3
AL CLARKE 50 0 0% 0 0 0 8
AL CONECUH 33 5 15.2% 0 1 3 14
AL COVINGTON 58 3 5.2% 0 0 3 9
AL CRENSHAW 36 0 0% 0 0 0 2
AL ESCAMBIA 65 6 9.2% 1 2 2 13
AL GENEVA 55 2 3.6% 0 0 2 18
AL MOBILE 414 1 0.2% 0 0 1 17
AL MONROE 37 3 8.1% 1 0 1 11
AL WASHINGTON 39 0 0% 0 0 0 3
TOTAL - 1173 21 1.8% 2 3 13 132
"""
DOC = "DOC-1A1"
CAUSES = ["out_damage", "out_transport", "out_power"]


class Case:
    def __init__(self):
        rep = parse_text(REPORT)
        self.rows = add_unattributed(pd.DataFrame([{"doc_id": DOC, **r} for r in rep.rows]))
        self.rows["area_status"] = "inside"
        self.totals = pd.DataFrame([{"doc_id": DOC, **t} for t in rep.state_totals])
        self.lists = pd.DataFrame([{"doc_id": DOC, **c} for c in rep.county_list])
        self.reports = pd.DataFrame([{"doc_id": DOC, "storm_name": "Isaias", "report_date": "2026-10-12",
                                      "pct_sites_out_stated": rep.pct_sites_out}])
        self.over = pd.DataFrame(columns=step4.OVER_FIELDS)
        self.headlines = pd.DataFrame(columns=step4.HEADLINE_FIELDS)
        self.unlisted = pd.DataFrame(columns=step4.OVER_FIELDS)
        self.overall = pd.DataFrame(columns=["doc_id", "states", "sites_served", "sites_out"])
        self.excluded = pd.DataFrame(columns=["doc_id", "storm_name", "report_date", "reason", "decided_on"])
        self.lines = pd.DataFrame([{"doc_id": DOC, "line": line} for line in REPORT.splitlines()])

    def reprint(self):
        """The change is in what the FCC printed, so the second reading of the PDF shows it too."""
        lines = []
        for r in self.rows.to_dict("records"):
            values = [f"{r['sites_served']:g}", f"{r['sites_out']:g}", f"{r['pct_out']:g}%"]
            values += [f"{r[c]:g}" for c in CAUSES + ["on_backup_power"] if pd.notna(r[c])]
            lines.append({"doc_id": DOC, "line": " ".join(["AL", r["county"], *values])})
        self.lines = pd.DataFrame(lines)

    def allow_unlisted(self, **changes):
        row = self.rows[self.rows.county == "BALDWIN"].iloc[0].to_dict()
        entry = {**{f: row.get(f) for f in step4.OVER_FIELDS}, "page": 3, "checked_on": "2026-11-22", **changes}
        self.unlisted = pd.DataFrame([entry])

    def set_row(self, county, col, value):
        self.rows.loc[self.rows.county == county, col] = value
        self.rows = add_unattributed(self.rows)

    def set_total(self, col, value):
        self.totals[col] = float(value)

    def make_exact(self):
        """Give every short row a cause, and move the printed total with it."""
        short = self.rows.out_unattributed
        self.rows["out_power"] += short
        self.totals["out_power"] += short.sum()
        self.rows = add_unattributed(self.rows)
        self.reprint()

    def make_over(self):
        self.set_row("BALDWIN", "out_transport", 1.0)
        self.set_total("out_transport", 4)
        self.reprint()

    def allow_over(self, **changes):
        row = self.rows[self.rows.county == "BALDWIN"].iloc[0].to_dict()
        entry = {**{f: row.get(f) for f in step4.OVER_FIELDS}, "page": 3, "checked_on": "2026-11-22", **changes}
        self.over = pd.DataFrame([entry])

    def allow_headline(self, **changes):
        self.headlines = pd.DataFrame([{"doc_id": DOC, "page": 3, "stated_pct": 21.7, "total_served": 1173,
                                        "total_out": 21, "checked_on": "2026-11-22", **changes}])

    def run(self):
        results, summary = step4.validate(self.rows, self.totals, self.reports, self.lists,
                                          self.over, self.headlines, self.unlisted, self.lines, self.overall,
                                          self.excluded)
        self.summary = summary.iloc[0]
        self.result = results.iloc[0]
        return self.result

    def fails_with(self, words):
        result = self.run()
        assert result.status == "fail"
        assert words in result.failures


@pytest.fixture
def case():
    return Case()


# --- pass and flag ---

def test_exact_report_is_ok(case):
    case.make_exact()
    assert case.run().status == "ok"


def test_shortfall_is_flagged_not_failed(case):
    result = case.run()
    assert result.status == "flagged"
    assert "3 rows short" in result.flag_reasons and result.sites_unattributed == 3


def test_shortfall_of_more_than_one_is_still_only_flagged(case):
    case.set_row("CONECUH", "out_power", 1.0)
    case.set_total("out_power", 11)
    case.reprint()
    assert case.run().status == "flagged"
    assert case.summary["Short by more"] == 1


def test_county_listed_twice_by_the_fcc_is_flagged(case):
    # Helene's Virginia list prints "Franklin, Franklin".
    case.make_exact()
    case.lists = pd.concat([case.lists, case.lists.iloc[[0]]], ignore_index=True)
    result = case.run()
    assert result.status == "flagged" and "listed more than once" in result.flag_reasons


def test_report_without_cause_columns_is_not_failed_or_counted_as_unattributed(case):
    case.rows[CAUSES] = None
    case.totals[CAUSES] = None
    case.rows = add_unattributed(case.rows)
    case.reprint()
    assert case.run().status == "ok"
    assert case.summary["Sites with no cause"] == "n/a"
    assert case.rows.out_unattributed.isna().all()


def test_names_match_despite_case_spacing_and_punctuation(case):
    case.lists.loc[0, "county"] = "bald-win"
    assert case.run().status == "flagged"  # flagged only for the three short rows


# --- rows, totals and sums ---

def test_zero_rows_fails(case):
    case.rows = case.rows.iloc[0:0]
    case.fails_with("zero county rows")


def test_missing_state_totals_fails_when_a_row_is_unconfirmed(case):
    case.totals = case.totals.iloc[0:0]
    case.lines = case.lines[~case.lines.line.str.contains("BUTLER")]
    case.fails_with("missing state total")


def test_one_of_two_state_totals_missing_fails(case):
    extra = case.rows.iloc[[0]].assign(state="Florida", county="BAY")
    case.rows = pd.concat([case.rows, extra], ignore_index=True)
    case.fails_with("missing state total: Florida")


def test_two_totals_for_one_state_fails(case):
    case.totals = pd.concat([case.totals, case.totals], ignore_index=True)
    case.fails_with("more than one state total")


def test_total_for_a_state_with_no_rows_fails(case):
    case.totals = pd.concat([case.totals, case.totals.assign(state="Florida")], ignore_index=True)
    case.fails_with("state total with no county rows")


@pytest.mark.parametrize("col", ["sites_served", "sites_out"] + CAUSES)
def test_column_not_adding_up_to_printed_total_fails(case, col):
    case.set_total(col, case.totals[col].iloc[0] + 1)
    case.fails_with(f"Alabama {col}")


def test_wrong_sites_out_cell_fails(case):
    case.set_row("CONECUH", "sites_out", 6.0)
    case.fails_with("Alabama sites_out")


def test_wrong_cause_cell_fails(case):
    case.set_row("CONECUH", "out_power", 2.0)
    case.fails_with("Alabama out_power")


def test_missing_cause_cell_fails(case):
    case.set_row("CONECUH", "out_power", None)
    case.fails_with("cause columns incomplete")


def test_causes_in_total_but_not_in_rows_fails(case):
    case.rows[CAUSES] = None
    case.rows = add_unattributed(case.rows)
    case.fails_with("cause columns incomplete")


def test_out_greater_than_served_fails(case):
    case.set_row("CONECUH", "sites_served", 4.0)
    case.fails_with("out > served")


def test_duplicate_county_fails(case):
    case.rows = pd.concat([case.rows, case.rows.iloc[[0]]], ignore_index=True)
    case.fails_with("duplicate county rows")


# --- the report's own county list ---

def test_misread_county_name_fails(case):
    # The Pearl River bug: every sum was right and the name was wrong.
    case.set_row("BALDWIN", "county", "WIN")
    case.fails_with("county names")


def test_listed_county_with_no_row_fails(case):
    case.lists = pd.concat([case.lists, case.lists.iloc[[0]].assign(county="Dallas")], ignore_index=True)
    case.fails_with("county names")


def test_county_row_not_in_list_is_kept_and_flagged(case):
    case.lists = case.lists.iloc[1:]
    case.rows.loc[case.rows.county == "BALDWIN", "area_status"] = "table_not_in_list"
    result = case.run()
    assert result.status == "flagged" and "in table, not in the report's county list: Alabama/BALDWIN" in result.flag_reasons


def test_county_under_wrong_state_fails(case):
    case.lists.loc[0, "state"] = "Florida"
    case.fails_with("county names")


def test_no_county_list_fails(case):
    case.lists = case.lists.iloc[0:0]
    case.fails_with("no county list")


# --- causes exceed sites out ---

def test_confirmed_causes_exceeding_out_are_flagged_and_kept(case):
    case.make_over()
    result = case.run()
    assert result.status == "flagged" and "causes exceed sites out, confirmed by second reading" in result.flag_reasons
    assert result.sites_overattributed == 1


def test_unconfirmed_causes_exceeding_out_fail(case):
    case.make_over()
    case.lines = case.lines[~case.lines.line.str.contains("BALDWIN")]
    case.fails_with("causes exceed sites out")


def test_listed_exception_is_flagged_not_failed(case):
    case.make_over()
    case.allow_over()
    result = case.run()
    assert result.status == "flagged" and "listed exception" in result.flag_reasons


@pytest.mark.parametrize("col", ["sites_served", "sites_out", "pct_out", "on_backup_power"] + CAUSES)
def test_exception_with_different_printed_values_fails(case, col):
    case.make_over()
    case.allow_over(**{col: 999})
    case.fails_with("exception matches no over-attributed row")


@pytest.mark.parametrize("change", [{"county": "BUTLER"}, {"state": "Florida"}])
def test_exception_for_another_row_does_not_apply(case, change):
    case.make_over()
    case.allow_over(**change)
    case.fails_with("exception matches no over-attributed row")


@pytest.mark.parametrize("field", ["page", "checked_on"])
def test_exception_without_page_or_check_date_fails(case, field):
    case.make_over()
    case.allow_over(**{field: None})
    case.fails_with("lacks page or checked_on")


def test_exception_that_matches_no_row_fails(case):
    case.allow_over()
    case.fails_with("exception matches no over-attributed row")


def test_shortfall_and_excess_are_not_netted(case):
    case.make_over()
    case.allow_over()
    result = case.run()
    assert (result.sites_unattributed, result.sites_overattributed) == (3, 1)
    assert case.summary["Sites with no cause"] == "3 of 21"


# --- headline percent ---

def test_headline_gap_fails_when_a_row_is_unconfirmed(case):
    case.reports["pct_sites_out_stated"] = 21.7
    case.lines = case.lines[~case.lines.line.str.contains("BUTLER")]
    case.fails_with("overall % out")


def test_missing_headline_fails(case):
    case.reports["pct_sites_out_stated"] = None
    case.fails_with("stated % out not found")


def test_known_fcc_inconsistency_uses_computed_and_records_stated(case):
    case.reports["pct_sites_out_stated"] = 21.7
    case.allow_headline()
    result = case.run()
    assert result.status == "known_fcc_inconsistency"
    assert result.pct_out_used == pytest.approx(100 * 21 / 1173)
    assert result.stated_pct_out == 21.7


@pytest.mark.parametrize("change", [{"stated_pct": 9.1}, {"total_served": 1}, {"total_out": 1}, {"doc_id": "DOC-2A1"}])
def test_headline_entry_must_match_the_report(case, change):
    # A non-matching entry is not used: the report is a plain headline_mismatch, not a known inconsistency.
    case.reports["pct_sites_out_stated"] = 21.7
    case.allow_headline(**change)
    result = case.run()
    assert result.status == "flagged" and "headline_mismatch" in result.flag_reasons


@pytest.mark.parametrize("field", ["page", "checked_on"])
def test_headline_entry_without_page_or_check_date_fails(case, field):
    case.reports["pct_sites_out_stated"] = 21.7
    case.allow_headline(**{field: None})
    case.fails_with("lacks page or checked_on")


def test_known_headline_never_hides_another_failure(case):
    case.reports["pct_sites_out_stated"] = 21.7
    case.allow_headline()
    case.set_row("CONECUH", "out_power", 2.0)
    case.fails_with("Alabama out_power")


def test_headline_entry_that_is_no_longer_needed_fails(case):
    case.allow_headline(stated_pct=1.8)
    case.fails_with("headline entry not needed")


# --- carried column ---

@pytest.mark.parametrize("col", ["out_unattributed", "out_overattributed"])
def test_dropped_column_fails(case, col):
    case.rows = case.rows.drop(columns=col)
    case.fails_with(col)


def test_altered_unattributed_column_fails(case):
    case.rows["out_unattributed"] = 0.0
    case.fails_with("out_unattributed")


# --- files and exit code, including the three broken inputs step 4 used to pass ---

def run_main(case, tmp_path, monkeypatch):
    for name, df in [("dirs_county_rows", case.rows), ("dirs_state_totals", case.totals),
                     ("dirs_county_lists", case.lists), ("dirs_reports", case.reports),
                     ("dirs_pdf_lines", case.lines), ("dirs_overall_totals", case.overall)]:
        df.to_parquet(tmp_path / f"{name}.parquet", index=False)
    case.over.to_csv(tmp_path / "over.csv", index=False)
    case.headlines.to_csv(tmp_path / "headlines.csv", index=False)
    case.unlisted.to_csv(tmp_path / "unlisted.csv", index=False)
    case.excluded.to_csv(tmp_path / "excluded.csv", index=False)
    monkeypatch.setattr(step4, "EXCLUDED", tmp_path / "excluded.csv")
    monkeypatch.setattr(step4, "INTERIM", tmp_path)
    monkeypatch.setattr(step4, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(step4, "OVER_EXCEPTIONS", tmp_path / "over.csv")
    monkeypatch.setattr(step4, "HEADLINE_EXCEPTIONS", tmp_path / "headlines.csv")
    monkeypatch.setattr(step4, "LIST_EXCEPTIONS", tmp_path / "unlisted.csv")
    with pytest.raises(SystemExit) as stop:
        step4.main()
    return stop.value.code


def second_report_with_no_rows(case):
    other = case.reports.assign(doc_id="DOC-2A1")
    case.reports = pd.concat([case.reports, other], ignore_index=True)


def drop_totals(case):
    # With every row confirmed, no printed totals is now a flag; it still stops the build if a row is unconfirmed.
    case.totals = case.totals.iloc[0:0]
    case.lines = case.lines[~case.lines.line.str.contains("BUTLER")]


def wrong_cause(case):
    case.set_row("CONECUH", "out_power", 2.0)


@pytest.mark.parametrize("breakage", [second_report_with_no_rows, drop_totals, wrong_cause])
def test_three_broken_inputs_now_stop_the_build(case, tmp_path, monkeypatch, breakage):
    breakage(case)
    assert run_main(case, tmp_path, monkeypatch) == 1


def test_every_report_empty_stops_the_build(case, tmp_path, monkeypatch):
    case.rows = pd.DataFrame()
    case.totals = pd.DataFrame()
    assert run_main(case, tmp_path, monkeypatch) == 1


def test_no_reports_at_all_stops_the_build(case, tmp_path, monkeypatch):
    case.reports = case.reports.iloc[0:0]
    assert run_main(case, tmp_path, monkeypatch) == 1


def test_flag_and_known_inconsistency_do_not_stop_the_build(case, tmp_path, monkeypatch):
    case.reports["pct_sites_out_stated"] = 21.7
    case.allow_headline()
    assert run_main(case, tmp_path, monkeypatch) == 0


def test_summary_file_has_the_agreed_columns_and_values(case, tmp_path, monkeypatch):
    run_main(case, tmp_path, monkeypatch)
    got = pd.read_csv(tmp_path / "output" / "validation_summary.csv")
    assert list(got.columns) == ["Report", "Rows", "Exact", "Short by 1", "Short by more", "Causes exceed out",
                                 "Sites with no cause"]
    assert got.iloc[0].tolist() == ["Isaias, Oct 12, 2026 (DOC-1A1)", 12, 9, 3, 0, 0, "3 of 21"]


# --- the committed exception lists ---

def test_only_the_two_helene_rows_are_excepted():
    got = pd.read_csv(ROOT / "manifest" / "cause_exceptions.csv")
    assert sorted(zip(got.doc_id, got.page, got.county)) == [("DOC-406099A1", 8, "Transylvania"),
                                                             ("DOC-406099A1", 9, "Charleston")]
    assert got[step4.OVER_FIELDS].notna().all().all()


def test_only_the_helene_oct_1_headline_is_known():
    got = pd.read_csv(ROOT / "manifest" / "known_fcc_inconsistencies.csv")
    assert got.doc_id.tolist() == ["DOC-406055A1"]
    assert got[step4.HEADLINE_FIELDS].notna().all().all()


def test_only_the_three_checked_counties_are_excepted_from_the_list_check():
    got = pd.read_csv(ROOT / "manifest" / "county_list_exceptions.csv")
    assert sorted(zip(got.doc_id, got.page, got.county)) == [
        ("DOC-387679A1", 5, "OKALOOSA"), ("DOC-404487A1", 3, "Brevard"), ("DOC-405943A1", 5, "Broward")]
    assert got[step4.OVER_FIELDS].notna().all().all()


# --- counties in the table but not in the report's list ---

def test_checked_unlisted_county_is_flagged_and_stays_in_sites_served(case):
    case.make_exact()
    case.lists = case.lists.iloc[1:]
    case.allow_unlisted()
    result = case.run()
    assert result.status == "flagged" and "kept in sites served" in result.flag_reasons
    assert case.summary["Rows"] == 12
    assert result.computed_pct_out == pytest.approx(100 * 21 / 1173)


@pytest.mark.parametrize("col", ["sites_served", "sites_out", "pct_out", "on_backup_power"] + CAUSES)
def test_unlisted_county_entry_with_different_values_fails(case, col):
    case.lists = case.lists.iloc[1:]
    case.allow_unlisted(**{col: 999})
    case.fails_with("county-list exception matches no unlisted row")


@pytest.mark.parametrize("change", [{"county": "BUTLER"}, {"state": "Florida"}])
def test_unlisted_county_entry_for_another_row_does_not_apply(case, change):
    case.lists = case.lists.iloc[1:]
    case.allow_unlisted(**change)
    case.fails_with("county-list exception matches no unlisted row")


def test_unlisted_county_entry_for_another_report_is_not_used_here(case):
    case.lists = case.lists.iloc[1:]
    case.allow_unlisted(doc_id="DOC-2A1")
    result = case.run()
    assert result.status == "flagged" and "listed exception" not in result.flag_reasons
    assert "in table, not in the report's county list: Alabama/BALDWIN" in result.flag_reasons


@pytest.mark.parametrize("field", ["page", "checked_on"])
def test_unlisted_county_entry_without_page_or_check_date_fails(case, field):
    case.lists = case.lists.iloc[1:]
    case.allow_unlisted(**{field: None})
    case.fails_with("lacks page or checked_on")


def test_unlisted_county_entry_that_is_no_longer_needed_fails(case):
    case.allow_unlisted()
    case.fails_with("county-list exception matches no unlisted row")


def test_exception_does_not_excuse_a_listed_county_with_no_row(case):
    case.lists = pd.concat([case.lists.iloc[1:], case.lists.iloc[[1]].assign(county="Dallas")], ignore_index=True)
    case.allow_unlisted()
    case.fails_with("county names")


# --- each row's printed percent ---

def test_wrong_row_percent_fails(case):
    case.set_row("CONECUH", "pct_out", 51.2)
    case.fails_with("row % out")


def test_missing_row_percent_fails(case):
    case.set_row("CONECUH", "pct_out", None)
    case.fails_with("row % out")


def test_row_percent_allows_rounding(case):
    case.set_row("CONECUH", "pct_out", 15.1)  # 15.15 cut to one place rather than rounded
    case.reprint()
    assert case.run().status == "flagged"


def swap(case, first, second, cols):
    a = case.rows.index[case.rows.county == first][0]
    b = case.rows.index[case.rows.county == second][0]
    for col in cols:
        case.rows.loc[a, col], case.rows.loc[b, col] = case.rows.loc[b, col], case.rows.loc[a, col]
    case.rows = add_unattributed(case.rows)


def test_swapped_counties_with_outages_fail_on_percent(case):
    swap(case, "CONECUH", "MONROE", ["sites_served"])
    case.fails_with("row % out")


def test_swapped_counties_with_no_outages_fail_on_second_reading(case):
    # Both rows stay at 0%, so every sum and percent still agrees.
    swap(case, "BUTLER", "CHOCTAW", ["sites_served"])
    result = case.run()
    assert result.status == "fail"
    assert "second reading" in result.failures and "row % out" not in result.failures


def test_whole_rows_swapped_between_counties_fail(case):
    swap(case, "CONECUH", "MONROE", ["sites_served", "sites_out", "pct_out", *CAUSES, "on_backup_power"])
    case.fails_with("second reading")


def test_same_county_name_in_another_state_is_not_a_match(case):
    case.lines["line"] = case.lines.line.str.replace("AL BUTLER", "GA BUTLER")
    case.fails_with("second reading")


def test_no_second_reading_fails(case):
    case.lines = case.lines.iloc[0:0]
    case.fails_with("second reading")


# --- backup power ---

def test_wrong_backup_cell_fails(case):
    case.set_row("BUTLER", "on_backup_power", 15.0)
    case.fails_with("Alabama on_backup_power")


def test_wrong_backup_total_fails(case):
    case.set_total("on_backup_power", 133)
    case.fails_with("Alabama on_backup_power")


def test_missing_backup_cell_fails(case):
    case.set_row("BUTLER", "on_backup_power", None)
    case.fails_with("backup column incomplete")


def swapped_zero_out_counties(case):
    swap(case, "BUTLER", "CHOCTAW", ["sites_served"])


def wrong_backup(case):
    case.set_row("BUTLER", "on_backup_power", 15.0)


@pytest.mark.parametrize("breakage", [swapped_zero_out_counties, wrong_backup])
def test_two_gaps_found_in_review_now_stop_the_build(case, tmp_path, monkeypatch, breakage):
    breakage(case)
    assert run_main(case, tmp_path, monkeypatch) == 1



# --- area status (decided 2026-11-22: a flag, not a failure) ---

def test_rows_outside_the_notice_area_are_kept_and_flagged(case):
    case.rows.loc[case.rows.county.isin(["BUTLER", "CLARKE"]), "area_status"] = "outside_notice_area"
    result = case.run()
    assert result.status == "flagged" and "2 rows outside_notice_area" in result.flag_reasons
    assert result.n_rows == 12


def test_missing_area_status_fails(case):
    case.rows = case.rows.drop(columns="area_status")
    case.fails_with("area_status")


def test_unknown_area_status_fails(case):
    case.rows.loc[case.rows.county == "BUTLER", "area_status"] = "maybe"
    case.fails_with("area_status")


def test_area_counts_file_for_the_methods_section(case, tmp_path, monkeypatch):
    case.rows.loc[case.rows.county == "BUTLER", "area_status"] = "outside_notice_area"
    run_main(case, tmp_path, monkeypatch)
    got = pd.read_csv(tmp_path / "output" / "area_status_counts.csv")
    assert got.columns.tolist() == ["doc_id", "inside", "inside_spelling_variant", "outside_notice_area",
                                    "table_not_in_list", "confirmed_by_second_reading"]
    assert got.iloc[0][["inside", "outside_notice_area", "confirmed_by_second_reading"]].tolist() == [11, 1, True]


# --- rows with no printed percent (Sally 2020) ---

def test_unprinted_percent_is_not_checked_against_the_pdf_or_the_row(case):
    case.rows["pct_printed"] = False
    case.rows["pct_out"] = 100 * case.rows.sites_out / case.rows.sites_served
    lines = []
    for r in case.rows.to_dict("records"):
        values = [f"{r[c]:g}" for c in ["sites_served", "sites_out", *CAUSES, "on_backup_power"]]
        lines.append({"doc_id": DOC, "line": " ".join(["AL", r["county"], *values])})
    case.lines = pd.DataFrame(lines)
    assert case.run().status == "flagged"  # only the three short rows



# --- overall totals (Harvey 2017) and names split across lines in the PDF (Isaias Oct 10, 2026) ---

def test_overall_total_reconciles_when_there_are_no_state_totals(case):
    case.overall = pd.DataFrame([{"doc_id": DOC, "states": "Alabama", "sites_served": 1173.0, "sites_out": 21.0}])
    case.totals = case.totals.iloc[0:0]
    assert case.run().status == "flagged"


def test_overall_total_that_does_not_add_up_fails(case):
    case.overall = pd.DataFrame([{"doc_id": DOC, "states": "Alabama", "sites_served": 1174.0, "sites_out": 21.0}])
    case.totals = case.totals.iloc[0:0]
    case.fails_with("overall sites_served")


def test_second_reading_accepts_any_word_of_the_name():
    # pdfplumber's plain text for DOC-425790A1: "PEARL 72 0 0% 0 0 0 0" then "MS RIVER"
    case_rows = Case()
    case_rows.rows.loc[case_rows.rows.county == "BALDWIN", "county"] = "PEARL BALDWIN"
    case_rows.lists.loc[case_rows.lists.county == "Baldwin", "county"] = "Pearl Baldwin"
    case_rows.lines["line"] = case_rows.lines.line.str.replace("AL BALDWIN 294", "PEARL 294")
    assert "second reading" not in case_rows.run().failures



# --- round 1 rules (2026-11-22) ---

def test_list_spelling_and_county_word_match_the_table(case):
    case.lists.loc[case.lists.county == "Baldwin", "county"] = "Baldwin County"
    case.lists.loc[case.lists.county == "Conecuh", "county"] = "Conecuhh"  # FCC typo, 93% alike
    result = case.run()
    assert result.status == "flagged" and "county names" not in result.failures


def test_one_unmatched_list_name_pairs_with_one_unmatched_table_name(case):
    # Helene Sep 28, 2024: the list prints "Unicorn" for Tennessee's Unicoi
    case.lists.loc[case.lists.county == "Monroe", "county"] = "Monrovia"
    result = case.run()
    assert "county names" not in result.failures and "listed as Monrovia" in result.flag_reasons


def test_headline_mismatch_is_flagged_when_rows_and_totals_check(case):
    case.reports["pct_sites_out_stated"] = 2.4
    result = case.run()
    assert result.status == "flagged" and "headline_mismatch" in result.flag_reasons
    assert result.pct_out_used == pytest.approx(100 * 21 / 1173) and result.stated_pct_out == 2.4


def test_headline_mismatch_still_fails_when_another_check_fails(case):
    case.reports["pct_sites_out_stated"] = 2.4
    case.set_row("CONECUH", "out_power", 2.0)
    case.fails_with("overall % out")


def test_no_printed_totals_is_flagged_when_every_row_is_confirmed(case):
    case.totals = case.totals.iloc[0:0]
    result = case.run()
    assert result.status == "flagged" and "no_printed_totals" in result.flag_reasons


def test_no_printed_totals_fails_when_a_row_is_not_confirmed(case):
    case.totals = case.totals.iloc[0:0]
    case.lines = case.lines[~case.lines.line.str.contains("BUTLER")]
    case.fails_with("missing state total")


def test_one_state_total_missing_among_others_still_fails_when_its_row_is_unconfirmed(case):
    extra = case.rows.iloc[[0]].assign(state="Florida", county="BAY")
    case.rows = pd.concat([case.rows, extra], ignore_index=True)
    case.lists = pd.concat([case.lists, case.lists.iloc[[0]].assign(state="Florida", county="Bay")], ignore_index=True)
    case.fails_with("missing state total: Florida")  # FL BAY is not in the second reading


def test_listed_excluded_report_is_excluded_with_its_reason(case, tmp_path, monkeypatch):
    case.set_row("CONECUH", "out_power", 2.0)
    case.excluded = pd.DataFrame([{"doc_id": DOC, "storm_name": "Isaias", "report_date": "2026-10-12",
                                   "reason": "totals do not reconcile", "decided_on": "2026-11-22"}])
    result = case.run()
    assert result.status == "excluded" and result.failures  # the reason it failed is kept
    assert run_main(case, tmp_path, monkeypatch) == 0
    got = pd.read_csv(tmp_path / "output" / "excluded_reports.csv")
    assert got.doc_id.tolist() == [DOC] and got.reason.tolist() == ["totals do not reconcile"]


def test_exclusion_no_longer_needed_fails(case):
    case.excluded = pd.DataFrame([{"doc_id": DOC, "storm_name": "Isaias", "report_date": "2026-10-12",
                                   "reason": "x", "decided_on": "2026-11-22"}])
    case.fails_with("excluded but now passes")



# --- state_total_missing (2026-11-22): exactly one state with no printed total ---

def two_states(case):
    """Alabama as printed, plus a one-county Florida table whose total the FCC did not print."""
    extra = case.rows.iloc[[0]].assign(state="Florida", county="BAY")
    case.rows = pd.concat([case.rows, extra], ignore_index=True)
    case.lists = pd.concat([case.lists, case.lists.iloc[[0]].assign(state="Florida", county="Bay")], ignore_index=True)
    case.lines = pd.concat([case.lines, pd.DataFrame([{"doc_id": DOC, "line": "FL BAY 294 1 0.3% 0 0 1 24"}])])
    case.reports["pct_sites_out_stated"] = round(100 * 22 / 1467, 1)


def test_one_state_without_a_total_is_kept_and_flagged(case):
    two_states(case)
    result = case.run()
    assert result.status == "flagged" and "state_total_missing: Florida" in result.flag_reasons


def test_one_state_without_a_total_fails_if_its_rows_are_not_confirmed(case):
    two_states(case)
    case.lines = case.lines[~case.lines.line.str.startswith("FL BAY")]
    case.fails_with("missing state total: Florida")


def test_one_state_without_a_total_fails_if_another_state_does_not_reconcile(case):
    two_states(case)
    case.set_total("sites_served", 1174)
    case.fails_with("missing state total: Florida")


def test_two_states_without_totals_still_fail(case):
    two_states(case)  # Florida has no total; Alabama keeps its total
    extra = case.rows.iloc[[0]].assign(state="Georgia", county="APPLING")
    case.rows = pd.concat([case.rows, extra], ignore_index=True)
    case.lists = pd.concat([case.lists, case.lists.iloc[[0]].assign(state="Georgia", county="Appling")], ignore_index=True)
    case.lines = pd.concat([case.lines, pd.DataFrame([{"doc_id": DOC, "line": "GA APPLING 294 1 0.3% 0 0 1 24"}])])
    case.fails_with("missing state total: Florida")


# --- the FCC's multiple-causes note (2026-11-22) ---

def test_multiple_causes_note_is_recorded(case):
    # Idalia Aug 30, 2023 (DOC-396514A1), across two PDF lines
    note = pd.DataFrame([{"doc_id": DOC, "line": "The number of total cell sites out may differ from the sum of numbers of cell"},
                         {"doc_id": DOC, "line": "sites out by cause. This is due to sites being out due to multiple causes or"}])
    case.lines = pd.concat([case.lines, note], ignore_index=True)
    assert case.run().fcc_multiple_causes_note


def test_no_note_is_recorded_as_false(case):
    assert not case.run().fcc_multiple_causes_note
