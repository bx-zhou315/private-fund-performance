"""Compare the five-row ChatGPT pilot to an independently captured table snapshot."""
import json

import pandas as pd

from analyse import KEYS, ROOT, SCHEMA

source = pd.read_csv(ROOT / "data/source_rows.tsv", sep="\t", names=SCHEMA,
                     dtype=str, keep_default_na=False, quoting=3).set_index(KEYS)
pilot = pd.read_csv(ROOT / "workflow/ai_pilot.csv", dtype=str, keep_default_na=False)
if pilot.columns.tolist() != SCHEMA or pilot.duplicated(KEYS).any() or pilot.empty:
    raise ValueError("Pilot schema or row identity is invalid")
pilot = pilot.set_index(KEYS)
expected = source.loc[pilot.index, pilot.columns]
differences = pilot.compare(expected, result_names=("pilot", "source"))
summary = {
    "rows_compared": len(pilot),
    "fields_per_row": len(pilot.columns),
    "field_matches": int(pilot.eq(expected).to_numpy().sum()),
    "differing_rows": len(differences),
}
print(json.dumps(summary, indent=2))
if not differences.empty:
    raise SystemExit(differences.to_string())
(ROOT / "outputs/ai_pilot_check.json").write_text(json.dumps(summary, indent=2) + "\n")
