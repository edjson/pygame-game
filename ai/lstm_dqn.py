import torch
import torch.nn as nn

class LSTMDQNNet(nn.Module):
    """LSTM-based DQN that returns Q-values, a lead probability, and updated hidden state."""

    def __init__(self, state_dim: int, action_dim: int, hidden: int = 128):
        """Build encoder, single-layer LSTM, Q-value head, and sigmoid lead head."""
        super().__init__()
        self.hidden_size = hidden
        self.encoder = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
        )

        self.head_lead = nn.Sequential(
            nn.Linear(hidden, 32),
            nn.ReLU(), 
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

        self.lstm = nn.LSTM(
            input_size=hidden,
            hidden_size=hidden,
            num_layers=1,
            batch_first=True,
        )

        self.head = nn.Sequential(
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, action_dim),
        )
        
    def forward(self, x, hidden=None):
        """Encode x, run LSTM, and return (Q-values, lead probability, hidden state) for the last timestep."""
        if x.dim() == 2:
            x = x.unsqueeze(1)   
        enc = self.encoder(x)    
        out, hidden = self.lstm(enc, hidden)
        last = out[:, -1, :]         
        q = self.head(last) 
        lead = self.head_lead(last)
        return q, lead, hidden
    
    def init_hidden(self, batch_size: int = 1, device: str = "cpu"):
        """Return zeroed (h_0, c_0) LSTM state for the start of an episode."""
        h = torch.zeros(1, batch_size, self.hidden_size, device=device)
        c = torch.zeros(1, batch_size, self.hidden_size, device=device)
        return (h, c)