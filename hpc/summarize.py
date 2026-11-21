"""Aggregate summary.json files from a sweep into a markdown table (+ optional PNG plot).
    python hpc/summarize.py results/gpu_12345 [results/cpu_12346 ...]
"""
import sys, os, json, glob, re

rows = []
for root in sys.argv[1:]:
    for p in sorted(glob.glob(os.path.join(root, "*_w*", "summary.json"))):
        s = json.load(open(p))
        m = re.search(r"(\w+)_w(\d+)$", os.path.dirname(p))
        rows.append(dict(sweep=os.path.basename(root), phase=m.group(1), workers=int(m.group(2)),
                         dev=s["hardware"]["device"], sps=s["env_steps_per_s"], ups=s["updates_per_s"],
                         util=s.get("worker_utilisation") or 0, frac=s["time_frac"],
                         gpu=s["hardware"].get("gpu", {}).get("name", s["hardware"].get("cpu_model", ""))))

for (sweep, phase) in sorted({(r["sweep"], r["phase"]) for r in rows}):
    rs = sorted([r for r in rows if r["sweep"] == sweep and r["phase"] == phase], key=lambda r: r["workers"])
    base = rs[0]["sps"] / rs[0]["workers"]
    print(f"\n### {sweep} / {phase}  ({rs[0]['dev']}, {rs[0]['gpu']})\n")
    print("| workers | env-steps/s | speedup | efficiency | updates/s | worker util | act | wait-sim | learn |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rs:
        sp = r["sps"] / rs[0]["sps"]
        eff = r["sps"] / (base * r["workers"])
        f = r["frac"]
        print(f"| {r['workers']} | {r['sps']:.0f} | {sp:.2f}x | {eff:.0%} | {r['ups']:.1f} | {r['util']:.0%} "
              f"| {f['act']:.0%} | {f['sim']:.0%} | {f['learn']:.0%} |")

try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4))
    for (sweep, phase) in sorted({(r["sweep"], r["phase"]) for r in rows}):
        rs = sorted([r for r in rows if r["sweep"] == sweep and r["phase"] == phase], key=lambda r: r["workers"])
        ax.plot([r["workers"] for r in rs], [r["sps"] for r in rs], marker="o", label=f"{sweep} {phase}")
    ax.set_xscale("log", base=2); ax.set_yscale("log")
    ax.set_xlabel("worker processes"); ax.set_ylabel("env steps / s"); ax.legend(fontsize=7); ax.grid(alpha=.3)
    out = os.path.join(sys.argv[1], "scaling.png"); fig.tight_layout(); fig.savefig(out, dpi=150)
    print(f"\n[plot] {out}")
except ImportError:
    pass
