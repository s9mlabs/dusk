import json
from pathlib import Path
import numpy as np
import secrets
import shutil

from nexus.circuits.build import build_circuit
from nexus.circuits.allpaths import measure_all_paths
from nexus.circuits.batch import BatchRunner
from nexus.circuits.corrupt import corrupt_wiring
from nexus.circuits.graded import write_network
from nexus.circuits.probe import V_HIGH, V_LOW, measure_circuit
from nexus.circuits.write_run import write_run
from nexus.perturb.protocol import DT, T_TRIAL, make_pokes, run_trials, trial_table
from nexus.format.heldout import RECIPIENT, circuit_side, noise_seed_count, withheld_mask
from nexus.format.locking import encrypt_file

def scaled_rates(rates, factor) -> dict:
    """The wiring error settings with every value multiplied by factor."""
    return {k: float(v) * factor for k, v in rates.items()}

def sample_accepted(motif_name, common, motifs, seed, workdir, max_tries=10) -> dict:
    """Draw circuits from a motif until one passes the probe; give up after max_tries."""
    workdir = Path(workdir); reasons = []
    circuit_id = f"{motif_name}_{seed:05d}"
    for i in range(max_tries):
        spec, roles = build_circuit(motif_name, common, motifs, np.random.default_rng([seed, i]), circuit_id)
        m = measure_all_paths(spec, roles, motifs[motif_name]["switch_type"], workdir / f"{circuit_id}_try{i}")
        reasons.append(m["reason"])
        if m["accepted"]:
            return {"spec": spec, "roles": roles, "measurement": m, "tries": i + 1, "reasons": reasons}
    return {"spec": None, "roles": None, "measurement": None, "tries": max_tries, "reasons": reasons}

def generate_animal(motif_name, common, motifs, rates, seed, workdir, out_path, max_tries=10, batch_size=100) -> dict:
    """Make one accepted circuit, simulate all its trials for one wiring-corruption draw, and write the NWB file."""
    workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)
    s = sample_accepted(motif_name, common, motifs, seed, workdir, max_tries)
    if s["spec"] is None: return {"accepted": False, "tries": s["tries"], "reasons": s["reasons"]}
    spec, roles, m = s["spec"], s["roles"], s["measurement"]
    stored, rows = corrupt_wiring(spec, rates, np.random.default_rng([seed, 1000]))
    pokes = make_pokes(spec, roles, np.random.default_rng([seed, 2000]))
    trials = trial_table(pokes)
    ids = [n["id"] for n in spec["neurons"]]
    nml = workdir / f"{spec['circuit_id']}.trials.net.nml"; write_network(spec, nml)
    runner = BatchRunner(nml, ids, DT, T_TRIAL)
    hashes = []
    v = run_trials(runner, spec, ids, roles, pokes, trials, seed, batch_size, hashes)
    bad = int(np.sum(~np.all(np.isfinite(v) & (v >= V_LOW) & (v <= V_HIGH), axis=(1, 2))))
    animal_id = f"{spec['circuit_id']}_a0"
    write_run(out_path, spec, roles, m, stored, rows, pokes, trials, v, hashes, seed, "", spec["circuit_id"], animal_id)
    checks = {"base": {k: float(v) for k, v in rates.items()}}
    for k, (label, factor) in enumerate((("half", 0.5), ("double", 2.0)), start=1):
        checks[label] = {"rates": scaled_rates(rates, factor), "stored": corrupt_wiring(spec, scaled_rates(rates, factor), np.random.default_rng([seed, 1000 + k]))[0]}
    checks_path = Path(out_path).with_suffix(".wiring_checks.json")
    checks_path.write_text(json.dumps(checks, default=float))
    return {"accepted": True, "tries": s["tries"], "reasons": s["reasons"], "circuit_id": spec["circuit_id"], "animal_id": animal_id, "n_neurons": len(ids), "n_trials": len(trials), "n_bad_trials": bad, "datasheets": m["datasheets"], "gate_ratios": m["gate_ratios"], "cross_ratios": m["cross_ratios"], "wiring_checks": str(checks_path)}

def generate_animal_split(motif_name, common, motifs, rates, seed, workdir, out_dir, split, recipient=RECIPIENT, max_tries=10, batch_size=100) -> dict:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    circuit_id = f"{motif_name}_{seed:05d}"
    side = circuit_side(split, circuit_id)
    held = side == "test"
    s = sample_accepted(motif_name, common, motifs, seed, workdir, max_tries)
    if s["spec"] is None:
        return {"accepted": False, "side": side, "tries": s["tries"], "reasons": s["reasons"]}
    spec, roles, m = s["spec"], s["roles"], s["measurement"]
    stored, rows = corrupt_wiring(spec, rates, np.random.default_rng([seed, 1000]))
    pokes = make_pokes(spec, roles, np.random.default_rng([seed, 2000]))
    trials = trial_table(pokes, noise_seed_count(split, circuit_id))
    ids = [n["id"] for n in spec["neurons"]]
    nml = workdir / f"{spec['circuit_id']}.trials.net.nml"
    write_network(spec, nml)
    runner = BatchRunner(nml, ids, DT, T_TRIAL)
    hashes = []
    v = run_trials(runner, spec, ids, roles, pokes, trials, seed, batch_size, hashes)
    bad = int(np.sum(~np.all(np.isfinite(v) & (v >= V_LOW) & (v <= V_HIGH), axis=(1, 2))))
    checks = {"base": {k: float(x) for k, x in rates.items()}}
    for k, (label, factor) in enumerate((("half", 0.5), ("double", 2.0)), start=1):
        checks[label] = {"rates": scaled_rates(rates, factor), "stored": corrupt_wiring(spec, scaled_rates(rates, factor), np.random.default_rng([seed, 1000 + k]))[0]}
    mask = withheld_mask(split, circuit_id, ids, trials, pokes)
    public_id = "h" + secrets.token_hex(8) if held else circuit_id
    private_nwb = workdir / f"{circuit_id}.private.nwb"
    write_run(private_nwb, spec, roles, m, stored, rows, pokes, trials, v, hashes, seed, "", circuit_id, f"{circuit_id}_a0")
    private_json = workdir / f"{circuit_id}.private.json"
    private_json.write_text(json.dumps({"circuit_id": circuit_id, "public_id": public_id, "side": side, "motif": motif_name, "datasheets": m["datasheets"], "gate_ratios": m["gate_ratios"], "cross_ratios": m["cross_ratios"], "wiring_checks": checks}, default=float))
    encrypt_file(private_nwb, out_dir / f"{public_id}.private.nwb.age", recipient)
    encrypt_file(private_json, out_dir / f"{public_id}.private.json.age", recipient)
    private_nwb.unlink()
    private_json.unlink()
    write_run(out_dir / f"{public_id}.nwb", spec, roles, m, stored, rows, pokes, trials, v, hashes, seed, "", public_id, f"{public_id}_a0", withheld=mask, hide_answers=held)
    out = {"accepted": True, "side": side, "public_id": public_id, "tries": s["tries"], "n_neurons": len(ids), "n_trials": len(trials), "n_bad_trials": bad, "n_withheld_trials": int(mask.any(axis=1).sum())}
    if held:
        for i in range(s["tries"]):
            shutil.rmtree(workdir / f"{circuit_id}_try{i}", ignore_errors=True)
        nml.unlink(missing_ok=True)
        return out
    else:
        checks_path = out_dir / f"{public_id}.wiring_checks.json"
        checks_path.write_text(json.dumps(checks, default=float))
        out.update({"circuit_id": circuit_id, "animal_id": f"{circuit_id}_a0", "reasons": s["reasons"], "datasheets": m["datasheets"], "gate_ratios": m["gate_ratios"], "cross_ratios": m["cross_ratios"], "wiring_checks": str(checks_path)})
        return out
