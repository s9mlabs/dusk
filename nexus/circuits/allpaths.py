import copy
import math
from pathlib import Path
from nexus.circuits.probe import measure_circuit
from nexus.score.recovery import CONTINUOUS_FIELDS

GATED_PATHS = {"global_shutoff": (("in1", "O1"), ("in2", "O2"))}
GEOMETRIC = ("trigger_gain", "tau_on_over_tau_ref", "tau_off_over_tau_ref")

def combine_datasheets(sheets) -> dict:
    """Combine multiple datasheets into a single one."""
    out = dict(sheets[0])
    for f in CONTINUOUS_FIELDS:
        values = [float(s[f]) for s in sheets]
        if f in GEOMETRIC:
            if all(math.isfinite(x) and x > 0 for x in values):
                out[f] = math.exp(sum(math.log(x) for x in values) / len(values))
            else:
                out[f] = math.nan
        else:
            if all(math.isfinite(x) for x in values):
                out[f] = sum(values) / len(values)
            else:
                out[f] = math.nan
    return out

def measure_all_paths(spec, roles, switch_type, workdir) -> dict:
    """Measure all paths for a given switch type."""
    if switch_type not in GATED_PATHS:
        return measure_circuit(spec, roles, workdir)
    gate = roles["gates"][0]
    results = []
    for test_input, output in GATED_PATHS[switch_type]:
        r = copy.deepcopy(roles)
        r["gates"] = [dict(gate, test_input=test_input, output=output)]
        m = measure_circuit(spec, r, Path(workdir) / f"path_{test_input}")
        if not m["accepted"]:
            return dict(m, reason=f"path {test_input}>{output}: " + m["reason"])
        results.append(m)
    path_sheets = [m["datasheets"][0] for m in results]
    sheet = combine_datasheets(path_sheets)
    if any(not math.isfinite(sheet[f]) for f in CONTINUOUS_FIELDS):
        return dict(results[0], accepted=False, reason="combined datasheet has a missing value", path_datasheets=path_sheets)
    return dict(results[0], datasheets=[sheet], path_datasheets=path_sheets)
