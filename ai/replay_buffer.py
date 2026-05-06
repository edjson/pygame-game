import random
import numpy as np
from collections import deque

class ReplayBuffer:
    """Fixed-capacity circular buffer storing (s, a, r, s', done) transitions for DQN training."""

    def __init__(self, capacity: int = 200000, seq_len = 16):
        """Initialise the deque with a maximum capacity, evicting oldest entries when full."""   
        self.buffer = deque(maxlen=capacity)
        self.staging = {}
        self.seq_len = seq_len

    def push(self, enemy_id, episode_id, state, action, reward, next_state, done):
        """Normalise and app end a single transition, casting to float32/int for memory efficiency."""
        key = (enemy_id, episode_id)

        if key not in self.staging:
            self.staging[key] = []

        self.staging[key].append((
            np.array(state, dtype=np.float32),
            int(action),
            float(reward),
            np.array(next_state, dtype=np.float32),
            float(done),
        ))
 
        if len(self.staging[key]) >= self.seq_len:
            self._commit(key)
 
        if done:
            self.flush(enemy_id, episode_id)
    
    def flush(self, enemy_id, episode_id):
        """ommit any incomplete staging sequence padding with zero transitions for reach seq_len."""
        key = (enemy_id, episode_id)
        if key not in self.staging or len(self.staging[key]) == 0:
            return 
        seq = self.staging.pop(key)
        while len(seq) < self.seq_len:
            zero_state = np.zeros_like(seq[0][0])
            seq.append((zero_state, 0, 0.0, zero_state, 1.0))
        self.buffer.append(seq)
    
    def _commit(self, key):
        self.buffer.append(list(self.staging.pop(key)))


    def sample(self, batch_size):
        """Return a random batch of transitions as stacked numpy arrays, ready for tensor conversion."""
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = [], [], [], [], []
        for seq in batch:
            s, a, r, ns, d = zip(*seq)
            states.append(np.stack(s))
            actions.append(np.array(a))
            rewards.append(np.array(r))
            next_states.append(np.stack(ns))
            dones.append(np.array(d))

        return (
            np.stack(states),
            np.stack(actions),
            np.stack(rewards),
            np.stack(next_states),
            np.stack(dones),
        )

    def __len__(self):
        """Return the current number of stored transitions."""
        return len(self.buffer)