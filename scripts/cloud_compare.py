import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMERIC = ("trigger_gain", "threshold", "tau_on_over_tau_ref", "tau_off_over_tau_ref", "reach")
EXACT = ("accepted", "tries", "n_neurons", "n_trials", "n_bad_trials")

def rel_diff(a, b) -> float:
    if a is None or b is None:
        return float("nan")
    a = float(a)
    b = float(b)
    if not (math.isfinite(a) and math.isfinite(b)):
        return 0.0 if (a == b or (math.isnan(a) and math.isnan(b))) else float("inf")
    return abs(a - b) / max(abs(a), abs(b), 1e-12)

def compare_pair(old, new) -> dict:
    mismatched = [k for k in EXACT if old.get(k) != new.get(k)]
    diffs = []  # list of (label, rel) tuples
    old_sheets = {d["gate_id"]: d for d in old.get("datasheets") or []}
    new_sheets = {d["gate_id"]: d for d in new.get("datasheets") or []}
    if sorted(old_sheets) != sorted(new_sheets):
        mismatched.append("gate_ids")
    for g in sorted(set(old_sheets) & set(new_sheets)):
        for f in NUMERIC:
            diffs.append((f"datasheet.{g}.{f}", rel_diff(old_sheets[g].get(f), new_sheets[g].get(f))))
    old_gr = old.get("gate_ratios") or []
    new_gr = new.get("gate_ratios") or []
    if len(old_gr) != len(new_gr):
        mismatched.append("gate_ratios_length")
    for i in range(min(len(old_gr), len(new_gr))):
        diffs.append((f"gate_ratio.{i}", rel_diff(old_gr[i], new_gr[i])))
    old_cr = old.get("cross_ratios") or {}
    new_cr = new.get("cross_ratios") or {}
    if sorted(old_cr) != sorted(new_cr):
        mismatched.append("cross_ratio_keys")
    for k in sorted(set(old_cr) & set(new_cr)):
        diffs.append((f"cross_ratio.{k}", rel_diff(old_cr[k], new_cr[k])))
    finite = [d for d in diffs if not math.isnan(d[1])]
    worst = max(finite, key=lambda d: d[1]) if finite else ("none", 0.0)
    return {"seed": new["seed"], "motif": new["motif"], "mismatched": mismatched, "n_values": len(finite), "max_rel_diff": worst[1], "worst": worst[0]}

def main():
    name = sys.argv[1]
    old = {int(r["seed"]): r for r in json.loads((ROOT / "logs" / "pilot" / "m3" / "results.json").read_text())}
    new = json.loads((ROOT / "outputs" / "cloud" / name / "results.json").read_text())
    rows = [compare_pair(old[int(r["seed"])], r) for r in sorted(new, key=lambda r: int(r["seed"]))]
    for r in rows:
        print(f"{r['motif']:18s} {r['seed']} mismatched={r['mismatched']} values={r['n_values']} max_rel_diff={r['max_rel_diff']:.3g} ({r['worst']})")
    all_max = max((r["max_rel_diff"] for r in rows), default=0.0)
    report = {"name": name, "n_circuits": len(rows), "n_with_mismatch": sum(1 for r in rows if r["mismatched"]), "n_values": sum(r["n_values"] for r in rows), "max_rel_diff": all_max, "rows": rows}
    (ROOT / "outputs" / "cloud" / name / "compare.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}))

if __name__ == "__main__":
    main()
