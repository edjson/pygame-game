import random
import numpy as np
from collections import deque

class ReplayBuffer:
    """Fixed-capacity circular buffer storing (s, a, r, s', done) transitions for DQN training."""

    def __init__(self, capacity: int = 200000):
        """Initialise the deque with a maximum capacity, evicting oldest entries when full."""   
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        """Normalise and append a single transition, casting to float32/int for memory efficiency."""
        self.buffer.append((
            np.array(state,      dtype=np.float32),
            int(action),
            float(reward),
            np.array(next_state, dtype=np.float32),
            float(done),
        ))

    def sample(self, batch_size):
        """Return a random batch of transitions as stacked numpy arrays, ready for tensor conversion."""
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        return (
            np.stack(states),
            np.array(actions),
            np.array(rewards),
            np.stack(next_states),
            np.array(dones),
        )

    def __len__(self):
        """Return the current number of stored transitions."""
        return len(self.buffer)