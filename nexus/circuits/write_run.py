import json
from datetime import datetime, timezone
import jaxley
import numpy as np
from pynwb import H5DataIO, NWBHDF5IO, TimeSeries
from nexus.format.ground_truth import make_ground_truth
from nexus.format.inputs import write_inputs
from nexus.format.metadata import collect_run_metadata, make_run_metadata
from nexus.format.pokes import add_pokes
from nexus.format.runfile import new_run_file
from nexus.perturb.protocol import DT, KEEP, KEEP_EVERY, NOISE_MV, STATES_MV, T_TRIAL

START_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
SPECIES = "in silico"
WINDOW_S = (KEEP[1] - KEEP[0]) / 1000.0

def write_run(path, spec, roles, measurement, stored, corruption_rows, pokes, trials, voltages, hashes, circuit_seed, twin_id, base_circuit_id, animal_id, withheld=None, hide_answers=False) -> None:
    """Write one simulated animal and all its trials to an NWB file. withheld is an optional bool array (n_trials, n_neurons) of voltages to replace with NaN; hide_answers leaves out everything that reveals the planted answer."""
    ids = [n["id"] for n in spec["neurons"]]
    mask = None if withheld is None else np.asarray(withheld, dtype=bool)
    session_description = f"Simulated graded circuit {base_circuit_id}" if hide_answers else f"Simulated graded circuit {spec['circuit_id']}, motif {roles['motif']}"
    f = new_run_file(identifier=animal_id, session_description=session_description, session_start_time=START_TIME, subject_id=animal_id, species=SPECIES)
    f.add_lab_meta_data(make_run_metadata(collect_run_metadata(seed=-1 if hide_answers else int(circuit_seed), simulated=True, simulator="jaxley", simulator_version=jaxley.__version__, thread_count=1, use_gpu=True)))
    if not hide_answers:
        f.add_lab_meta_data(make_ground_truth(switch_type=roles["switch_type"], is_decoy=bool(roles["is_decoy"]), twin_id=twin_id, base_circuit_id=base_circuit_id, animal_id=animal_id, datasheets=measurement["datasheets"], wiring_corruption=corruption_rows))
    f.add_trial_column(name="poke_id", description="Poke given in this trial.")
    f.add_trial_column(name="poke_type", description="Poke type label.")
    f.add_trial_column(name="target_neuron", description="Neuron that received the poke.")
    f.add_trial_column(name="state_index", description="Brain-state level, 0 to 5.")
    f.add_trial_column(name="state_mV", description="Brain-state drive on neuron S, in mV.")
    f.add_trial_column(name="seed_index", description="Noise seed index.")
    f.add_trial_column(name="hold_neuron", description="Input held on for the whole trial in a paired poke; empty otherwise.")
    if mask is not None:
        f.add_trial_column(name="withheld", description="True if any voltage in this trial is withheld (NaN) and kept only in the encrypted file.")
    poke_rows = []
    for k, t in enumerate(trials):
        p = pokes[t["poke_index"]]
        row = {
            "start_time": k * WINDOW_S,
            "stop_time": (k + 1) * WINDOW_S,
            "poke_id": p["poke_id"],
            "poke_type": p["type"],
            "target_neuron": p["target"],
            "state_index": int(t["state_index"]),
            "state_mV": float(STATES_MV[t["state_index"]]),
            "seed_index": int(t["seed_index"]),
            "hold_neuron": p.get("hold", "")
        }
        if mask is not None:
            row["withheld"] = bool(mask[k].any())
        f.add_trial(**row)
        poke_rows.append({"start_time": k * WINDOW_S + (p["start_ms"] - KEEP[0]) / 1000.0, "stop_time": k * WINDOW_S + (p["stop_ms"] - KEEP[0]) / 1000.0, "target_neuron": p["target"], "amplitude": p["amplitude_mV"], "amplitude_unit": "mV of steady-state depolarisation", "modality": "current"})
    add_pokes(f, poke_rows)
    v = np.asarray(voltages, dtype=np.float32)
    if mask is not None:
        v = v.copy()
        v[mask] = np.nan
    data = v.transpose(0, 2, 1).reshape(-1, v.shape[1])
    f.add_acquisition(TimeSeries(name="membrane_potential", data=H5DataIO(data, compression="gzip"), unit="volts", conversion=0.001, rate=1000.0 / (KEEP_EVERY * DT), starting_time=0.0, description="Membrane potential in mV (conversion 0.001 to volts). Columns follow the neuron_ids input; trials are laid end to end."))
    inputs = {
        "neuron_ids": np.array(ids),
        "states_mV": np.array(STATES_MV),
        "trial_poke_index": np.array([t["poke_index"] for t in trials]),
        "trial_state_index": np.array([t["state_index"] for t in trials]),
        "trial_seed_index": np.array([t["seed_index"] for t in trials]),
        "noise_mV": np.array([NOISE_MV]),
        "dt_ms": np.array([DT]),
        "t_trial_ms": np.array([T_TRIAL]),
        "circuit_seed": np.array([int(circuit_seed)]),
        "currents_sha256": np.array(hashes)
    }
    if hide_answers:
        del inputs["circuit_seed"]
        del inputs["currents_sha256"]
    if mask is not None:
        inputs["withheld_mask"] = mask.astype(np.uint8)
    write_inputs(f, inputs)
    if not hide_answers:
        f.add_scratch(json.dumps(spec, sort_keys=True), name="circuit_spec_json", description="The simulated circuit, exactly.")
    if hide_answers:
        roles_json = json.dumps({"inputs": roles["inputs"], "outputs": roles["outputs"], "state": roles["state"]}, sort_keys=True)
    else:
        roles_json = json.dumps(roles, sort_keys=True)
    f.add_scratch(roles_json, name="roles_json", description="Which neurons are inputs, outputs, gates and the brain-state neuron.")
    f.add_scratch(json.dumps(stored, sort_keys=True), name="wiring_diagram_json", description="The corrupted wiring diagram a model is given.")
    f.add_scratch(json.dumps(pokes, sort_keys=True), name="pokes_json", description="The 50 pokes, by index.")
    with NWBHDF5IO(str(path), "w") as io:
        io.write(f)
