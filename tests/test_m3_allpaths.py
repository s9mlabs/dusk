import math
from pathlib import Path
import numpy as np
from nexus.circuits.allpaths import GATED_PATHS, combine_datasheets, measure_all_paths
from nexus.circuits.build import build_circuit, load_motifs
from nexus.circuits.library import scaled_rates
from nexus.circuits.probe import measure_circuit

ROOT = Path(__file__).resolve().parents[1]
COMMON, MOTIFS = load_motifs(ROOT / "configs" / "motifs")

def sheet(gain, threshold, tau_on, tau_off, reach):
    return {"gate_id": "g0", "trigger_channel": "trig", "priority": 0, "trigger_gain": gain, "threshold": threshold,
            "tau_on_over_tau_ref": tau_on, "tau_off_over_tau_ref": tau_off, "reach": reach}

def test_combine_geometric_and_ordinary_means():
    out = combine_datasheets([sheet(2.0, 10.0, 0.5, 4.0, 0.2), sheet(8.0, 20.0, 2.0, 1.0, 0.4)])
    assert math.isclose(out["trigger_gain"], 4.0)
    assert math.isclose(out["tau_on_over_tau_ref"], 1.0)
    assert math.isclose(out["tau_off_over_tau_ref"], 2.0)
    assert math.isclose(out["threshold"], 15.0)
    assert math.isclose(out["reach"], 0.3)
    assert out["trigger_channel"] == "trig"
    assert out["gate_id"] == "g0"

def test_combine_bad_value_gives_nan():
    out = combine_datasheets([sheet(0.0, 10.0, 1.0, 1.0, 0.2), sheet(8.0, math.nan, 1.0, 1.0, 0.4)])
    assert math.isnan(out["trigger_gain"])
    assert math.isnan(out["threshold"])
    assert math.isclose(out["reach"], 0.3)

def test_only_global_shutoff_has_several_paths():
    assert list(GATED_PATHS) == ["global_shutoff"]
    assert len(GATED_PATHS["global_shutoff"]) == 2

def test_scaled_rates():
    r = scaled_rates({"missing_edge": 0.1, "false_edge": 0.05, "sign_flip": 0.05, "weight_sd_log": 0.3}, 2.0)
    assert math.isclose(r["missing_edge"], 0.2)
    assert math.isclose(r["false_edge"], 0.1)
    assert math.isclose(r["sign_flip"], 0.1)
    assert math.isclose(r["weight_sd_log"], 0.6)

def test_global_shutoff_measures_both_paths(tmp_path):
    spec, roles = build_circuit("global_shutoff", COMMON, MOTIFS, np.random.default_rng([0, 0]), "global_shutoff_00000")
    m = measure_all_paths(spec, roles, "global_shutoff", tmp_path)
    assert m["accepted"] is True
    assert len(m["path_datasheets"]) == 2
    assert len(m["datasheets"]) == 1
    assert math.isclose(m["datasheets"][0]["trigger_gain"], math.sqrt(m["path_datasheets"][0]["trigger_gain"] * m["path_datasheets"][1]["trigger_gain"]), rel_tol=1e-9)
    assert math.isclose(m["datasheets"][0]["threshold"], (m["path_datasheets"][0]["threshold"] + m["path_datasheets"][1]["threshold"]) / 2, rel_tol=1e-9)

def test_other_types_unchanged(tmp_path):
    spec, roles = build_circuit("release", COMMON, MOTIFS, np.random.default_rng([0, 0]), "release_00000")
    a = measure_all_paths(spec, roles, "release", tmp_path / "a")
    b = measure_circuit(spec, roles, tmp_path / "b")
    assert "path_datasheets" not in a
    assert a["accepted"] == b["accepted"]
    assert a["datasheets"] == b["datasheets"]
