"""
train.py  -  single or multiprocessing training, with throughput instrumentation
--------------------------------------------------------------------------------
    python -m ai.train                                   # single, 1000 eps
    python -m ai.train --mode multi --workers 7
    python -m ai.train --episodes 5000 --envs 128 --mode multi

Benchmarking (fixed wall-clock budget, fresh weights, metrics to a run dir):
    python -m ai.train --mode multi --workers 16 --envs 128 \
        --fresh --time-limit 600 --run-dir runs/w16

Each run dir gets:
    metrics.jsonl   one row every --log-interval seconds (throughput, time split, reward, loss)
    summary.json    config + hardware + aggregate numbers for the whole run
    weights.pt      checkpoint (unless --weights-out says otherwise)
"""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import sys
import json
import time
import random
import socket
import platform
import itertools
import argparse
import multiprocessing as mp
import numpy as np
from tqdm import tqdm
import torch
import pygame

from ai.dqn_enemy import DQNagent
from entities.enemy_list import build_types, types
from ai.sim import Simulation


# config
learn_every   = 2
n_enemies     = 3
sim_dt        = 1 / 20.0
replays_dir   = "replays"

parser = argparse.ArgumentParser()
parser.add_argument("--episodes",     type=int, default=1000)
parser.add_argument("--envs",         type=int, default=128)
parser.add_argument("--workers",      type=int, default=max(1, mp.cpu_count() - 1))
parser.add_argument("--save-every",   type=int, default=100)
parser.add_argument("--mode",         choices=["single", "multi"], default="single")
parser.add_argument("--max-steps",    type=int, default=3000, help="sim steps per episode")
parser.add_argument("--time-limit",   type=float, default=0, help="stop after N seconds (0 = no limit)")
parser.add_argument("--fresh",        action="store_true", help="ignore existing weights, start from scratch")
parser.add_argument("--seed",         type=int, default=0)
parser.add_argument("--device",       default=None, help="cuda / cpu (default: cuda if available)")
parser.add_argument("--run-dir",      default=None, help="write metrics.jsonl / summary.json / weights here")
parser.add_argument("--weights-in",   default="ai/weights/weights.pt")
parser.add_argument("--weights-out",  default=None, help="default: <run-dir>/weights.pt or ai/weights/weights.pt")
parser.add_argument("--warmup-eps",   type=int, default=50, help="episodes before learning starts (huge = sim-only benchmark)")
parser.add_argument("--log-interval", type=float, default=30.0, help="seconds between metrics rows")
args = parser.parse_args()

n_episodes = args.episodes
n_envs     = args.envs
n_workers  = args.workers
save_every = args.save_every
mode       = args.mode
max_steps  = args.max_steps
warmup_eps = args.warmup_eps
run_dir    = args.run_dir
if run_dir:
    os.makedirs(run_dir, exist_ok=True)
weights_out = args.weights_out or (os.path.join(run_dir, "weights.pt") if run_dir else "ai/weights/weights.pt")


# ══════════════════════════════════════════════════════════════════════════════
# INSTRUMENTATION
# ══════════════════════════════════════════════════════════════════════════════
class Meter:
    """Accumulates wall-clock time per phase plus counters; emits periodic JSONL rows."""

    PHASES = ("act", "sim", "learn", "other")

    def __init__(self, path, interval, device):
        self.path      = path
        self.interval  = interval
        self.cuda      = device.type == "cuda"
        self.t0        = time.perf_counter()
        self.last_t    = self.t0
        self.tot       = {p: 0.0 for p in self.PHASES}
        self.win       = {p: 0.0 for p in self.PHASES}
        self.counts    = dict(env_steps=0, transitions=0, updates=0, episodes=0, actions=0)
        self.last_cnt  = dict(self.counts)
        self.rows      = 0
        self.f         = open(path, "w") if path else None

    def add(self, phase, dt):
        self.tot[phase] += dt
        self.win[phase] += dt

    def maybe_log(self, rewards_log, losses, epsilon, force=False):
        now = time.perf_counter()
        dt  = now - self.last_t
        if not force and dt < self.interval:
            return None
        d   = {k: self.counts[k] - self.last_cnt[k] for k in self.counts}
        row = {
            "t":               round(now - self.t0, 2),
            "episodes":        self.counts["episodes"],
            "env_steps":       self.counts["env_steps"],
            "env_steps_per_s": d["env_steps"] / dt if dt else 0,
            "actions_per_s":   d["actions"] / dt if dt else 0,
            "updates_per_s":   d["updates"] / dt if dt else 0,
            "episodes_per_s":  d["episodes"] / dt if dt else 0,
            "frac":            {p: self.win[p] / dt if dt else 0 for p in self.PHASES},
            "reward_mean":     float(np.mean(rewards_log[-50:])) if rewards_log else None,
            "loss_mean":       float(np.mean(losses)) if losses else None,
            "epsilon":         epsilon,
        }
        if self.cuda:
            row["gpu_mem_alloc_mb"] = torch.cuda.memory_allocated() / 2**20
            row["gpu_mem_peak_mb"]  = torch.cuda.max_memory_allocated() / 2**20
        if self.f:
            self.f.write(json.dumps(row) + "\n")
            self.f.flush()
        self.last_t   = now
        self.last_cnt = dict(self.counts)
        self.win      = {p: 0.0 for p in self.PHASES}
        self.rows    += 1
        return row

    def elapsed(self):
        return time.perf_counter() - self.t0


class timed:
    """Context manager: `with timed(meter, "sim"): ...`"""
    def __init__(self, meter, phase):
        self.m, self.p = meter, phase
    def __enter__(self):
        self.s = time.perf_counter()
    def __exit__(self, *a):
        self.m.add(self.p, time.perf_counter() - self.s)


def hardware_info(device):
    info = {
        "host":         socket.gethostname(),
        "platform":     platform.platform(),
        "python":       sys.version.split()[0],
        "torch":        torch.__version__,
        "cpu_count":    mp.cpu_count(),
        "affinity":     len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "torch_threads": torch.get_num_threads(),
        "device":       str(device),
        "slurm":        {k: v for k, v in os.environ.items() if k.startswith("SLURM_") and k in (
                            "SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_CPUS_PER_TASK",
                            "SLURM_JOB_NODELIST", "SLURM_JOB_GPUS", "SLURM_ARRAY_TASK_ID")},
    }
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    if device.type == "cuda":
        p = torch.cuda.get_device_properties(0)
        info["gpu"] = {"name": p.name, "mem_gb": round(p.total_memory / 2**30, 1),
                       "hip": getattr(torch.version, "hip", None), "cuda": torch.version.cuda}
    return info


# shared helpers
def discover_profiles():
    """Scan the replays directory and return a list of (name, data) tuples for every valid profile.json."""
    profiles = []
    if not os.path.isdir(replays_dir):
        return profiles
    for name in os.listdir(replays_dir):
        path = os.path.join(replays_dir, name, "profile.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                profiles.append((name, data))
            except (json.JSONDecodeError, IOError):
                pass
    return profiles


def make_env(profile_name=None):
    return Simulation(n_enemies=n_enemies, max_steps=max_steps, profile_name=profile_name)


def time_up(meter):
    return args.time_limit > 0 and meter.elapsed() >= args.time_limit


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-PROCESS TRAINING
# ══════════════════════════════════════════════════════════════════════════════
def train_single(enemy_agent, profiles, meter):
    print(f"[mode] single-process | {n_envs} envs | save every {save_every} eps")

    def pick_profile():
        return random.choice(profiles) if profiles else (None, None)

    env_profiles   = [pick_profile() for _ in range(n_envs)]
    envs           = [make_env(env_profiles[i][0]) for i in range(n_envs)]
    env_states     = [sim.reset() for sim in envs]
    env_rewards    = [[0.0] * len(sim.enemies()) for sim in envs]
    env_steps      = [0] * n_envs
    ep_rewards_log = []
    episode        = 0
    total_steps    = 0
    losses         = []
    last_save      = 0

    pbar = tqdm(total=n_episodes, desc="Training", unit="ep", ascii=True,
                bar_format="{l_bar}{bar:30}{r_bar}", mininterval=5)

    while episode < n_episodes and not time_up(meter):
        for env_i, sim in enumerate(envs):
            states = env_states[env_i]
            n      = len(sim.enemies())
            while len(env_rewards[env_i]) < n:
                env_rewards[env_i].append(0.0)
            while len(states) < n:
                states.append(np.zeros(30, dtype=np.float32))

            with timed(meter, "act"):
                actions = []
                for i in range(n):
                    if i < len(states) and sim.enemies()[i].health > 0:
                        action, lead_scale = enemy_agent.select_action(
                            states[i], enemy_id=sim.enemies()[i].enemy_id
                        )
                        actions.append((action, lead_scale))
                        meter.counts["actions"] += 1
                    else:
                        actions.append((0, 0.5))

            with timed(meter, "sim"):
                next_states, rewards, dones, info = sim.step(actions, dt=sim_dt)
            total_steps += 1
            meter.counts["env_steps"] += 1

            with timed(meter, "other"):
                for i in range(n):
                    if i < len(states) and i < len(next_states):
                        if i < len(sim.enemies()) and (sim.enemies()[i].health > 0 or dones[i]):
                            enemy_id = sim.enemies()[i].enemy_id
                            enemy_agent.push(enemy_id, states[i], actions[i][0], rewards[i], next_states[i], dones[i])
                            meter.counts["transitions"] += 1
                    if i < len(rewards) and i < len(env_rewards[env_i]):
                        env_rewards[env_i][i] += rewards[i]

                env_states[env_i] = next_states
                env_steps[env_i] += 1

                if not info["player_alive"] or env_steps[env_i] >= max_steps:
                    episode += 1
                    meter.counts["episodes"] += 1
                    env_steps[env_i] = 0
                    for e in sim.enemies():
                        enemy_agent.buffer.flush(e.enemy_id, enemy_agent.episode_id)
                    enemy_agent.reset_hidden()
                    enemy_agent.decay_epsilon()
                    ep_rewards_log.append(np.mean(env_rewards[env_i]) if env_rewards[env_i] else 0.0)
                    env_profiles[env_i] = pick_profile()
                    sim.profile_name    = env_profiles[env_i][0]
                    env_states[env_i]   = sim.reset()
                    env_rewards[env_i]  = [0.0] * len(sim.enemies())

        if total_steps % learn_every == 0 and episode > warmup_eps:
            with timed(meter, "learn"):
                loss = enemy_agent.learn()
            if loss is not None:
                losses.append(loss)
                meter.counts["updates"] += 1

        row = meter.maybe_log(ep_rewards_log, losses, enemy_agent.epsilon)
        if row:
            losses = []
            pbar.n = episode
            pbar.set_postfix({"eps": round(enemy_agent.epsilon, 3),
                              "r": round(row["reward_mean"] or 0, 2),
                              "steps/s": round(row["env_steps_per_s"])})
            pbar.refresh()

        if episode - last_save >= save_every:
            last_save = episode
            enemy_agent.save(weights_out)

    pbar.close()
    return ep_rewards_log, losses


# ══════════════════════════════════════════════════════════════════════════════
# MULTIPROCESSING WORKER
# ══════════════════════════════════════════════════════════════════════════════
def worker_fn(worker_id, env_ids, profiles, action_queue, experience_queue, max_steps, sim_dt, n_enemies, seed):
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    torch.set_num_threads(1)
    random.seed(seed + 1000 * (worker_id + 1))
    np.random.seed(seed + 1000 * (worker_id + 1))
    build_types()

    # Give every worker a disjoint enemy_id range. Without this, every process
    # counts from 0 and the learner's per-enemy LSTM hidden state and replay
    # sequences get mixed up between unrelated enemies in different workers.
    import entities.enemy as _em
    _em._id_counter = itertools.count(worker_id * 1_000_000_000)

    from ai.sim import Simulation

    def pick_profile():
        return random.choice(profiles) if profiles else (None, None)

    n       = len(env_ids)
    envs    = [Simulation(n_enemies=n_enemies, max_steps=max_steps, profile_name=pick_profile()[0]) for _ in range(n)]
    states  = [sim.reset() for sim in envs]
    rewards = [[0.0] * len(sim.enemies()) for sim in envs]
    steps   = [0] * n

    while True:
        msg = action_queue.get()
        if msg == "STOP":
            break

        t_start         = time.perf_counter()
        actions_per_env = msg
        experiences     = []
        episode_results = []

        for env_i, sim in enumerate(envs):
            env_actions = actions_per_env[env_i]
            cur_states  = states[env_i]

            actual_n = len(sim.enemies())
            while len(env_actions) < actual_n:
                env_actions.append((0, 0.5))

            next_states, step_rewards, dones, info = sim.step(env_actions, dt=sim_dt)

            for i in range(actual_n):
                if i < len(cur_states) and i < len(next_states) and i < len(env_actions):
                    if i < len(sim.enemies()) and (sim.enemies()[i].health > 0 or dones[i]):
                        enemy_id = sim.enemies()[i].enemy_id
                        experiences.append((
                            enemy_id, cur_states[i], env_actions[i][0],
                            step_rewards[i], next_states[i], dones[i],
                        ))
                if i < len(step_rewards):
                    while len(rewards[env_i]) <= i:
                        rewards[env_i].append(0.0)
                    rewards[env_i][i] += step_rewards[i]

            states[env_i] = next_states
            steps[env_i] += 1

            if not info["player_alive"] or steps[env_i] >= max_steps:
                mean_r = float(np.mean(rewards[env_i])) if rewards[env_i] else 0.0
                episode_results.append(mean_r)
                steps[env_i]     = 0
                sim.profile_name = pick_profile()[0]
                states[env_i]    = sim.reset()
                rewards[env_i]   = [0.0] * len(sim.enemies())

        experience_queue.put({
            "experiences":     experiences,
            "episode_results": episode_results,
            "states":          [states[i] for i in range(n)],
            "enemy_counts":    [len(sim.enemies()) for sim in envs],
            "enemy_ids":       [[e.enemy_id for e in sim.enemies()] for sim in envs],
            "alive":           [[e.health > 0 for e in sim.enemies()] for sim in envs],
            "busy_s":          time.perf_counter() - t_start,
            "n_env_steps":     n,
        })

    pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
# MULTIPROCESSING TRAINING
# ══════════════════════════════════════════════════════════════════════════════
def train_multi(enemy_agent, profiles, meter):
    print(f"[mode] multiprocessing | {n_workers} workers | {n_envs} total envs | save every {save_every} eps")

    envs_per_worker = n_envs // n_workers
    remainder       = n_envs % n_workers
    env_splits      = []
    start           = 0
    for w in range(n_workers):
        count = envs_per_worker + (1 if w < remainder else 0)
        env_splits.append(list(range(start, start + count)))
        start += count

    action_queues     = [mp.Queue() for _ in range(n_workers)]
    experience_queues = [mp.Queue() for _ in range(n_workers)]

    workers = []
    for w in range(n_workers):
        p = mp.Process(
            target=worker_fn,
            args=(w, env_splits[w], profiles, action_queues[w],
                  experience_queues[w], max_steps, sim_dt, n_enemies, args.seed),
            daemon=True,
        )
        p.start()
        workers.append(p)

    for w in range(n_workers):
        dummy = [[(0, 0.5)] * n_enemies for _ in range(len(env_splits[w]))]
        action_queues[w].put(dummy)

    worker_states    = [None] * n_workers
    worker_enemy_ids = [None] * n_workers
    worker_alive     = [None] * n_workers

    for w in range(n_workers):
        result = experience_queues[w].get()
        worker_states[w]    = result["states"]
        worker_enemy_ids[w] = result["enemy_ids"]
        worker_alive[w]     = result["alive"]

    # reset the clock so process spawn / warm-up isn't counted as throughput
    meter.t0 = meter.last_t = time.perf_counter()

    ep_rewards_log = []
    episode        = 0
    total_steps    = 0
    losses         = []
    last_save      = 0
    worker_busy    = 0.0   # summed busy time across workers (for utilisation)

    pbar = tqdm(total=n_episodes, desc="Training", unit="ep", ascii=True,
                bar_format="{l_bar}{bar:30}{r_bar}", mininterval=5)

    try:
        while episode < n_episodes and not time_up(meter):
            with timed(meter, "act"):
                for w in range(n_workers):
                    actions_per_env = []
                    for env_i in range(len(env_splits[w])):
                        env_states  = worker_states[w][env_i]
                        enemy_ids   = worker_enemy_ids[w][env_i]
                        alive       = worker_alive[w][env_i]
                        env_actions = []
                        for j, state in enumerate(env_states):
                            if j < len(alive) and alive[j]:
                                eid = enemy_ids[j]
                                env_actions.append(enemy_agent.select_action(state, enemy_id=eid))
                                meter.counts["actions"] += 1
                            else:
                                env_actions.append((0, 0.5))
                        while len(env_actions) < n_enemies:
                            env_actions.append((0, 0.5))
                        actions_per_env.append(env_actions)
                    action_queues[w].put(actions_per_env)

            for w in range(n_workers):
                with timed(meter, "sim"):          # time blocked waiting on workers
                    result = experience_queues[w].get()

                with timed(meter, "other"):
                    for exp in result["experiences"]:
                        enemy_agent.push(*exp)
                        total_steps += 1
                    meter.counts["transitions"] += len(result["experiences"])
                    meter.counts["env_steps"]   += result["n_env_steps"]
                    worker_busy += result["busy_s"]

                    for mean_r in result["episode_results"]:
                        episode += 1
                        meter.counts["episodes"] += 1
                        enemy_agent.reset_hidden()
                        enemy_agent.decay_epsilon()
                        ep_rewards_log.append(mean_r)

                    worker_states[w]    = result["states"]
                    worker_enemy_ids[w] = result["enemy_ids"]
                    worker_alive[w]     = result["alive"]

            if total_steps % learn_every == 0 and episode > warmup_eps:
                with timed(meter, "learn"):
                    loss = enemy_agent.learn()
                if loss is not None:
                    losses.append(loss)
                    meter.counts["updates"] += 1

            row = meter.maybe_log(ep_rewards_log, losses, enemy_agent.epsilon)
            if row:
                losses = []
                pbar.n = episode
                pbar.set_postfix({"eps": round(enemy_agent.epsilon, 3),
                                  "r": round(row["reward_mean"] or 0, 2),
                                  "steps/s": round(row["env_steps_per_s"])})
                pbar.refresh()

            if episode - last_save >= save_every:
                last_save = episode
                enemy_agent.save(weights_out)

    finally:
        for q in action_queues:
            q.put("STOP")
        for p in workers:
            p.join(timeout=5)

    pbar.close()
    meter.worker_busy = worker_busy
    return ep_rewards_log, losses


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def train():
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    pygame.init()
    pygame.mixer.quit()

    build_types()
    print(f"[types] {len(types)} enemy types loaded")

    enemy_agent = DQNagent(device=args.device)
    hw = hardware_info(enemy_agent.device)
    print(f"[device] {enemy_agent.device} — {hw.get('gpu', {}).get('name', hw.get('cpu_model', 'CPU'))}")

    if not args.fresh and os.path.exists(args.weights_in):
        enemy_agent.load(args.weights_in)
        print(f"[weights] loaded {args.weights_in}")
    else:
        print("[weights] starting from scratch")

    profiles = discover_profiles()
    print(f"[profiles] {len(profiles)} loaded: {[p[0] for p in profiles]}")
    print(f"[config] mode={mode} envs={n_envs} workers={n_workers if mode == 'multi' else 1} "
          f"episodes={n_episodes} time_limit={args.time_limit} max_steps={max_steps}")

    meter = Meter(os.path.join(run_dir, "metrics.jsonl") if run_dir else None,
                  args.log_interval, enemy_agent.device)
    meter.worker_busy = None

    if mode == "multi":
        rewards_log, _ = train_multi(enemy_agent, profiles, meter)
    else:
        rewards_log, _ = train_single(enemy_agent, profiles, meter)

    meter.maybe_log(rewards_log, [], enemy_agent.epsilon, force=True)
    wall = meter.elapsed()
    enemy_agent.save(weights_out)
    print(f"[save] final weights -> {weights_out}")

    c = meter.counts
    summary = {
        "config": {k: v for k, v in vars(args).items()},
        "hardware": hw,
        "wall_s": wall,
        "totals": c,
        "env_steps_per_s":  c["env_steps"] / wall,
        "actions_per_s":    c["actions"] / wall,
        "updates_per_s":    c["updates"] / wall,
        "episodes_per_s":   c["episodes"] / wall,
        "time_frac":        {p: meter.tot[p] / wall for p in Meter.PHASES},
        "worker_utilisation": (meter.worker_busy / (wall * n_workers)) if meter.worker_busy else None,
        "reward_first50":   float(np.mean(rewards_log[:50])) if rewards_log else None,
        "reward_last50":    float(np.mean(rewards_log[-50:])) if rewards_log else None,
        "final_epsilon":    enemy_agent.epsilon,
    }
    if enemy_agent.device.type == "cuda":
        summary["gpu_mem_peak_mb"] = torch.cuda.max_memory_allocated() / 2**20
    print(json.dumps({k: summary[k] for k in ("wall_s", "env_steps_per_s", "actions_per_s",
                                              "updates_per_s", "time_frac", "worker_utilisation")}, indent=2))
    if run_dir:
        with open(os.path.join(run_dir, "summary.json"), "w") as f:
            json.dump(summary, f, indent=2)
        print(f"[summary] {os.path.join(run_dir, 'summary.json')}")
    pygame.quit()


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    train()
