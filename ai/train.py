"""
train.py  -  single or multiprocessing training
-------------------------------------------------
Switch modes via command line:

    python -m ai.train                          # single, 1000 eps
    python -m ai.train --mode single            # explicit single
    python -m ai.train --mode multi             # multiprocessing
    python -m ai.train --mode multi --workers 7
    python -m ai.train --episodes 5000 --envs 128 --mode multi
    python -m ai.train --episodes 500 --save-every 50
"""

import os
import sys
import json
import time
import random
import numpy as np
from tqdm import tqdm
import torch
import argparse
import multiprocessing as mp
from ai.dqn_enemy import DQNagent
from entities.enemy_list import build_types, types
from ai.sim import Simulation
import pygame
pygame.init()
pygame.mixer.quit()
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


# config
n_episodes    = 1000
n_envs        = 128
n_workers     = max(1, mp.cpu_count() - 1)
mode          = "single"
save_every    = 100
print_every   = 10
warmup_eps    = 50
learn_every   = 2
max_steps     = 3000
n_enemies     = 3
sim_dt        = 1 / 20.0
enemy_weights = "ai/weights/weights.pt"
replays_dir   = "replays"

# CLI args
parser = argparse.ArgumentParser()
parser.add_argument("--episodes",   type=int, default=1000)
parser.add_argument("--envs",       type=int, default=128)
parser.add_argument("--workers",    type=int, default=n_workers)
parser.add_argument("--save-every", type=int, default=100)
parser.add_argument("--mode",       choices=["single", "multi"], default="single")
args        = parser.parse_args()
n_episodes  = args.episodes
n_envs      = args.envs
n_workers   = args.workers
save_every  = args.save_every
mode        = args.mode

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
    """Instantiate and return a Simulation configured with the global n_enemies and max_steps."""
    return Simulation(n_enemies=n_enemies, max_steps=max_steps, profile_name=profile_name)


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-PROCESS TRAINING
# ══════════════════════════════════════════════════════════════════════════════
def train_single(enemy_agent, profiles):
    """Run the full training loop in-process across n_envs parallel simulations."""
    print(f"[mode] single-process | {n_envs} envs | save every {save_every} eps")

    def pick_profile():
        """Return a random (name, data) profile tuple, or (None, None) if none exist."""
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
    last_print     = 0
    t0             = time.time()

    pbar = tqdm(total=n_episodes, desc="Training", unit="ep", ascii=True,
                bar_format="{l_bar}{bar:30}{r_bar}")

    while episode < n_episodes:
        for env_i, sim in enumerate(envs):
            states = env_states[env_i]
            n      = len(sim.enemies())
            while len(env_rewards[env_i]) < n:
                env_rewards[env_i].append(0.0)
            while len(states) < n:
                states.append(np.zeros(30, dtype=np.float32))

            actions = []
            for i in range(n):
                if i < len(states) and sim.enemies()[i].health > 0:
                    action, lead_scale = enemy_agent.select_action(
                        states[i], enemy_id=sim.enemies()[i].enemy_id
                    )
                    actions.append((action, lead_scale))
                else:
                    actions.append((0, 0.5))

            next_states, rewards, dones, info = sim.step(actions, dt=sim_dt)
            total_steps += 1

            for i in range(n):
                if i < len(states) and i < len(next_states):
                    if i < len(sim.enemies()) and (sim.enemies()[i].health > 0 or dones[i]):
                        enemy_agent.push(states[i], actions[i][0], rewards[i], next_states[i], dones[i])
                if i < len(rewards) and i < len(env_rewards[env_i]):
                    env_rewards[env_i][i] += rewards[i]

            env_states[env_i] = next_states
            env_steps[env_i] += 1

            if not info["player_alive"] or env_steps[env_i] >= max_steps:
                episode += 1
                env_steps[env_i] = 0
                enemy_agent.decay_epsilon()
                mean_r = np.mean(env_rewards[env_i]) if env_rewards[env_i] else 0.0
                ep_rewards_log.append(mean_r)
                env_profiles[env_i] = pick_profile()
                sim.profile_name    = env_profiles[env_i][0]
                env_states[env_i]   = sim.reset()
                env_rewards[env_i]  = [0.0] * len(sim.enemies())

        if total_steps % learn_every == 0 and episode > warmup_eps:
            loss = enemy_agent.learn()
            if loss is not None:
                losses.append(loss)

        if episode - last_print >= print_every and episode > 0:
            last_print  = episode
            recent      = np.mean(ep_rewards_log[-print_every:]) if ep_rewards_log else 0.0
            avg_loss    = np.mean(losses[-100:]) if losses else 0.0
            elapsed     = time.time() - t0
            eps_per_sec = episode / elapsed if elapsed > 0 else 0
            pbar.n = episode
            pbar.set_postfix({
                "eps":  round(enemy_agent.epsilon, 3),
                "r":    round(recent, 2),
                "loss": round(avg_loss, 4),
                "ep/s": round(eps_per_sec, 1),
            })
            pbar.refresh()
            losses = []

        if episode % save_every == 0 and episode > 0:
            enemy_agent.save(enemy_weights)
            print(f"[save] weights saved at episode {episode}")

    pbar.close()


# ══════════════════════════════════════════════════════════════════════════════
# MULTIPROCESSING WORKER
# ══════════════════════════════════════════════════════════════════════════════
def worker_fn(worker_id, env_ids, profiles, action_queue, experience_queue, max_steps, sim_dt, n_enemies):
    build_types()

    from ai.sim import Simulation

    def pick_profile():
        """Return a random profile tuple, or (None, None) if the list is empty."""
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
                        experiences.append((
                            cur_states[i], env_actions[i][0],
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
        })

    pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
# MULTIPROCESSING TRAINING
# ══════════════════════════════════════════════════════════════════════════════
def train_multi(enemy_agent, profiles):
    """Distribute environments across n_workers subprocesses, collect experiences, and train the agent."""
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
                  experience_queues[w], max_steps, sim_dt, n_enemies),
            daemon=True,
        )
        p.start()
        workers.append(p)

    for w in range(n_workers):
        dummy = [[(0, 0.5)] * n_enemies for _ in range(len(env_splits[w]))]
        action_queues[w].put(dummy)

    worker_states    = [None] * n_workers
    worker_enemy_ids = [None] * n_workers
    worker_counts    = [None] * n_workers

    for w in range(n_workers):
        result = experience_queues[w].get()
        worker_states[w]    = result["states"]
        worker_enemy_ids[w] = result["enemy_ids"]
        worker_counts[w]    = result["enemy_counts"]

    ep_rewards_log = []
    episode        = 0
    total_steps    = 0
    losses         = []
    last_print     = 0
    t0             = time.time()

    pbar = tqdm(total=n_episodes, desc="Training", unit="ep", ascii=True,
                bar_format="{l_bar}{bar:30}{r_bar}")

    try:
        while episode < n_episodes:
            for w in range(n_workers):
                actions_per_env = []
                for env_i in range(len(env_splits[w])):
                    env_states  = worker_states[w][env_i]
                    enemy_ids   = worker_enemy_ids[w][env_i]
                    env_actions = []
                    for j, state in enumerate(env_states):
                        eid = enemy_ids[j] if j < len(enemy_ids) else j
                        action, lead_scale = enemy_agent.select_action(state, enemy_id=eid)
                        env_actions.append((action, lead_scale))
                    while len(env_actions) < n_enemies:
                        env_actions.append((0, 0.5))
                    actions_per_env.append(env_actions)
                action_queues[w].put(actions_per_env)

            for w in range(n_workers):
                result = experience_queues[w].get()

                for exp in result["experiences"]:
                    enemy_agent.push(*exp)
                    total_steps += 1

                for mean_r in result["episode_results"]:
                    episode += 1
                    enemy_agent.decay_epsilon()
                    ep_rewards_log.append(mean_r)

                worker_states[w]    = result["states"]
                worker_enemy_ids[w] = result["enemy_ids"]
                worker_counts[w]    = result["enemy_counts"]

            if total_steps % learn_every == 0 and episode > warmup_eps:
                loss = enemy_agent.learn()
                if loss is not None:
                    losses.append(loss)

            if episode - last_print >= print_every and episode > 0:
                last_print  = episode
                recent      = np.mean(ep_rewards_log[-print_every:]) if ep_rewards_log else 0.0
                avg_loss    = np.mean(losses[-100:]) if losses else 0.0
                elapsed     = time.time() - t0
                eps_per_sec = episode / elapsed if elapsed > 0 else 0
                pbar.n = episode
                pbar.set_postfix({
                    "eps":     round(enemy_agent.epsilon, 3),
                    "r":       round(recent, 2),
                    "loss":    round(avg_loss, 4),
                    "ep/s":    round(eps_per_sec, 1),
                    "workers": n_workers,
                })
                pbar.refresh()
                losses = []

            if episode % save_every == 0 and episode > 0:
                enemy_agent.save(enemy_weights)
                print(f"[save] weights saved at episode {episode}")

    finally:
        for q in action_queues:
            q.put("STOP")
        for p in workers:
            p.join(timeout=5)

    pbar.close()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def train():
    """Load enemy types and weights, then dispatch to single or multi-process training based on --mode."""
    build_types()
    print(f"[types] {len(types)} enemy types loaded")

    enemy_agent = DQNagent()
    print(f"[device] {enemy_agent.device} — {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")

    if os.path.exists(enemy_weights):
        enemy_agent.load(enemy_weights)

    profiles = discover_profiles()
    print(f"[profiles] {len(profiles)} loaded: {[p[0] for p in profiles]}")
    print(f"[config] episodes={n_episodes} envs={n_envs} save_every={save_every} mode={mode}")

    if mode == "multi":
        train_multi(enemy_agent, profiles)
    else:
        train_single(enemy_agent, profiles)

    enemy_agent.save(enemy_weights)
    print(f"[save] final weights saved")
    pygame.quit()


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    train()