Song: Chillpeach - In Dreamland : https://www.youtube.com/watch?v=DSWYAclv2I8

Fire sound : https://pixabay.com/sound-effects/film-special-effects-ui-pop-sound-316482/

Death sound: https://pixabay.com/sound-effects/film-special-effects-happy-pop-2-185287/

# Adaptive Enemy AI — Pygame Top-Down Shooter

A top-down shooter where enemies learn from how you play. After each session the game analyses your behaviour, builds a profile, and uses it to adapt enemy speed, aggression, targeting strategy, and fire rate in real time.

---

## How It Works

Every run logs frame-by-frame data — movement, accuracy, evasion, upgrade choices, and positioning. After the game ends this log is sent to an LLM (Groq / LLaMA 3.3) which produces a structured player profile. That profile is merged with previous sessions using exponential smoothing and saved to disk. The next time you play, enemies spawn with scaled stats and use a counter-strategy tailored to your profile.

During a run, a lightweight version of the same analysis runs live every time a stage clears, so enemies start adapting mid-session without waiting for game-over.

---

## How To Start

install all packages in requirements.txt
`pip install -r requirements.txt`

then run
`python main.py`

to train examples for command line 
    `python -m ai.train                          # single, 1000 eps`
    `python -m ai.train --mode single            # explicit single`
    `python -m ai.train --mode multi             # multiprocessing`
    `python -m ai.train --mode multi --workers 7`
    `python -m ai.train --episodes 5000 --envs 128 --mode multi`
    `python -m ai.train --episodes 500 --save-every 50`

## Features

- **LSTM-DQN enemy AI** — enemies use a recurrent deep Q-network with per-enemy hidden state, trained across parallel headless simulations
- **LLM player profiling** — Groq API analyses session logs and produces a JSON profile covering playstyle, accuracy, evasion, preferred range, upgrade priority, and enemy strategy
- **Live in-session adaptation** — `behavior_tracker.py` computes a live profile at each stage clear and pushes spawn multipliers and strategy changes immediately
- **Headless simulation training** — `sim.py` and `train.py` run the full game loop without a display, supporting both single-process and multiprocessing modes
- **Fine-tuning agent** — `FineTuneAgent` fine-tunes a pre-trained base policy against a specific profile using a KL-divergence penalty to limit behavioural drift
- **Tutorial mode** — guided WASD + mouse-1 tutorial that feeds into the same logging and profiling pipeline
- **Simulation mode** — watch an AI player (driven by `AIPlayer`) face the enemy AI so you can observe adaptation without playing

---

## Enemy Types

| # | Name | Description |
|---|------|-------------|
| 0 | Scout | Fastest, paper-thin, rapid chip damage |
| 1 | Tank | Highest HP, slow, hits hard |
| 2 | Skirmisher | Baseline balanced enemy |
| 3 | Glass Cannon | Fragile, fast, high damage |
| 4 | Bruiser | Tanky, constant fire, war of attrition |
| 5 | Assassin | Fragile, fast, closes gap |

---

## Project Structure

```
├── ai/
│   ├── lstm_dqn.py          # LSTM-DQN network
│   ├── dqn_enemy.py         # DQNAgent, build_state(), compute_rewards()
│   ├── replay_buffer.py     # Experience replay buffer
│   ├── sim.py               # Headless RL training environment
│   ├── train.py             # Single and multiprocessing training entry point
│   ├── finetune.py          # FineTuneAgent with KL penalty
│   ├── llm.py               # Groq LLM session synthesis
│   └── weights/             # Saved model checkpoints
│
├── core/
│   ├── behavior_tracker.py  # Live in-session profile computation
│   ├── event_handler.py     # Pygame event routing and firing logic
│   ├── render.py            # Screen rendering (world + HUD)
│   └── profile_manager.py   # Profile initialisation
│
├── entities/
│   ├── enemy.py             # Enemy class + DQN inference
│   ├── enemy_list.py        # Enemy type definitions
│   ├── player.py            # Human player
│   ├── ai_player.py         # Profile-driven AI player
│   └── projections.py       # Projectile class
│
├── game_environments/
│   ├── game.py              # Main game loop
│   ├── tutorial.py          # Tutorial game loop
│   └── simulationenv.py     # AI-vs-AI simulation loop
│
├── menu/
│   ├── main_menu.py
│   ├── pause_menu.py
│   ├── game_over.py
│   ├── level_up_menu.py
│   ├── setting_menu.py
│   └── input_menu.py
│
├── replays/
│   └── <profile_name>/
│       ├── profile.json     # Merged player profile
│       └── *_run_*.json     # Per-session behavior logs
│
├── assets/
├── settings.py
├── main.py                  # Entry point
└── seed_profiles.py         # Generate archetype profiles for testing
```

---

## Setup

```bash
pip install pygame pygame_gui torch numpy groq tqdm
```

Set your Groq API key:
```bash
export GROQ_API_KEY=your_key_here
```

Run the game:
```bash
python main.py
```

---

## Training

```bash
# Single-process (default)
python -m ai.train

# Multiprocessing
python -m ai.train --mode multi --workers 7

# Custom config
python -m ai.train --episodes 5000 --envs 128 --save-every 100
```

Weights are saved to `ai/weights/weights.pt`.

---

## Seed Profiles

To populate the replays directory with hand-crafted archetypes for testing:

```bash
python seed_profiles.py
```

Included archetypes: `the_camper`, `the_rusher`, `the_kiter`, `the_waller`, `the_sniper`, `the_sprayer`, `the_survivor`, `the_random`, `the_flanker`, `the_balanced`, `the_tank_killer`, `the_glass_cannon_hunter`.

---

## Player Profile Fields

| Field | Description |
|-------|-------------|
| `aggression_score` | 0–1, shot density relative to frames |
| `avg_displacement` | Average px moved per frame |
| `avg_center_dist` | 0 = always center, 1 = always corner |
| `evasion_rate` | Fraction of projectiles successfully dodged |
| `accuracy` | Shots hit / shots fired |
| `enemy_strategy` | Counter-strategy: `rush`, `flank`, or `surround` |
| `speed_multiplier` | Applied to enemy speed at spawn |
| `damage_multiplier` | Applied to enemy damage at spawn |
| `fire_rate_multiplier` | Applied to enemy fire rate at spawn |