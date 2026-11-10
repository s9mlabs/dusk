import json
import math
from pathlib import Path
import numpy as np
from nexus.circuits.build import build_circuit, load_motifs
from nexus.circuits.corrupt import corrupt_wiring, true_edges
from nexus.score.recovery import order_agreement
from nexus.score.report import score_prediction

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = json.loads((ROOT / "prereg" / "thresholds-0.3.json").read_text())

def test_predicted_tie_is_disagreement():
    assert order_agreement({"a": 1, "b": 1}, {"a": 1, "b": 2}) == 0.0
    assert order_agreement({"a": 1, "b": 1}, {"a": 2, "b": 1}) == 0.0
    assert order_agreement({"a": 1, "b": 2}, {"a": 1, "b": 2}) == 1.0

def test_ceiling_samples_floored_after_exclusion():
    rng = np.random.default_rng(0)
    rows = [{"ceiling_samples": np.full(20, 0.6), "r": {"dusk": 0.5 + 0.01 * rng.normal(), "baseline1_pooled": 0.3 + 0.01 * rng.normal(), "baseline1_per_state": 0.3 + 0.01 * rng.normal(), "baseline4": 0.3 + 0.01 * rng.normal()}} for _ in range(40)]
    rows[0]["ceiling_samples"][:5] = 0.0
    rows[1]["ceiling_samples"] = np.full(20, 0.05)
    out = score_prediction(rows, "dusk", THRESHOLDS, n_boot=500)
    assert out["n_excluded_low_ceiling"] == 1
    for name in ["baseline1_pooled", "baseline1_per_state"]:
        assert math.isfinite(out["comparisons"][name]["low"])
        assert math.isfinite(out["comparisons"][name]["high"])

def test_strength_errors_are_log10():
    common, motifs = load_motifs(ROOT / "configs" / "motifs")
    spec, roles = build_circuit("global_shutoff", common, motifs, np.random.default_rng([0, 0]), "global_shutoff_00000")
    true = {(e["pre"], e["post"]): e["weight"] for e in true_edges(spec)}
    rates = {"missing_edge": 0.0, "false_edge": 0.0, "sign_flip": 0.0, "weight_sd_log": 0.3}
    logs = []
    for seed in range(300):
        stored, rows = corrupt_wiring(spec, rates, np.random.default_rng(seed))
        for e in stored:
            logs.append(math.log10(e["weight"] / true[(e["pre"], e["post"])]))
    assert abs(float(np.std(logs)) - 0.3) < 0.02
    assert abs(float(np.mean(logs))) < 0.02

def test_corruption_config_is_settled():
    cfg = json.loads((ROOT / "configs" / "corruption.json").read_text())
    assert cfg["provisional"] is False
    assert cfg["units"]["weight_sd_log"] == "log10"
    assert cfg["rates"] == {"missing_edge": 0.1, "false_edge": 0.05, "sign_flip": 0.05, "weight_sd_log": 0.3}

def test_thresholds_match_version_02_where_unchanged():
    old = json.loads((ROOT / "prereg" / "thresholds.json").read_text())
    for key in ("no_false_switch", "leak", "tie", "held_out", "exclusion"):
        assert THRESHOLDS[key] == old[key]
    assert THRESHOLDS["recovery"]["max_width_fraction_of_prior"] == old["recovery"]["max_width_fraction_of_prior"]
    assert THRESHOLDS["recovery"]["pass_fraction_of_switch_circuits"] == old["recovery"]["pass_fraction_of_switch_circuits"]
    assert THRESHOLDS["recovery"]["interval_level_scope"] == "joint_per_circuit"
