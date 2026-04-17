import os
import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import random
from ai.replay_buffer import ReplayBuffer
from ai.lstm_dqn import LSTMDQNNet
from settings import screen_height, screen_width, wall_penalty_margin, detection_radius

input_vector  = 30
total_actions = 9
layers        = 512
gamma         = 0.9
learning_rate = 0.001
batch_size    = 512        # was 2048 — smaller batches prevent early overfitting
target_sync   = 500
explore_start = 1.0
explore_end   = 0.15       # was 0.05 — keep more randomness late in training
explore_decay = 0.9995     # was 0.999 — slower decay, more exploration time

diagonal = math.hypot(screen_width, screen_height)

movement = [
    ( 0,  0),   # 0 stay
    ( 0, -1),   # 1 N
    ( 1, -1),   # 2 NE
    ( 1,  0),   # 3 E
    ( 1,  1),   # 4 SE
    ( 0,  1),   # 5 S
    (-1,  1),   # 6 SW
    (-1,  0),   # 7 W
    (-1, -1),   # 8 NW
]


class DQNagent:
    def __init__(self, device: str | None = None):
        self.device    = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.online    = LSTMDQNNet(input_vector, total_actions, layers).to(self.device)
        self.target    = LSTMDQNNet(input_vector, total_actions, layers).to(self.device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()
        self.optimizer = optim.Adam(self.online.parameters(), lr=learning_rate)
        self.buffer    = ReplayBuffer()
        self.epsilon   = explore_start
        self.steps     = 0
        self.hidden    = {}

    def reset_hidden(self, enemy_id=None):
        if enemy_id is None:
            self.hidden = {}
        else:
            self.hidden.pop(enemy_id, None)

    def select_action(self, state, enemy_id):
        if random.random() < self.epsilon:
            return random.randrange(total_actions), 0.5
        with torch.no_grad():
            s              = torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            hidden         = self.hidden.get(enemy_id)
            q, lead, new_hidden = self.online(s, hidden)
            self.hidden[enemy_id] = new_hidden
            action     = int(q.argmax(dim=1).item())
            lead_scale = float(lead.item())
            return action, lead_scale

    def action_to_direction(self, action):
        dx, dy = movement[action]
        length = math.hypot(dx, dy)
        if length > 0:
            return dx / length, dy / length
        return 0.0, 0.0

    def push(self, state, action, reward, next_state, done):
        self.buffer.push(state, action, reward, next_state, done)
        self.steps += 1
        if self.steps % target_sync == 0:
            self.target.load_state_dict(self.online.state_dict())

    def learn(self):
        if len(self.buffer) < batch_size:
            return None

        states, actions, rewards, next_states, dones = self.buffer.sample(batch_size)
        s  = torch.tensor(states,      dtype=torch.float32, device=self.device)
        a  = torch.tensor(actions,     dtype=torch.long,    device=self.device)
        r  = torch.tensor(rewards,     dtype=torch.float32, device=self.device)
        ns = torch.tensor(next_states, dtype=torch.float32, device=self.device)
        d  = torch.tensor(dones,       dtype=torch.float32, device=self.device)

        q_vals, _, _ = self.online(s)
        q_vals       = q_vals.gather(1, a.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            next_q, _, _ = self.target(ns)
            target       = r + gamma * next_q.max(dim=1).values * (1 - d)

        loss = nn.functional.mse_loss(q_vals, target)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 10)
        self.optimizer.step()
        return loss.item()

    def decay_epsilon(self):
        self.epsilon = max(explore_end, self.epsilon * explore_decay)

    def save(self, path: str = "ai/weights/weights.pt"):
        torch.save({
            "online":  self.online.state_dict(),
            "target":  self.target.state_dict(),
            "epsilon": self.epsilon,
            "steps":   self.steps,
        }, path)

    def load(self, path: str = "ai/weights/weights.pt"):
        ck = torch.load(path, map_location=self.device, weights_only=True)
        self.online.load_state_dict(ck["online"])
        self.target.load_state_dict(ck["target"])
        self.epsilon = ck.get("epsilon", explore_end)
        self.steps   = ck.get("steps", 0)


def build_state(enemy, player, projectile, allies, profile=None):
    ex = enemy.pos.x
    ey = enemy.pos.y
    px = player.pos.x
    py = player.pos.y

    rel_px = (px - ex) / screen_width
    rel_py = (py - ey) / screen_height
    p_vx   = player.vel.x / detection_radius
    p_vy   = player.vel.y / detection_radius
    hp_r   = enemy.health / enemy.maxhealth

    near   = [p for p in projectile if enemy.pos.distance_to(p.pos) < detection_radius]
    n_near = min(len(near), 10) / 10

    if near:
        closest = min(near, key=lambda p: enemy.pos.distance_to(p.pos))
        np_rx   = (closest.pos.x - ex) / detection_radius
        np_ry   = (closest.pos.y - ey) / detection_radius
        np_vx   = closest.velocity.x / 500
        np_vy   = closest.velocity.y / 500
    else:
        np_rx = 0.0
        np_ry = 0.0
        np_vx = 0.0
        np_vy = 0.0

    ally_feats = []
    for a in allies[:5]:
        ally_feats += [(a.pos.x - ex) / screen_width, (a.pos.y - ey) / screen_height]
    while len(ally_feats) < 10:
        ally_feats += [0.0, 0.0]

    angle  = math.atan2(py - ey, px - ex) / math.pi
    dist   = enemy.pos.distance_to(player.pos) / diagonal
    wall_x = min(ex, screen_width  - ex) / screen_width
    wall_y = min(ey, screen_height - ey) / screen_height

    state = [rel_px, rel_py, p_vx, p_vy, hp_r,
             n_near, np_rx, np_ry, np_vx, np_vy,
             *ally_feats, angle, dist, wall_x, wall_y]

    if profile:
        state += [
            float(profile.get("aggression_score",  0.5)),
            float(profile.get("avg_displacement",  25.0)) / 50.0,
            float(profile.get("avg_center_dist",   0.5)),
            float(profile.get("evasion_rate",      0.5)),
            float(profile.get("accuracy",          0.5)),
            float(profile.get("session_count",     1)) / 10.0,
        ]
    else:
        state += [0.5, 0.5, 0.5, 0.5, 0.5, 0.1]

    return np.array(state, dtype=np.float32)


def compute_rewards(enemy, player, allies, prev_player_health, curr_player_health,
                    hit_by_projectile, died, profile=None):
    reward = 0.0
    damage = prev_player_health - curr_player_health
    reward += damage * 1.0
    reward += 0.1

    if died:
        reward -= 5.0
        return reward

    # Spread bonus — reward enemies for surrounding the player
    alive = [e for e in allies if e.health > 0] + [enemy]
    if len(alive) > 1:
        angles = [math.atan2(e.pos.y - player.pos.y, e.pos.x - player.pos.x) for e in alive]
        angles.sort()
        gaps         = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)]
        gaps.append(angles[0] + 2 * math.pi - angles[-1])
        spread_bonus = 1 - (np.std(gaps) / math.pi)
        reward      += spread_bonus * 0.1

    # Penalty for clustering with allies
    for a in allies:
        if a is not enemy and a.health > 0:
            if enemy.pos.distance_to(a.pos) < 25:
                reward -= 0.5

    # Wall penalties
    if enemy.pos.x < wall_penalty_margin:
        reward -= 0.5 * (wall_penalty_margin - enemy.pos.x) / wall_penalty_margin
    if enemy.pos.x > screen_width - wall_penalty_margin:
        reward -= 0.5 * (enemy.pos.x - (screen_width - wall_penalty_margin)) / wall_penalty_margin
    if enemy.pos.y < wall_penalty_margin:
        reward -= 0.5 * (wall_penalty_margin - enemy.pos.y) / wall_penalty_margin
    if enemy.pos.y > screen_height - wall_penalty_margin:
        reward -= 0.5 * (enemy.pos.y - (screen_height - wall_penalty_margin)) / wall_penalty_margin

    if hit_by_projectile:
        reward -= 1.0

    # Strategy-based positioning rewards
    distance = enemy.pos.distance_to(player.pos)
    default  = random.choice(["rush", "flank", "surround"])
    strategy = profile.get("enemy_strategy", default) if profile else default

    if strategy == "rush":
        if distance > 250:
            reward -= 0.3 * (distance / 250)

    elif strategy == "flank":
        if distance < 150:
            reward -= 0.2
        elif distance > 400:
            reward -= 0.2

    elif strategy == "surround":
        if distance < 100:
            reward -= 0.3

    return float(reward)