import os
import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import random
from ai.replay_buffer import ReplayBuffer
from ai.lstm_dqn import LSTMDQNNet

input_vector  = 30
total_actions = 9
layers        = 512
gamma         = 0.9
learning_rate = 0.00001
epsilon       = 0.05
batch_size    = 32
sync          = 200
penalty_weight = 2
base_weights  = "ai/weights/weights.pt"
ft_weights    = "ai/weights/weights_finetuned.pt"


class FineTuneAgent:
    def __init__(self, device: str | None = None):
        self.device  = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.base    = LSTMDQNNet(input_vector, total_actions, layers).to(self.device)
        self.online  = LSTMDQNNet(input_vector, total_actions, layers).to(self.device)
        self.target  = LSTMDQNNet(input_vector, total_actions, layers).to(self.device)
        self.base.eval()
        for p in self.base.parameters():
            p.requires_grad = False
        self.optimizer = optim.Adam(self.online.parameters(), lr=learning_rate)
        self.buffer    = ReplayBuffer(capacity=200_000)
        self.epsilon   = epsilon
        self.steps     = 0
        self.hidden    = {}   # per-enemy LSTM hidden state (matches DQNagent pattern)
        self.load()

    def load(self):
        if os.path.exists(base_weights):
            ck = torch.load(base_weights, map_location=self.device, weights_only=True)
            self.base.load_state_dict(ck["online"])
            self.online.load_state_dict(ck["online"])
            self.target.load_state_dict(ck["online"])

        if os.path.exists(ft_weights):
            ck = torch.load(ft_weights, map_location=self.device, weights_only=True)
            self.online.load_state_dict(ck["online"])
            self.target.load_state_dict(ck["target"])
            self.steps = ck.get("steps", 0)

        self.target.eval()

    def select_action(self, state, enemy_id=None):
        if random.random() < self.epsilon:
            return random.randrange(total_actions), 0.5
        with torch.no_grad():
            s      = torch.tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            hidden = self.hidden.get(enemy_id) if enemy_id is not None else None
            q, lead, new_hidden = self.online(s, hidden)   # unpack all 3
            if enemy_id is not None:
                self.hidden[enemy_id] = new_hidden
            return int(q.argmax(dim=1).item()), float(lead.item())

    def push(self, state, action, reward, next_state, done):
        self.buffer.push(state, action, reward, next_state, done)
        self.steps += 1
        if self.steps % sync == 0:
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

        # online forward — unpack 3 values
        q_vals, _, _    = self.online(s)
        q_vals          = q_vals.gather(1, a.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            next_q, _, _ = self.target(ns)
            td_target    = r + gamma * next_q.max(dim=1).values * (1 - d)

        dqn_loss = nn.functional.mse_loss(q_vals, td_target)

        # KL penalty to stay close to base policy
        with torch.no_grad():
            base_q, _, _ = self.base(s)

        online_q, _, _  = self.online(s)
        base_probs      = torch.softmax(base_q,   dim=1)
        online_probs    = torch.softmax(online_q, dim=1)
        kl_loss         = nn.functional.kl_div(
            online_probs.log(), base_probs, reduction="batchmean"
        )

        loss = dqn_loss + penalty_weight * kl_loss
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online.parameters(), 10)
        self.optimizer.step()
        return loss.item()

    def save(self):
        torch.save({
            "online": self.online.state_dict(),
            "target": self.target.state_dict(),
            "steps":  self.steps,
        }, ft_weights)