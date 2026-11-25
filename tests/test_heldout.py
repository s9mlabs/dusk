import json
from pathlib import Path
import numpy as np
import pytest
from pynwb import NWBHDF5IO
from nexus.circuits.build import load_motifs
from nexus.circuits.library import generate_animal_split
from nexus.format.ground_truth import read_ground_truth
from nexus.format.heldout import HELD_OUT_SEEDS, NORMAL_SEEDS, make_library_split, neuron_sides, noise_seed_count, withheld_mask
from nexus.format.inputs import read_inputs
from nexus.format.locking import decrypt_file, generate_placeholder_identity
from nexus.perturb.protocol import N_KEEP, trial_table
from nexus.models.data import _text

ROOT = Path(__file__).resolve().parents[1]
COMMON, MOTIFS = load_motifs(ROOT / "configs" / "motifs")
RATES = {"missing_edge": 0.0, "false_edge": 0.0, "sign_flip": 0.0, "weight_sd_log": 0.0}
POKE_TYPES = ["dep_small", "dep_large", "hyp", "brief", "long", "paired", "paired_step", "paired_both"]
SPLIT = {"schema_version": "0.1.0", "seed": 0, "test_fraction": 0.2, "val_fraction": 0.2, "circuits": {"train": ["decoy_shunt_00000"], "val": [], "test": ["release_00000"]}, "poke_types": {"train": ["dep_small", "dep_large", "brief", "paired", "paired_step", "paired_both"], "val": ["long"], "test": ["hyp"]}, "states": {"train": [0, 1, 2, 3], "val": [4], "test": [5]}}

def read_public(path):
    with NWBHDF5IO(str(path), "r") as io:
        f = io.read()
        return {
            "meta": list(f.lab_meta_data.keys()),
            "scratch": list(f.scratch.keys()),
            "data": f.acquisition["membrane_potential"].data[:],
            "inputs": read_inputs(f),
            "roles": json.loads(_text(f.get_scratch("roles_json"))),
            "description": f.session_description,
            "poke_type": list(f.trials["poke_type"][:]),
            "state_index": [int(x) for x in f.trials["state_index"][:]],
            "seed_index": [int(x) for x in f.trials["seed_index"][:]],
            "columns": list(f.trials.colnames)
        }

@pytest.fixture(scope="module")
def made(tmp_path_factory):
    root = tmp_path_factory.mktemp("heldout")
    secret, public = generate_placeholder_identity()
    held = generate_animal_split("release", COMMON, MOTIFS, RATES, 0, root / "work", root / "out", SPLIT, recipient=public)
    train = generate_animal_split("decoy_shunt", COMMON, MOTIFS, RATES, 0, root / "work", root / "out", SPLIT, recipient=public)
    return {"root": root, "secret": secret, "held": held, "train": train}

def test_split_is_deterministic_and_partitions():
    ids = [f"c{i}" for i in range(10)]
    a = make_library_split(ids, POKE_TYPES, range(6), 0)
    b = make_library_split(ids, POKE_TYPES, range(6), 0)
    assert a == b
    for key, units in (("circuits", ids), ("poke_types", POKE_TYPES), ("states", list(range(6)))):
        parts = a[key]
        assert sorted(parts["train"] + parts["val"] + parts["test"]) == sorted(units)
        assert len(parts["test"]) >= 1 and len(parts["val"]) >= 1

def test_noise_seed_count():
    assert noise_seed_count(SPLIT, "release_00000") == HELD_OUT_SEEDS == 10
    assert noise_seed_count(SPLIT, "decoy_shunt_00000") == NORMAL_SEEDS == 3

def test_neuron_sides():
    names = ["a", "b", "c", "d", "e"]
    assert set(neuron_sides(SPLIT, "release_00000", names).values()) == {"test"}
    s1 = neuron_sides(SPLIT, "decoy_shunt_00000", names)
    assert s1 == neuron_sides(SPLIT, "decoy_shunt_00000", names)
    assert "test" in s1.values() and "train" in s1.values()

def test_withheld_mask_rules():
    names = ["a", "b", "c", "d", "e"]
    pokes = [{"type": "dep_small"}, {"type": "hyp"}]
    trials = [{"poke_index": 0, "state_index": 0}, {"poke_index": 1, "state_index": 0}, {"poke_index": 0, "state_index": 5}]
    m = withheld_mask(SPLIT, "decoy_shunt_00000", names, trials, pokes)
    sides = neuron_sides(SPLIT, "decoy_shunt_00000", names)
    assert m.shape == (3, 5)
    assert m[1].all() and m[2].all()
    assert list(m[0]) == [sides[n] == "test" for n in names]
    assert withheld_mask(SPLIT, "release_00000", names, trials, pokes).all()

def test_trial_table_seeds():
    pokes = [{"type": "dep_small"}] * 2
    t10 = trial_table(pokes, 10)
    assert len(t10) == 2 * 6 * 10
    assert sorted({t["seed_index"] for t in t10}) == list(range(10))
    assert len(trial_table(pokes)) == 2 * 6 * 3

def test_held_out_public_file_hides_answers(made):
    h = made["held"]
    assert h["accepted"]
    assert "circuit_id" not in h and "datasheets" not in h
    pid = h["public_id"]
    assert pid.startswith("h") and len(pid) == 17
    out = made["root"] / "out"
    p = read_public(out / f"{pid}.nwb")
    assert "nexus_ground_truth" not in p["meta"]
    assert "circuit_spec_json" not in p["scratch"]
    assert set(p["roles"]) == {"inputs", "outputs", "state"}
    assert "release" not in p["description"]
    assert np.isnan(p["data"]).all()
    assert "circuit_seed" not in p["inputs"] and "currents_sha256" not in p["inputs"]
    assert max(p["seed_index"]) == 9
    assert not (out / f"{pid}.wiring_checks.json").exists()

def test_held_out_private_files_decrypt(made):
    pid = made["held"]["public_id"]
    out = made["root"] / "out"
    decrypt_file(out / f"{pid}.private.json.age", made["root"] / "p.json", made["secret"])
    info = json.loads((made["root"] / "p.json").read_text())
    assert info["circuit_id"] == "release_00000" and info["side"] == "test" and len(info["datasheets"]) >= 1
    decrypt_file(out / f"{pid}.private.nwb.age", made["root"] / "p.nwb", made["secret"])
    with NWBHDF5IO(str(made["root"] / "p.nwb"), "r") as io:
        assert read_ground_truth(io.read())["switch_type"] == "release"

def test_no_plaintext_left(made):
    root = made["root"]
    names = [x.name for x in root.rglob("*")]
    assert not any(n.endswith(".private.nwb") or n.endswith(".private.json") for n in names)
    assert not (root / "work" / "release_00000_try0").exists()

def test_training_public_file(made):
    t = made["train"]
    assert t["accepted"] and t["circuit_id"] == "decoy_shunt_00000" and t["public_id"] == "decoy_shunt_00000"
    out = made["root"] / "out"
    p = read_public(out / "decoy_shunt_00000.nwb")
    assert "nexus_ground_truth" in p["meta"]
    assert "withheld" in p["columns"]
    assert max(p["seed_index"]) == 2
    ids = [str(x.decode() if isinstance(x, bytes) else x) for x in p["inputs"]["neuron_ids"]]
    sides = neuron_sides(SPLIT, "decoy_shunt_00000", ids)
    n = len(p["poke_type"])
    v = p["data"].reshape(n, N_KEEP, len(ids))
    for k in range(n):
        held_trial = p["poke_type"][k] == "hyp" or p["state_index"][k] == 5
        for j, name in enumerate(ids):
            expect_nan = held_trial or sides[name] == "test"
            assert bool(np.isnan(v[k, :, j]).all()) == expect_nan
    assert (out / "decoy_shunt_00000.wiring_checks.json").exists()
