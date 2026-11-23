"""Columns that must be carried from step 3 through to the panel and the public CSV.

out_unattributed    sites out with no cause given (sites out minus the three causes, never below 0)
out_overattributed  causes in excess of sites out: consistent with sites counted under more than one cause, not an
                    FCC error (the FCC notes that "sites being out due to multiple causes" can make the counts differ)

The two are kept apart because netting them understates the sites with no cause. For every row with causes:
    damage + transport + power + out_unattributed - out_overattributed = sites_out
Both are empty, not zero, where a report has no cause columns.
"""
import pandas as pd

CAUSES = ["out_damage", "out_transport", "out_power"]
CARRIED = ["out_unattributed", "out_overattributed"]


def add_unattributed(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in CAUSES:
        df[col] = pd.to_numeric(df[col]).astype(float)
    gap = df["sites_out"].astype(float) - df[CAUSES].sum(axis=1, skipna=False)
    df["out_unattributed"] = gap.clip(lower=0)
    df["out_overattributed"] = (-gap).clip(lower=0)
    return df


def require_carried(df: pd.DataFrame, where: str) -> None:
    """Raise if a table has dropped or altered a carried column. Call it on every table written downstream."""
    missing = [col for col in CARRIED if col not in df.columns]
    if missing:
        raise ValueError(f"{where}: dropped {', '.join(missing)}")
    want = add_unattributed(df)
    for col in CARRIED:
        if not pd.to_numeric(df[col]).astype(float).equals(want[col]):
            raise ValueError(f"{where}: {col} does not equal the value implied by sites out and the causes")
