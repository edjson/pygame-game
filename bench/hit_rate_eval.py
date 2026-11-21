"""
hit_rate_eval.py  -  hit rate of trained vs scripted enemies against the scripted player bot
--------------------------------------------------------------------------------------------
    python bench/hit_rate_eval.py                       # 200 paired episodes per policy
    python bench/hit_rate_eval.py --episodes 10         # quick check
    python bench/hit_rate_eval.py --weights runs/w16/weights.pt --workers 15

Both policies play ai.sim.Simulation as ai/train.py sets it up (3 enemies, at most 3000 steps,
dt 1/20) against the same scripted player, SimPlayer (entities/ai_player.py AIPlayer):
    trained   DQNagent from --weights, greedy unless --epsilon; each enemy's LSTM state is
              carried across steps and cleared at the start of every episode
    scripted  Enemy.rule_based_update in the sim's action space: the move closest to the
              direction of the player, every shot aimed at the player's current position
Episode i of both policies is seeded with --seed + i (python random + numpy) right before
reset, so each pair starts from the same enemy types, spawn points and player position.
Hit rate = enemy shots that hit the player / enemy shots fired, pooled over the episodes.
The report (header, tables, counting method) is printed and appended to --out.
"""

import os
os.environ["SDL_VIDEODRIVER"]            = "dummy"
os.environ["SDL_AUDIODRIVER"]            = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"      # one banner per worker otherwise

import sys
import json
import math
import time
import random
import socket
import hashlib
import argparse
import subprocess
import multiprocessing as mp
from datetime import datetime, timezone

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root, for the ai.* / entities.* imports
sys.path.insert(0, root)
ncpu = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()

import numpy as np
import torch

from ai.sim import Simulation, SimPlayer
from ai.dqn_enemy import DQNagent, movement
from entities.enemy_list import build_types

# sim config, as in ai/train.py
n_enemies = 3
max_steps = 3000
sim_dt    = 1 / 20.0
policies  = ("trained", "scripted")

parser = argparse.ArgumentParser(description="Hit rate of trained vs scripted enemies against the scripted player bot.")
parser.add_argument("--episodes",  type=int, default=200, help="episodes per policy")
parser.add_argument("--seed",      type=int, default=0, help="episode i of both policies is seeded with seed + i")
parser.add_argument("--weights",   default="ai/weights/weights.pt", help="checkpoint for the trained policy")
parser.add_argument("--epsilon",   type=float, default=0.0, help="exploration for the trained policy (0 = greedy). Acts through select_action, "
                         "as the game does: the LSTM is not run on random steps (training's batched "
                         "path still advances it)")
parser.add_argument("--profile",   default=None, help="player profile under replays/ (default: none)")
parser.add_argument("--workers",   type=int, default=max(1, min(6, ncpu - 1)), help="episode processes")
parser.add_argument("--device",    default="cpu", help="device for the trained policy")
parser.add_argument("--bootstrap", type=int, default=10000, help="resamples for the 95%% CIs")
parser.add_argument("--out",       default="results/hit_rate_runs.txt", help="report is appended here")


# ══════════════════════════════════════════════════════════════════════════════
# EPISODES (worker processes)
# ══════════════════════════════════════════════════════════════════════════════
class ShotLog(list):
    """Stands in for sim.enemy_proj. Simulation.step appends every enemy shot and removes one only
    once it has left the screen or hit the player, so a remove() while still on screen is a hit."""

    def __init__(self):
        super().__init__()
        self.shots      = 0
        self.hits       = 0
        self.misses     = 0
        self.hit_damage = 0.0

    def append(self, proj):
        self.shots += 1
        super().append(proj)

    def remove(self, proj):
        if proj.out_of_bounds():
            self.misses += 1
        else:
            self.hits       += 1
            self.hit_damage += proj.damage
        super().remove(proj)


class DamageMeter(SimPlayer):
    """SimPlayer whose health setter adds up every drop (shot hits and contact damage); heals are not netted out."""

    @property
    def health(self):
        return self.__dict__["health"]

    @health.setter
    def health(self, value):
        self.damage_taken      += max(0.0, self.__dict__["health"] - value)
        self.__dict__["health"] = value


_agent = None   # this worker's trained policy, see init_worker


def init_worker(weights, device, epsilon):
    """Pool initializer: one torch thread per process, the enemy types, the trained agent."""
    global _agent
    torch.set_num_threads(1)
    build_types()
    _agent         = DQNagent(device=device)
    _agent.load(weights)
    _agent.epsilon = epsilon
    _agent.online.eval()


def scripted_action(enemy, player):
    """Enemy.rule_based_update as an (action, lead) pair: the move closest to the player's direction, no lead."""
    dx, dy = player.pos.x - enemy.pos.x, player.pos.y - enemy.pos.y
    if dx == 0 and dy == 0:
        return 0, 0.0
    return max(range(1, len(movement)),
               key=lambda a: (movement[a][0] * dx + movement[a][1] * dy) / math.hypot(*movement[a])), 0.0


def run_episode(task):
    """Play one seeded episode with one policy; return its shot, damage and length counters."""
    policy, seed, profile = task
    random.seed(seed)
    np.random.seed(seed)
    sim    = Simulation(n_enemies=n_enemies, max_steps=max_steps, profile_name=profile)
    states = sim.reset()
    log    = ShotLog()
    sim.enemy_proj          = log                  # reset() made a fresh list; nothing has been fired yet
    sim.player.damage_taken = 0.0
    sim.player.__class__    = DamageMeter
    _agent.reset_hidden()
    bad_steps = 0
    while True:
        actions = []
        for i, e in enumerate(sim.enemies()):
            if e.health <= 0:
                actions.append((0, 0.5))           # step() skips dead enemies
            elif policy == "trained":
                actions.append(_agent.select_action(states[i], e.enemy_id))
            else:
                actions.append(scripted_action(e, sim.player))
        hits_before        = log.hits
        states, _, _, info = sim.step(actions, dt=sim_dt)
        hits               = log.hits - hits_before
        landed             = sum(e.hit_landed for e in sim.enemies())   # enemies with >= 1 hit this step
        if hits < landed or (hits > 0) != (landed > 0):
            bad_steps += 1
        if not info["player_alive"] or info["step"] >= max_steps:
            break
    return dict(policy=policy, seed=seed, shots=log.shots, hits=log.hits, misses=log.misses,
                in_flight=len(log), shot_damage=log.hit_damage, damage=sim.player.damage_taken,
                steps=info["step"], died=not info["player_alive"], stage=info["stage"], bad_steps=bad_steps)


# ══════════════════════════════════════════════════════════════════════════════
# REPORT (main process)
# ══════════════════════════════════════════════════════════════════════════════
def sha256(path):
    """First 12 hex digits of the file's sha256."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def header(args):
    """Date, machine, commit, checkpoint and config lines for the top of the report."""
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
    ck = torch.load(args.weights, map_location="cpu", weights_only=True)
    return [
        f"## hit-rate eval  ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)",
        f"commit {commit} | host {socket.gethostname()} | {ncpu} cpus | cpu {cpu} | torch {torch.__version__}",
        f"weights {args.weights} sha256 {sha256(args.weights)} | checkpoint: "
        f"{ck.get('steps')} transitions, epsilon {ck.get('epsilon')}",
        f"seeds {args.seed}..{args.seed + args.episodes - 1}, one per episode, the same for both policies "
        f"(python random + numpy, reseeded right before reset)",
        f"sim: {n_enemies} enemies, max {max_steps} steps, dt {sim_dt:g}, player profile {args.profile} | "
        f"trained: epsilon {args.epsilon:g} on {args.device} | scripted: closest move to the player, lead 0",
        f"args {json.dumps(vars(args))}",
    ]


def pct(x):
    """0.1234 -> '12.3%'."""
    return f"{100 * x:.1f}%"


def report(args, rows, wall):
    """Tables, paired difference and counting notes from the episode rows."""
    n    = args.episodes
    keys = [k for k in rows[0] if k not in ("policy", "seed")]
    by   = {p: sorted((r for r in rows if r["policy"] == p), key=lambda r: r["seed"]) for p in policies}
    col  = {p: {k: np.array([r[k] for r in by[p]], dtype=float) for k in keys} for p in policies}
    rng  = np.random.default_rng(args.seed)
    idx  = rng.integers(0, n, size=(args.bootstrap, n))       # resampled seeds, the same for both policies
    rate = {p: col[p]["hits"].sum() / max(col[p]["shots"].sum(), 1) for p in policies}
    boot = {p: col[p]["hits"][idx].sum(1) / np.maximum(col[p]["shots"][idx].sum(1), 1) for p in policies}
    lo, hi = {}, {}
    for p in policies:
        lo[p], hi[p] = np.percentile(boot[p], [2.5, 97.5])
    d_lo, d_hi = np.percentile(boot["trained"] - boot["scripted"], [2.5, 97.5])
    with np.errstate(divide="ignore", invalid="ignore"):
        r_lo, r_hi = np.percentile(boot["trained"] / boot["scripted"], [2.5, 97.5])

    lines = ["", "| policy | shots fired | hits | left screen | in flight at end | hit rate | 95% CI |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for p in policies:
        c = col[p]
        lines.append(f"| {p} | {c['shots'].sum():.0f} | {c['hits'].sum():.0f} | {c['misses'].sum():.0f} | "
                     f"{c['in_flight'].sum():.0f} | {pct(rate[p])} | {pct(lo[p])} - {pct(hi[p])} |")
    lines += ["", "| policy | episodes | player deaths | mean length (steps, sim time) | mean stage | shots / ep "
                  "| shot damage / ep | total damage / ep |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for p in policies:
        c = col[p]
        lines.append(f"| {p} | {n} | {c['died'].sum():.0f} ({pct(c['died'].mean())}) | {c['steps'].mean():.0f} "
                     f"({c['steps'].mean() * sim_dt:.0f} s) | {c['stage'].mean():.1f} | {c['shots'].mean():.1f} | "
                     f"{c['shot_damage'].mean():.1f} | {c['damage'].mean():.1f} |")
    lines += ["", f"trained - scripted hit rate: {100 * (rate['trained'] - rate['scripted']):+.1f} pp "
                  f"(95% CI {100 * d_lo:+.1f} to {100 * d_hi:+.1f} pp), trained / scripted: "
                  f"{rate['trained'] / max(rate['scripted'], 1e-12):.2f}x (95% CI {r_lo:.2f} - {r_hi:.2f}x)"]

    bad_steps = int(sum(col[p]["bad_steps"].sum() for p in policies))
    bad_eps   = int(sum((col[p]["shots"] != col[p]["hits"] + col[p]["misses"] + col[p]["in_flight"]).sum()
                        for p in policies))
    lines += ["",
              "Hit rate = hits / shots fired, pooled over all episodes of a policy.",
              "Counting (ai/sim.py unchanged): after every reset the eval swaps sim.enemy_proj for a list subclass.",
              "Simulation.step appends each enemy shot to it (= fired) and removes a projectile only once it has left",
              "the screen or hit the player, so a remove() of a projectile still on screen is a hit, one off screen a",
              "miss. Shots still in flight when an episode ends count as fired, not as hits.",
              f"Cross-checks: fired = hits + left screen + in flight in every episode ({bad_eps} episodes off); every",
              f"step, hits >= enemies with hit_landed set, and both are zero together ({bad_steps} steps off).",
              "hit_landed alone would undercount: it is one flag per enemy per step.",
              "Damage: the player object's class is swapped for a SimPlayer subclass whose health setter adds up",
              "every drop, i.e. shot hits plus contact damage; heals (stage-clear regen, Heal buff) are not netted",
              "out. Shot damage = damage of the projectiles counted as hits.",
              f"CIs: percentile bootstrap over episodes ({args.bootstrap} resamples), not over shots, since shots in",
              "one episode are correlated; the difference and ratio resample the same seeds for both policies.",
              f"wall time {wall:.0f} s with {min(args.workers, 2 * n)} worker processes"]
    return lines, bad_steps + bad_eps


def main():
    args = parser.parse_args()
    if args.episodes < 1:
        parser.error("--episodes must be at least 1")
    if args.profile and not os.path.exists(os.path.join(root, "replays", args.profile, "profile.json")):
        parser.error(f"no replays/{args.profile}/profile.json under {root}")
    if not os.path.exists(args.weights):
        parser.error(f"no checkpoint at {args.weights}")

    out  = os.path.abspath(args.out)
    head = header(args)
    print("\n".join(head), flush=True)

    tasks = [(p, args.seed + i, args.profile) for i in range(args.episodes) for p in policies]
    rows  = []
    every = max(1, len(tasks) // 10)
    t0    = time.perf_counter()
    with mp.Pool(min(args.workers, len(tasks)), initializer=init_worker,
                 initargs=(args.weights, args.device, args.epsilon)) as pool:
        for k, row in enumerate(pool.imap_unordered(run_episode, tasks), 1):
            rows.append(row)
            if k % every == 0 or k == len(tasks):
                print(f"[{k}/{len(tasks)}] episodes done, {time.perf_counter() - t0:.0f} s", flush=True)
    wall = time.perf_counter() - t0

    lines, off = report(args, rows, wall)
    text       = "\n".join(head + lines)
    print("\n".join(lines))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(text + "\n\n")
    print(f"[out] appended to {out}")
    sys.exit(1 if off else 0)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
