"""
rollout_bench.py  -  rollout throughput sweep (sim + inference, learning off)
-----------------------------------------------------------------------------
    python bench/rollout_bench.py                           # envs 1 2 4 8 16, one worker each, 3 x 30 s
    python bench/rollout_bench.py --envs 128 --workers 31   # the training config
    python bench/rollout_bench.py --epsilon 1.0             # random actions only: no inference

Each run is `python -m ai.train --fresh` with learning off and epsilon held at --epsilon.
At the 0.15 training floor ~85% of actions go through the network, as they do for most of
a real training run; --fresh alone starts at 1.0, where select_action skips the network.
Throughput = env-steps after the first --warmup seconds, from the run's metrics.jsonl.
Repeats are interleaved (every N once, then again) so background load hits all N alike.
The report is appended to --out; run dirs go to <dir of --out>/rollout/<tag>/n<N>_r<r>.
"""

import os
import sys
import json
import signal
import socket
import argparse
import subprocess
from datetime import datetime, timezone
import torch

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # ai.train runs from the repo root
ncpu = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()

parser = argparse.ArgumentParser(description="Rollout throughput sweep around ai.train (learning off).")
parser.add_argument("--envs",    type=int, nargs="+", default=[1, 2, 4, 8, 16])
parser.add_argument("--workers", type=int, default=None, help="same worker count for every N, capped at N "
                                                              "(default: one worker per env, capped at cpus-1)")
parser.add_argument("--repeats", type=int, default=3)
parser.add_argument("--seconds", type=float, default=30, help="measured seconds per run")
parser.add_argument("--warmup",  type=float, default=5, help="seconds at the start of each run left out")
parser.add_argument("--epsilon", type=float, default=0.15, help="held for the whole run (0.15 = training floor)")
parser.add_argument("--device",  default="cuda" if torch.cuda.is_available() else "cpu")
parser.add_argument("--mode",    choices=["multi", "single"], default="multi")
parser.add_argument("--out",     default="results/rollout_runs.txt", help="report is appended here")
parser.add_argument("--tag",     default=None, help="run-dir name (default: <mode>_eps<E>_<UTC time>)")


def workers_for(n, args):
    """Worker processes for an n-env run: 1 in single mode, never more than n."""
    if args.mode == "single":
        return 1
    return min(n, args.workers or max(1, ncpu - 1))


def run_once(n, w, run_dir, args):
    """Run one ai.train rollout into run_dir; return its exit code, or "timeout"."""
    os.makedirs(run_dir, exist_ok=True)
    for name in ("metrics.jsonl", "summary.json"):      # never report an earlier run's numbers
        if os.path.exists(os.path.join(run_dir, name)):
            os.remove(os.path.join(run_dir, name))
    cmd = [sys.executable, "-m", "ai.train", "--mode", args.mode, "--workers", str(w), "--envs", str(n),
           "--fresh", "--warmup-eps", "1000000000", "--episodes", "1000000000", "--epsilon", str(args.epsilon),
           "--time-limit", str(args.warmup + args.seconds), "--log-interval", "1",
           "--save-every", "1000000000", "--run-dir", run_dir, "--device", args.device,
           "--weights-out", os.devnull]                  # learning is off, so the checkpoint is just the init
    with open(os.path.join(run_dir, "train.log"), "w") as log:
        p = subprocess.Popen(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:                                            # +300 s: spawning many workers on a slow FS
            return p.wait(timeout=args.warmup + args.seconds + 300)
        except subprocess.TimeoutExpired:
            return "timeout"
        finally:
            try:                                        # timeout, Ctrl-C or a stray worker: nothing
                os.killpg(p.pid, signal.SIGKILL)        # from this run may slow down the next one
            except ProcessLookupError:
                pass
            p.wait()


def measure(run_dir, warmup):
    """(env-steps, seconds) from the first metrics row at t >= warmup to the last timed row, or None.

    ai.train writes one final row after the loop stops, once the workers have been told to stop
    and joined; that stretch has no env-steps, so the window ends at the row before it.
    """
    try:
        with open(os.path.join(run_dir, "metrics.jsonl")) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return None
    rows = [r for r in rows[:-1] if r["t"] >= warmup]
    if len(rows) < 2 or rows[-1]["t"] <= rows[0]["t"]:
        return None
    return rows[-1]["env_steps"] - rows[0]["env_steps"], rows[-1]["t"] - rows[0]["t"]


def load_summary(run_dir):
    """The run's summary.json, or None if it never got written."""
    try:
        with open(os.path.join(run_dir, "summary.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def header(args, tag):
    """Machine + config lines for the top of the report."""
    def sh(*cmd):
        try:
            return subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    commit = sh("git", "rev-parse", "--short", "HEAD") or "unknown"
    if sh("git", "status", "--porcelain", "--untracked-files=no"):
        commit += "-dirty"
    cpu = "unknown"
    try:
        with open("/proc/cpuinfo") as f:
            cpu = next((l.split(":", 1)[1].strip() for l in f if l.startswith("model name")), cpu)
    except OSError:
        pass
    gpu = torch.cuda.get_device_name(args.device) if args.device.startswith("cuda") else "-"   # no CUDA context
    return [
        f"## rollout sweep {tag}  ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)",
        f"commit {commit} | host {socket.gethostname()} | {ncpu} cpus | cpu {cpu}",
        f"gpu {gpu} | torch {torch.__version__}",
        f"mode {args.mode} | device {args.device} | epsilon {args.epsilon} held, learning off, fresh weights | "
        f"{args.seconds:g} s measured after {args.warmup:g} s warmup | repeats {args.repeats}",
    ]


def pct(x):
    """0.123 -> '12%', None -> '-'."""
    return "-" if x is None else f"{x:.0%}"


def main():
    args = parser.parse_args()
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        parser.error(f"--device {args.device} but torch sees no GPU")

    envs     = list(dict.fromkeys(args.envs))          # a repeated N would reuse the same run dirs
    out      = os.path.abspath(args.out)
    tag      = args.tag or f"{args.mode}_eps{args.epsilon:g}_{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    run_root = os.path.join(os.path.dirname(out), "rollout", tag)
    head     = header(args, tag)
    sim      = "sim-wait" if args.mode == "multi" else "sim"
    print("\n".join(head), flush=True)

    runs = []
    for r in range(args.repeats):
        for n in envs:
            w       = workers_for(n, args)
            name    = f"n{n}_r{r}"
            run_dir = os.path.join(run_root, name)
            print(f"[{name}] envs {n}, workers {w} ...", end=" ", flush=True)
            rc  = run_once(n, w, run_dir, args)
            m   = measure(run_dir, args.warmup)
            s   = load_summary(run_dir)
            ok  = rc == 0 and m is not None and s is not None
            runs.append(dict(name=name, envs=n, workers=w, rc=rc, m=m, s=s, ok=ok))
            if ok:
                f = s["time_frac"]
                print(f"{m[0] / m[1]:.1f} env-steps/s ({m[0]} steps / {m[1]:.2f} s) | act {pct(f['act'])} "
                      f"{sim} {pct(f['sim'])} other {pct(f['other'])} | worker util {pct(s['worker_utilisation'])}",
                      flush=True)
            else:
                why = f"exit {rc}" if rc != 0 else "no summary.json" if s is None else "no metrics after --warmup"
                print(f"FAILED ({why}), last lines of {os.path.join(run_dir, 'train.log')}:")
                with open(os.path.join(run_dir, "train.log"), errors="replace") as f:
                    print("".join("    " + line for line in f.readlines()[-15:]), flush=True)

    lines = head + ["", "| envs | workers | env-steps/s mean | min-max | speedup vs first row |",
                    "|---:|---:|---:|---:|---:|"]
    base = None
    for n in envs:
        sps = [x["m"][0] / x["m"][1] for x in runs if x["envs"] == n and x["ok"]]
        if not sps:
            lines.append(f"| {n} | {workers_for(n, args)} | failed | - | - |")
            continue
        mean = sum(sps) / len(sps)
        if n == envs[0]:
            base = mean
        lines.append(f"| {n} | {workers_for(n, args)} | {mean:.0f} | {min(sps):.0f}-{max(sps):.0f} | "
                     + (f"{mean / base:.2f}x |" if base else "- |"))
    failed = [x["name"] for x in runs if not x["ok"]]
    if failed:
        lines.append(f"\nFAILED runs (left out of the means): {' '.join(failed)}")

    lines += ["", "Per run. Time split and worker utilisation cover the whole run (summary.json);",
              "env-steps/s covers the post-warmup window (metrics.jsonl).", "",
              f"| run | envs | workers | env-steps/s | env-steps | seconds | act | {sim} | other | learn "
              "| worker util | final eps | exit |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for x in runs:
        m, s = x["m"], x["s"] or {}
        f    = s.get("time_frac", {})
        cols = [x["name"], x["envs"], x["workers"],
                f"{m[0] / m[1]:.1f} | {m[0]} | {m[1]:.2f}" if m else "- | - | -",
                *(pct(f.get(p)) for p in ("act", "sim", "other", "learn")),
                pct(s.get("worker_utilisation")), s.get("final_epsilon", "-"), x["rc"]]
        lines.append("| " + " | ".join(map(str, cols)) + " |")
    lines.append(f"\nrun dirs: {run_root}")

    report = "\n".join(lines)
    print("\n" + report)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(report + "\n\n")
    print(f"[out] appended to {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
