import json
import os

profiles = [
    {
        "name": "the_camper",
        "profile": {
            "level_up_priority": ["Max Health", "Health Regen", "Heal", "Speed", "Damage"],
            "playstyle": "defensive",
            "aggression_score": 0.1,
            "accuracy_rating": "excellent",
            "preferred_range": "far",
            "weakness": "Player rarely moves and gets overwhelmed when Scouts and Assassins close the gap.",
            "enemy_strategy": "surround",
            "summary": "Stationary sniper who waits for enemies to walk into their crosshair — likely patient and methodical, prefers control over chaos.",
            "avg_displacement": 2.1,
            "avg_center_dist": 0.05,
            "avg_edge_dist": 0.45,
            "dodge_ratio": 0.6,
            "evasion_rate": 0.1,
            "accuracy": 0.78,
            "avg_frames_since_shot": 6.2,
            "avg_damage_taken": -18.4,
            "session_count": 1,
            "enemy_type_engagement": {"0": 120, "1": 80, "2": 200, "3": 60, "4": 90, "5": 50}
        }
    },
    {
        "name": "the_rusher",
        "profile": {
            "level_up_priority": ["Damage", "Speed", "Heal", "Max Health", "Health Regen"],
            "playstyle": "aggressive",
            "aggression_score": 0.95,
            "accuracy_rating": "poor",
            "preferred_range": "close",
            "weakness": "Player charges into Bruiser and Tank clusters and takes massive sustained damage.",
            "enemy_strategy": "rush",
            "summary": "All-in brawler who sprints into melee range without regard for incoming fire — likely impulsive with high risk tolerance.",
            "avg_displacement": 38.5,
            "avg_center_dist": 0.4,
            "avg_edge_dist": 0.35,
            "dodge_ratio": 0.8,
            "evasion_rate": 0.05,
            "accuracy": 0.31,
            "avg_frames_since_shot": 1.8,
            "avg_damage_taken": -32.1,
            "session_count": 1,
            "enemy_type_engagement": {"0": 300, "1": 50, "2": 180, "3": 220, "4": 40, "5": 210}
        }
    },
    {
        "name": "the_kiter",
        "profile": {
            "level_up_priority": ["Speed", "Damage", "Health Regen", "Heal", "Max Health"],
            "playstyle": "aggressive",
            "aggression_score": 0.6,
            "accuracy_rating": "good",
            "preferred_range": "medium",
            "weakness": "Player loses kiting lanes near walls and struggles when Assassins flank from behind.",
            "enemy_strategy": "flank",
            "summary": "Mobile skirmisher who keeps enemies at mid-range while constantly repositioning — likely strategic and reads spatial situations well.",
            "avg_displacement": 52.3,
            "avg_center_dist": 0.3,
            "avg_edge_dist": 0.55,
            "dodge_ratio": 0.75,
            "evasion_rate": 0.65,
            "accuracy": 0.61,
            "avg_frames_since_shot": 3.1,
            "avg_damage_taken": -8.2,
            "session_count": 1,
            "enemy_type_engagement": {"0": 250, "1": 60, "2": 200, "3": 180, "4": 70, "5": 240}
        }
    },
    {
        "name": "the_waller",
        "profile": {
            "level_up_priority": ["Max Health", "Damage", "Health Regen", "Speed", "Heal"],
            "playstyle": "defensive",
            "aggression_score": 0.3,
            "accuracy_rating": "average",
            "preferred_range": "medium",
            "weakness": "Player backs into corners and gets trapped with no escape — Assassins and Scouts exploit this completely.",
            "enemy_strategy": "surround",
            "summary": "Wall-hugger who uses edges as cover and waits for clean shots — likely cautious and prefers a safe anchor point.",
            "avg_displacement": 18.7,
            "avg_center_dist": 0.85,
            "avg_edge_dist": 0.08,
            "dodge_ratio": 0.5,
            "evasion_rate": 0.3,
            "accuracy": 0.48,
            "avg_frames_since_shot": 5.5,
            "avg_damage_taken": -14.6,
            "session_count": 1,
            "enemy_type_engagement": {"0": 100, "1": 150, "2": 200, "3": 80, "4": 160, "5": 110}
        }
    },
    {
        "name": "the_sniper",
        "profile": {
            "level_up_priority": ["Damage", "Max Health", "Speed", "Heal", "Health Regen"],
            "playstyle": "defensive",
            "aggression_score": 0.4,
            "accuracy_rating": "excellent",
            "preferred_range": "far",
            "weakness": "Player freezes when multiple Scouts and Assassins close in simultaneously.",
            "enemy_strategy": "rush",
            "summary": "Precision shooter who waits for clean shots from maximum distance — likely detail-oriented and dislikes wasted effort.",
            "avg_displacement": 9.4,
            "avg_center_dist": 0.15,
            "avg_edge_dist": 0.42,
            "dodge_ratio": 0.45,
            "evasion_rate": 0.55,
            "accuracy": 0.88,
            "avg_frames_since_shot": 8.3,
            "avg_damage_taken": -11.3,
            "session_count": 1,
            "enemy_type_engagement": {"0": 80, "1": 200, "2": 180, "3": 60, "4": 210, "5": 70}
        }
    },
    {
        "name": "the_sprayer",
        "profile": {
            "level_up_priority": ["Damage", "Speed", "Heal", "Health Regen", "Max Health"],
            "playstyle": "aggressive",
            "aggression_score": 0.8,
            "accuracy_rating": "poor",
            "preferred_range": "medium",
            "weakness": "Player fires constantly without aiming — Tanks absorb all of it while Bruisers out-sustain the spray.",
            "enemy_strategy": "rush",
            "summary": "Spray-and-pray fighter who bets on volume of fire over precision — likely reactive and prefers action over planning.",
            "avg_displacement": 29.1,
            "avg_center_dist": 0.25,
            "avg_edge_dist": 0.38,
            "dodge_ratio": 0.7,
            "evasion_rate": 0.2,
            "accuracy": 0.22,
            "avg_frames_since_shot": 1.2,
            "avg_damage_taken": -21.5,
            "session_count": 1,
            "enemy_type_engagement": {"0": 280, "1": 100, "2": 220, "3": 200, "4": 130, "5": 190}
        }
    },
    {
        "name": "the_survivor",
        "profile": {
            "level_up_priority": ["Heal", "Health Regen", "Max Health", "Speed", "Damage"],
            "playstyle": "defensive",
            "aggression_score": 0.2,
            "accuracy_rating": "average",
            "preferred_range": "far",
            "weakness": "Player stacks healing but deals so little damage that Bruiser and Tank waves outlast them.",
            "enemy_strategy": "surround",
            "summary": "Pure survivalist who avoids damage and stacks sustain at all costs — likely risk-averse and plays the long game.",
            "avg_displacement": 24.6,
            "avg_center_dist": 0.2,
            "avg_edge_dist": 0.5,
            "dodge_ratio": 0.65,
            "evasion_rate": 0.7,
            "accuracy": 0.45,
            "avg_frames_since_shot": 7.1,
            "avg_damage_taken": -5.1,
            "session_count": 1,
            "enemy_type_engagement": {"0": 160, "1": 90, "2": 210, "3": 130, "4": 80, "5": 130}
        }
    },
    {
        "name": "the_random",
        "profile": {
            "level_up_priority": ["Heal", "Speed", "Damage", "Max Health", "Health Regen"],
            "playstyle": "random",
            "aggression_score": 0.5,
            "accuracy_rating": "poor",
            "preferred_range": "medium",
            "weakness": "Player has no consistent pattern — efficient enemies adapt faster than they do.",
            "enemy_strategy": "flank",
            "summary": "Chaotic player with no repeatable strategy — likely a new player still learning or someone experimenting with the game.",
            "avg_displacement": 33.2,
            "avg_center_dist": 0.45,
            "avg_edge_dist": 0.33,
            "dodge_ratio": 0.55,
            "evasion_rate": 0.25,
            "accuracy": 0.28,
            "avg_frames_since_shot": 4.8,
            "avg_damage_taken": -19.7,
            "session_count": 1,
            "enemy_type_engagement": {"0": 170, "1": 140, "2": 190, "3": 150, "4": 130, "5": 160}
        }
    },
    {
        "name": "the_flanker",
        "profile": {
            "level_up_priority": ["Speed", "Damage", "Heal", "Health Regen", "Max Health"],
            "playstyle": "aggressive",
            "aggression_score": 0.75,
            "accuracy_rating": "good",
            "preferred_range": "close",
            "weakness": "Player over-commits to flanking routes and loses track of Glass Cannon and Bruiser projectiles from behind.",
            "enemy_strategy": "flank",
            "summary": "Calculated aggressor who circles enemies and attacks from angles — likely competitive and enjoys outplaying opponents.",
            "avg_displacement": 45.8,
            "avg_center_dist": 0.55,
            "avg_edge_dist": 0.4,
            "dodge_ratio": 0.72,
            "evasion_rate": 0.5,
            "accuracy": 0.67,
            "avg_frames_since_shot": 2.4,
            "avg_damage_taken": -13.8,
            "session_count": 1,
            "enemy_type_engagement": {"0": 230, "1": 70, "2": 190, "3": 210, "4": 60, "5": 240}
        }
    },
    {
        "name": "the_balanced",
        "profile": {
            "level_up_priority": ["Damage", "Health Regen", "Speed", "Max Health", "Heal"],
            "playstyle": "aggressive",
            "aggression_score": 0.55,
            "accuracy_rating": "good",
            "preferred_range": "medium",
            "weakness": "Player is well-rounded but lacks a dominant trait — no clear exploit but no dominant edge either.",
            "enemy_strategy": "surround",
            "summary": "All-around solid player with no glaring weakness — likely experienced, adaptable, and reads situations before committing.",
            "avg_displacement": 28.4,
            "avg_center_dist": 0.28,
            "avg_edge_dist": 0.44,
            "dodge_ratio": 0.62,
            "evasion_rate": 0.55,
            "accuracy": 0.63,
            "avg_frames_since_shot": 3.6,
            "avg_damage_taken": -10.2,
            "session_count": 1,
            "enemy_type_engagement": {"0": 180, "1": 160, "2": 200, "3": 170, "4": 150, "5": 140}
        }
    },
    {
        "name": "the_tank_killer",
        "profile": {
            "level_up_priority": ["Damage", "Max Health", "Health Regen", "Heal", "Speed"],
            "playstyle": "aggressive",
            "aggression_score": 0.65,
            "accuracy_rating": "good",
            "preferred_range": "medium",
            "weakness": "Player focuses Tanks and ignores fast enemies — Scouts and Assassins chip them down uncontested.",
            "enemy_strategy": "rush",
            "summary": "Target-priority player who focuses the biggest threats first — likely analytical and plays with a mental priority list.",
            "avg_displacement": 22.3,
            "avg_center_dist": 0.35,
            "avg_edge_dist": 0.42,
            "dodge_ratio": 0.6,
            "evasion_rate": 0.4,
            "accuracy": 0.7,
            "avg_frames_since_shot": 4.1,
            "avg_damage_taken": -15.3,
            "session_count": 1,
            "enemy_type_engagement": {"0": 60, "1": 400, "2": 150, "3": 80, "4": 300, "5": 70}
        }
    },
    {
        "name": "the_glass_cannon_hunter",
        "profile": {
            "level_up_priority": ["Speed", "Damage", "Heal", "Max Health", "Health Regen"],
            "playstyle": "aggressive",
            "aggression_score": 0.85,
            "accuracy_rating": "average",
            "preferred_range": "close",
            "weakness": "Player dives Glass Cannons and Scouts but ignores Bruisers who punish the recklessness.",
            "enemy_strategy": "rush",
            "summary": "Kill-the-weak-first player who hunts fragile high-damage enemies before they fire — likely proactive and hates taking avoidable damage.",
            "avg_displacement": 48.1,
            "avg_center_dist": 0.5,
            "avg_edge_dist": 0.38,
            "dodge_ratio": 0.78,
            "evasion_rate": 0.35,
            "accuracy": 0.52,
            "avg_frames_since_shot": 2.0,
            "avg_damage_taken": -22.6,
            "session_count": 1,
            "enemy_type_engagement": {"0": 350, "1": 40, "2": 160, "3": 380, "4": 50, "5": 320}
        }
    }
]

# Save each profile
base_dir = os.path.dirname(os.path.abspath(__file__))
for p in profiles:
    save_dir = os.path.join(base_dir, "replays", p["name"])
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "profile.json")
    # remove name key before saving — profile.json only stores the profile data
    profile_data = {k: v for k, v in p["profile"].items()}
    with open(save_path, "w") as f:
        json.dump(profile_data, f, indent=2)
    print(f"Saved: {save_path}")

print(f"\nDone — {len(profiles)} profiles generated.")