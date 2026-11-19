r"""Demo B step 3c, final: apply the approved fuzzy rule (fuzzy3c) plus the
hand-approved national-alias links (review/b_3c_alias_candidates.csv,
approve = Y). The rule is NOT adjusted using the step-3d labels.

Outputs
  data/interim/osha_resolved.csv           full rows + final employer id/label
  data/processed/osha_upa_employer.csv     UPA -> employer_id, employer_label
  results/osha_audit.json ["step3c_final"], ["final_tables"]
  results/figures/b_before_after.csv, b_waterfall.csv, b_waterfall.png

    .venv\Scripts\python -m osha_audit.src.step3c_apply
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from osha_audit.src.download import RAW, read_member
from osha_audit.src.duplicates import clusters
from osha_audit.src.entities3b import counts
from osha_audit.src.fuzzy3c import canon, generic_tokens
from osha_audit.src.naive import MEMBER, naive_counts, save_results
from osha_audit.src.step3c_preview import entity_table, resolve

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data/interim/osha_step3b.csv"
ALIASES = ROOT / "review/b_3c_alias_candidates.csv"
FIG = ROOT / "results/figures"
INK, MUTED, RULE = "#0F2338", "#51626F", "#C9D1D8"


def alias_links(E, alias_df):
    """Approved (Y) alias rows -> list of (entity_a, entity_b). Names are
    the 3b entity labels; each must identify exactly one entity."""
    ids = E.groupby("label").entity.apply(list)
    links = []
    for r in alias_df[alias_df.approve.str.upper() == "Y"].itertuples():
        for nm in (r.name_a, r.name_b):
            if len(ids.get(nm, [])) != 1:
                raise ValueError(f"alias name {nm!r} matches {len(ids.get(nm, []))} entities")
        links.append((ids[r.name_a][0], ids[r.name_b][0]))
    return links


def merge_entities(d, link_pairs, col_in="entity", col_out="employer_id"):
    root = {}
    for c in clusters(link_pairs):
        r = min(c)
        for v in c:
            root[v] = r
    out = d.copy()
    out[col_out] = out[col_in].map(lambda e: root.get(e, e))
    lab = out.groupby(col_out).Employer.agg(lambda s: s.value_counts().index[0])
    out["employer_label"] = out[col_out].map(lab)
    return out


def resolved_top(r, top=15):
    g = r.groupby("employer_id")
    t = pd.DataFrame({"employer": g.employer_label.first(), "reports": g.size(),
                      "raw_variants": g.Employer.nunique(), "states": g.State.nunique(),
                      "federalstate0_reports": g.FederalState.agg(lambda s: int((s == "0").sum()))})
    t = t.reset_index(drop=True).sort_values(["reports", "employer"], ascending=[False, True]).head(top)
    t["pct_of_reports"] = 100 * t.reports / len(r)
    t.insert(0, "rank", range(1, len(t) + 1))
    return t.reset_index(drop=True)


def waterfall_rows(raw, a3, b3, c3_fuzzy, final):
    def row(step, df, col):
        fs0 = df[df.FederalState == "0"]
        return {"step": step,
                "employers_by_name": int(df[col].nunique()),
                "employers_by_name_and_state": int(df[[col, "State"]].drop_duplicates().shape[0]),
                "federalstate0_employers_by_name": int(fs0[col].nunique()),
                "federalstate0_employers_by_name_and_state": int(fs0[[col, "State"]].drop_duplicates().shape[0]),
                "reports": int(len(df)), "federalstate0_reports": int(len(fs0))}
    return pd.DataFrame([
        row("Raw employer field", raw, "Employer"),
        row("3a: duplicates removed", a3, "Employer"),
        row("3b: names normalized", b3, "entity"),
        row("3c: fuzzy matching", c3_fuzzy, "entity3c"),
        row("3c: national aliases (final)", final, "employer_id"),
    ])


def plot_waterfall(w, path):
    fig, ax = plt.subplots(figsize=(9, 4.6), dpi=150)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.grid(axis="y", color=RULE, linewidth=0.8); ax.set_axisbelow(True)
    vals = w.employers_by_name.tolist()
    x = range(len(vals))
    for i, v in enumerate(vals):
        if i == 0:
            ax.bar(i, v, color=INK, width=0.6)
        else:
            drop = vals[i - 1] - v
            ax.bar(i, drop, bottom=v, color=MUTED if i < len(vals) - 1 else MUTED, width=0.6)
            ax.text(i, vals[i - 1] + 600, f"−{drop:,}", ha="center", color=INK, fontsize=8.5)
    ax.bar(len(vals), vals[-1], color=INK, width=0.6)
    ax.text(0, vals[0] + 600, f"{vals[0]:,}", ha="center", color=INK, fontsize=8.5)
    ax.text(len(vals), vals[-1] + 600, f"{vals[-1]:,}", ha="center", color=INK, fontsize=8.5)
    labels = ["Raw names", "Duplicates\nremoved", "Names\nnormalized", "Fuzzy\nmatching", "National\naliases", "Employers\n(final)"]
    ax.set_xticks(list(range(len(vals) + 1)))
    ax.set_xticklabels(labels, color=MUTED, fontsize=8.5)
    ax.set_ylabel("Distinct employers (by name)", color=MUTED, fontsize=9)
    ax.set_title("How each audit step changed the count of distinct employers", color=INK,
                 fontsize=10.5, loc="left")
    ax.set_ylim(0, vals[0] * 1.12)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def main():
    raw = read_member(RAW, MEMBER)
    a3 = pd.read_csv(ROOT / "data/interim/osha_step3a.csv", dtype=str, keep_default_na=False)
    d = pd.read_csv(IN, dtype=str, keep_default_na=False)
    d["entity"] = d.entity.astype(int)
    E = entity_table(d)
    generic = generic_tokens(E.name.map(canon))
    r, stats, matched = resolve(d, E, generic)
    links = alias_links(E, pd.read_csv(ALIASES, dtype=str, keep_default_na=False))
    final = merge_entities(d, matched + links)
    final.to_csv(ROOT / "data/interim/osha_resolved.csv", index=False)
    final[["UPA", "employer_id", "employer_label"]].to_csv(ROOT / "data/processed/osha_upa_employer.csv", index=False)

    w = waterfall_rows(raw, a3, d, r, final)
    FIG.mkdir(parents=True, exist_ok=True)
    w.to_csv(FIG / "b_waterfall.csv", index=False)
    plot_waterfall(w, FIG / "b_waterfall.png")

    naive_top, _ = naive_counts(raw)
    res_top = resolved_top(final)
    ba = pd.DataFrame({"rank": range(1, 16),
                       "naive_employer": naive_top.employer, "naive_reports": naive_top.reports,
                       "resolved_employer": res_top.employer, "resolved_reports": res_top.reports,
                       "resolved_pct_of_reports": res_top.pct_of_reports,
                       "resolved_raw_variants": res_top.raw_variants, "resolved_states": res_top.states,
                       "resolved_federalstate0_reports": res_top.federalstate0_reports})
    fs0_line = {"naive_federalstate0_reports": int((raw.FederalState == "0").sum()),
                "resolved_federalstate0_reports": int((final.FederalState == "0").sum()),
                "resolved_federalstate0_employers": int(final.loc[final.FederalState == "0", "employer_id"].nunique())}
    ba.to_csv(FIG / "b_before_after.csv", index=False)
    save_results("step3c_final", {**stats, "alias_links_applied": len(links),
                                  "final_counts": counts(final.assign(entity=final.employer_id)),
                                  "rule_tuned_on_3d_labels": False})
    save_results("final_tables", {"before_after": ba.to_dict(orient="records"),
                                  "federalstate0_line": fs0_line,
                                  "waterfall": w.to_dict(orient="records")})
    return ba, w, fs0_line


if __name__ == "__main__":
    ba, w, fs0 = main()
    print(ba.round(2).to_string(index=False)); print(fs0)
    print(w.to_string(index=False))
