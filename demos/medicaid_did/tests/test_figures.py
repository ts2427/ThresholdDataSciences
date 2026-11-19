import pandas as pd

from medicaid_did.src.figures import export_event_study, plot_event_study


def _res():
    ev = [{"spec": "pop", "e": e, "att": (None if e == -1 else float(e)), "se": 1.0,
           "lo": (None if e == -1 else e - 1.0), "hi": (None if e == -1 else e + 1.0),
           "lo_uniform": None, "hi_uniform": None, "crit_uniform": 2.3} for e in range(-2, 2)]
    return {"step2_main": {"event_study": {"pop": ev}}}


def test_export_event_study_reference_zero(tmp_path):
    ev = export_event_study(_res(), tmp_path / "ev.csv")
    ref = ev[ev.e == -1].iloc[0]
    assert ref.att == 0 and ref.lo == 0 and ref.hi == 0
    assert pd.read_csv(tmp_path / "ev.csv").shape[0] == 4


def test_plot_event_study_writes_png(tmp_path):
    export_event_study(_res(), tmp_path / "ev.csv")
    plot_event_study(tmp_path / "ev.csv", tmp_path / "ev.png")
    assert (tmp_path / "ev.png").stat().st_size > 1000
