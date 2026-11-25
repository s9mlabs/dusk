import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNCHANGED = ("decoy_adaptation", "decoy_shunt", "plain", "release")

def pick_seeds(n) -> list:
    rows = json.loads((ROOT / "logs" / "pilot" / "m3" / "results.json").read_text())
    return [(r["motif"], int(r["seed"])) for r in rows if r["motif"] in UNCHANGED and r["accepted"]][:n]

def run_one(job) -> dict:
    motif, seed, out_dir = job
    from nexus.circuits.build import load_motifs
    from nexus.circuits.library import generate_animal
    common, motifs = load_motifs(ROOT / "configs" / "motifs")
    rates = json.loads((ROOT / "configs" / "corruption.json").read_text())["rates"]
    out = Path(out_dir); path = out / f"{motif}_{seed:05d}_a0.nwb"; work = out / "work" / f"{motif}_{seed:05d}"
    t0 = time.time(); r = generate_animal(motif, common, motifs, rates, seed, work, path)
    r["motif"] = motif; r["seed"] = seed; r["seconds"] = round(time.time() - t0, 2); r["bytes"] = path.stat().st_size if r["accepted"] else 0; r["pid"] = os.getpid()
    return r

def main():
    name = sys.argv[1]; n_procs = int(sys.argv[2]); n = int(sys.argv[3])
    os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
    out = ROOT / "outputs" / "cloud" / name; out.mkdir(parents=True, exist_ok=True)
    jobs = [(m, s, str(out)) for m, s in pick_seeds(n)]
    t0 = time.time()
    ctx = mp.get_context("spawn")
    rows = []
    with ctx.Pool(n_procs) as pool:
        for r in pool.imap_unordered(run_one, jobs):
            rows.append(r)
            print(f"{r['motif']:18s} {r['seed']} accepted={r['accepted']} {r['seconds']}s", flush=True)
    (out / "results.json").write_text(json.dumps(rows, indent=1, default=str))
    wall = time.time() - t0
    summary = {"name": name, "n_procs": n_procs, "n_circuits": len(rows), "wall_seconds": round(wall, 1), "circuits_per_hour": round(3600 * len(rows) / wall, 2), "mean_circuit_seconds": round(sum(r["seconds"] for r in rows) / max(len(rows), 1), 2), "total_bytes": sum(r["bytes"] for r in rows)}
    (out / "summary.json").write_text(json.dumps(summary, indent=1)); print(json.dumps(summary))

if __name__ == "__main__":
    main()
