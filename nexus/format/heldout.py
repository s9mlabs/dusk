import zlib
import numpy as np
from nexus.format.splits import _split_units

RECIPIENT = "age1vte8j93exfsjdcarne4tq2ar9ssfw9zqe3sp4sj8feew7v59r4cq8dtpvw"
SCHEMA_VERSION = "0.1.0"
NORMAL_SEEDS = 3
HELD_OUT_SEEDS = 10

def make_library_split(circuit_ids, poke_types, states, seed, test_fraction=0.2, val_fraction=0.2) -> dict:
    """Split circuits, poke types, and states into train, validation, and test sets."""
    rng = np.random.default_rng(seed)
    circuits = _split_units(list(circuit_ids), rng, test_fraction, val_fraction)
    pokes = _split_units(list(poke_types), rng, test_fraction, val_fraction)
    st = _split_units([int(s) for s in states], rng, test_fraction, val_fraction)
    return {"schema_version": SCHEMA_VERSION, "seed": int(seed), "test_fraction": float(test_fraction), "val_fraction": float(val_fraction), "circuits": circuits, "poke_types": pokes, "states": st, "neuron_rule": "per circuit: _split_units(neuron_ids, default_rng([seed, crc32(circuit_id)]))"}

def _side_of(parts, unit) -> str:
    """Determine which split a unit belongs to."""
    for key in ("train", "val", "test"):
        if unit in parts[key]:
            return key
    raise ValueError(f"Unit {unit} is not in the split")

def circuit_side(split, circuit_id) -> str:
    """Determine which split a circuit belongs to."""
    return _side_of(split["circuits"], circuit_id)

def noise_seed_count(split, circuit_id) -> int:
    """Determine the number of noise seeds for a circuit."""
    return HELD_OUT_SEEDS if circuit_side(split, circuit_id) == "test" else NORMAL_SEEDS

def neuron_sides(split, circuit_id, neuron_ids) -> dict:
    """Determine which split each neuron belongs to."""
    if circuit_side(split, circuit_id) == "test":
        return {n: "test" for n in neuron_ids}
    rng = np.random.default_rng([int(split["seed"]), zlib.crc32(circuit_id.encode())])
    parts = _split_units(list(neuron_ids), rng, split["test_fraction"], split["val_fraction"])
    return {n: _side_of(parts, n) for n in neuron_ids}

def withheld_mask(split, circuit_id, neuron_ids, trials, pokes) -> np.ndarray:
    """Create a mask indicating which trials and neurons are withheld."""
    neuron_sides_dict = neuron_sides(split, circuit_id, neuron_ids)
    held_circuit = circuit_side(split, circuit_id) == "test"
    mask = np.zeros((len(trials), len(neuron_ids)), dtype=bool)
    for i, trial in enumerate(trials):
        poke_type = pokes[trial["poke_index"]]["type"]
        state_index = int(trial["state_index"])
        for j in range(len(neuron_ids)):
            if (held_circuit or
                _side_of(split["poke_types"], poke_type) == "test" or
                _side_of(split["states"], state_index) == "test" or
                neuron_sides_dict[neuron_ids[j]] == "test"):
                mask[i, j] = True
    return mask
