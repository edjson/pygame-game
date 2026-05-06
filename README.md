Song: Chillpeach - In Dreamland : https://www.youtube.com/watch?v=DSWYAclv2I8

Fire sound : https://pixabay.com/sound-effects/film-special-effects-ui-pop-sound-316482/

Death sound: https://pixabay.com/sound-effects/film-special-effects-happy-pop-2-185287/

# Adaptive Enemy AI — Pygame Top-Down Shooter

A top-down shooter where enemies learn from how you play. After each session the game analyses your behaviour, builds a profile, and uses it to adapt enemy speed, aggression, targeting strategy, and fire rate in real time.

---

## How It Works

Every run logs frame-by-frame data — movement, accuracy, evasion, upgrade choices, and positioning. After the game ends this log is sent to an LLM (Groq / LLaMA 3.3) which produces a structured player profile. That profile is merged with previous sessions using exponential smoothing and saved to disk at a 70 / 30 ratio. The next time you play, enemies spawn with scaled stats and use a counter-strategy tailored to your profile.

During a run, a lightweight version of the same analysis runs live every time a stage clears (from stage 3+), so enemies start adapting mid-session without waiting for game-over. This was implemented because at start the enemy will not know the player. This way having the 3 stages info gathering, the enemy would be better informed. 

---

## How To Start

Install all packages in requirements.txt:
```bash
pip install -r requirements.txt
```

To set your Groq API key in the terminal:
```bash
export GROQ_API_KEY=your_key_here
```

Run the game:
```bash
python main.py
```

To train — examples for command line:
```bash
python -m ai.train                           # single, 1000 eps
python -m ai.train --mode single             # explicit single
python -m ai.train --mode multi              # multiprocessing
python -m ai.train --mode multi --workers 7
python -m ai.train --episodes 5000 --envs 128 --mode multi
python -m ai.train --episodes 500 --save-every 50
```

---

## Features

- **LSTM-DQN enemy AI** — enemies use a recurrent deep Q-network with per-enemy hidden state, trained across parallel headless simulations
- **LLM player profiling** — Groq API analyses session logs and produces a JSON profile covering playstyle, accuracy, evasion, preferred range, upgrade priority, Myers-Briggs personality estimate, and enemy strategy
- **Live in-session adaptation** — `behavior_tracker.py` computes a live profile at each stage clear (stage 3+) and pushes spawn multipliers and strategy changes immediately
- **Approach-ratio aggression** — aggression is measured by how often the player closes the gap vs retreats from the nearest enemy, giving a more accurate read than raw shot count
- **Enemy strategy overrides** — enemies use `rush` (direct charge), `flank` (angled approach), or `surround` (evenly distributed around player) based on the computed counter-strategy
- **Particle effects** — enemies burst into particles on death, colored to match their type
- **Sprite support** — player and projectiles use PNG sprites with velocity-aligned rotation
- **Sound effects** — shoot and death SFX that respect the master volume setting
- **Headless simulation training** — `sim.py` and `train.py` run the full game loop without a display, supporting both single-process and multiprocessing modes
- **Fine-tuning agent** — `FineTuneAgent` fine-tunes a pre-trained base policy against a specific profile using a KL-divergence penalty to limit behavioural drift
- **Tutorial mode** — guided WASD + mouse-1 tutorial that feeds into the same logging and profiling pipeline; tutorial enemy is a stationary dud with no AI
- **Simulation mode** — watch an AI player (driven by `AIPlayer`) face the enemy AI so you can observe adaptation without playing (does not train model directly just to analyze AI Player)
- **Profile merging** — each session is exponentially smoothed (70/30) with the prior profile so the enemy adapts gradually across multiple runs
- **Trajectory lines** — optional trace mode draws projectile trajectory lines from current position forward (for prediction observatons)

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
| 6 | Tutorial | Stationary dud, no AI, used in tutorial only |

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
│   ├── behavior_tracker.py  # Live in-session profile computation (approach-ratio aggression)
│   ├── event_handler.py     # Pygame event routing and firing logic
│   ├── render.py            # Screen rendering (world + HUD + particles + trajectory lines)
│   └── profile_manager.py   # Profile initialisation
│
├── entities/
│   ├── enemy.py             # Enemy class + DQN inference + strategy overrides
│   ├── enemy_list.py        # Enemy type definitions
│   ├── player.py            # Human player with sprite and shoot SFX
│   ├── ai_player.py         # Profile-driven AI player
│   ├── projections.py       # Projectile class with sprite + velocity rotation
│   └── particles.py         # Death particle effect system
│
├── game_environments/
│   ├── game.py              # Main game loop (inheritable base)
│   ├── tutorial.py          # Tutorial — inherits Game, disables enemy AI during tutorial phase
│   └── simulationenv.py     # AI-vs-AI visual simulation loop
│
├── assets/
│   ├── audio/               # Music and SFX files
│   └── sprites/             # Player, enemy, and projectile PNGs
│       ├── assets.py        # Music and SFX loader classes
│
├── menu/
│   ├── main_menu.py
│   ├── pause_menu.py
│   ├── game_over.py
│   ├── level_up_menu.py
│   ├── setting_menu.py      # Volume slider + trace toggle
│   └── input_menu.py
│
├── replays/
│   └── <profile_name>/
│       ├── profile.json     # Merged player profile
│       └── *_run_*.json     # Per-session behavior logs
│
├── settings.py
├── main.py                  # Entry point
└── seed_profiles.py         # Generate archetype profiles for testing
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
python generate_profiles.py
```

Included archetypes: `the_camper`, `the_rusher`, `the_kiter`, `the_waller`, `the_sniper`, `the_sprayer`, `the_survivor`, `the_random`, `the_flanker`, `the_balanced`, `the_tank_killer`, `the_glass_cannon_hunter`.

---

## Player Profile Fields

| Field | Description |
|-------|-------------|
| `aggression_score` | Approach ratio — how often the player closes the gap vs retreats |
| `approach_ratio` | Raw closing-in fraction (0=always retreating, 1=always closing in) |
| `avg_displacement` | Average px moved per frame |
| `avg_center_dist` | 0 = always center, 1 = always corner |
| `evasion_rate` | Fraction of projectiles successfully dodged |
| `accuracy` | Shots hit / shots fired |
| `preferred_range` | `close`, `medium`, or `far` based on avg distance to nearest enemy |
| `enemy_strategy` | Counter-strategy: `rush`, `flank`, or `surround` |
| `playstyle` | `aggressive`, `defensive`, or `random` |
| `speed_multiplier` | Applied to enemy speed at spawn |
| `damage_multiplier` | Applied to enemy damage at spawn |
| `fire_rate_multiplier` | Applied to enemy fire rate at spawn |
| `session_count` | Number of sessions merged into this profile |