import json
import os
from groq import Groq

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

client = Groq(api_key=os.environ.get("GROQ_API_KEY", "api key"))


def merge_profiles(old, new):
    """Exponentially smooth numeric profile fields (70/30) and increment session count."""
    weight = 0.7
    numeric_keys =[
        "aggression_score", "avg_displacement", "avg_center_dist",
        "evasion_rate", "accuracy", "session_count"
    ]

    merged = dict(new)
    for key in numeric_keys:
        if key in old and key in new:
            merged[key] = round(new[key] * weight + old[key] * (1-weight), 3)
    merged["session_count"] = old.get("session_count", 1) + 1
    return merged

def synthesis(log_path, profile_name):
    """Aggregate a session log into stats, send them to the LLM, merge with prior profile, and save."""
    print(f"synthesis() called with log_path={log_path}, profile={profile_name}")

    try:
        with open(log_path) as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Failed to load log file: {e}")
        return None

    if not log:
        print("Empty log, skipping analysis")
        return None

    total_frames  = len(log)
    avg_health    = sum(f["player_health"] for f in log) / total_frames
    stages        = log[-1]["stage"]
    actions       = [f["player_action"] for f in log]
    action_counts = {a: actions.count(a) for a in set(actions)}

    last = log[-1]

    shots_fired = last.get("shots_fired", action_counts.get("shoot", 0))
    shots_hit   = last.get("shots_hit", 0)
    accuracy    = round(shots_hit / shots_fired, 2) if shots_fired > 0 else 0.0

    avg_enemy_dist = sum(
        sum(e.get("dist_to_player", 0) for e in f["enemies"]) / max(len(f["enemies"]), 1)
        for f in log if f["enemies"]
    ) / max(sum(1 for f in log if f["enemies"]), 1)

    level_up_choices = {}
    for frame in reversed(log):
        if "level_up_priority" in frame:
            level_up_choices = frame["level_up_priority"]
            break
    print(f"[llm] level_up_choices pulled: {level_up_choices}")

    avg_center_dist  = round(sum(f.get("center_dist", 0.5) for f in log) / total_frames, 3)
    avg_edge_dist    = round(sum(f.get("edge_dist", 0.5) for f in log) / total_frames, 3)
    avg_displacement = round(sum(f.get("displacement", 0) for f in log) / total_frames, 2)

    frames_with_incoming  = sum(1 for f in log if f.get("incoming_projectile_count", 0) > 0)
    dodge_ratio           = round(frames_with_incoming / total_frames, 3)
    avg_frames_since_shot = round(
        sum(f.get("frames_since_shot", 0) for f in log) / total_frames, 1)

    nearest_types = [f["nearest_enemy"]["type"] for f in log
                     if f.get("nearest_enemy") and f["nearest_enemy"]["type"]]
    type_counts = {t: nearest_types.count(t) for t in set(nearest_types)} if nearest_types else {}

    negative_deltas  = [f.get("health_delta", 0) for f in log if f.get("health_delta", 0) < 0]
    avg_damage_taken = round(sum(negative_deltas) / len(negative_deltas), 1) if negative_deltas else 0

    summary = {
        "profile":               profile_name,
        "total_frames":          total_frames,
        "stages_reached":        stages,
        "shots_fired":           shots_fired,
        "shots_hit":             shots_hit,
        "accuracy":              accuracy,
        "avg_health":            round(avg_health, 1),
        "avg_enemy_distance":    round(avg_enemy_dist, 1),
        "action_breakdown":      action_counts,
        "level_up_choices":      level_up_choices,
        "avg_center_dist":       avg_center_dist,
        "avg_edge_dist":         avg_edge_dist,
        "avg_displacement":      avg_displacement,
        "dodge_ratio":           dodge_ratio,
        "avg_frames_since_shot": avg_frames_since_shot,
        "enemy_type_engagement": type_counts,
        "avg_damage_taken":      avg_damage_taken,
        "evasion_attempted":     log[-1].get("evasions_attempted", 0),
        "evasion_successful":    log[-1].get("evasions_successful", 0),
        "evasion_rate":          log[-1].get("evasion_rate", 0.0),
    }

    print(f"\nSending to groq:\n{json.dumps(summary, indent=2)}")

    prompt = f"""
You are analyzing gameplay data from a top-down shooter game.

Enemy types:
0 — Scout: paper-thin, fastest in the game, rapid chip damage
1 — Tank: wall of HP, barely moves, each shot is a serious threat
2 — Skirmisher: the baseline enemy, nothing extreme
3 — Glass Cannon: dies fast, moves fast, hits harder than most
4 — Bruiser: tanky, fires constantly, war of attrition
5 — Assassin: fragile, fast, closes gap, mid damage

Field guide:
- avg_center_dist: 0=always center, 1=always corner
- avg_edge_dist: low=hugs walls, high=stays away from edges
- avg_displacement: low=barely moves, high=very mobile
- dodge_ratio: fraction of frames with incoming projectiles (how much pressure player faces)
- evasion_rate: fraction of tracked projectiles the player successfully avoided (0=never dodges, 1=perfect)
- avg_frames_since_shot: low=fires constantly, high=fires rarely
- enemy_type_engagement: which enemy types the player most often faces/targets
- avg_damage_taken: average health lost per damage frame (negative = taking hits)
- level_up_choices: how many times each upgrade was picked

The "level_up_choices" field shows how many times the player picked each upgrade.
Rank them from most to least chosen for "level_up_priority". If all are 0, infer from playstyle.

Return ONLY a valid JSON object with these exact fields:
- level_up_priority: ordered list most to least chosen, e.g. ["Damage", "Speed", "Heal", "Max Health", "Health Regen"]
- playstyle: "aggressive", "defensive", or "random"
- aggression_score: float 0.0 to 1.0
- accuracy_rating: "poor", "average", "good", or "excellent"
- preferred_range: "close", "medium", or "far"
- weakness: one sentence
- enemy_strategy: "flank", "rush", or "surround"
- summary: one sentence + guess of users personality

Data:
{json.dumps(summary)}

Return ONLY the JSON. No explanation, no markdown, no backticks.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        text = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        text = text.strip()

        profile = json.loads(text)

        print("\n--- PLAYER PROFILE ---")
        print(json.dumps(profile, indent=2))
        print("----------------------\n")

        print("========================================")
        print(f"  PLAYSTYLE OVERVIEW: {profile_name}")
        print("========================================")
        print(f"  Style      : {profile.get('playstyle', '?').upper()}")
        print(f"  Aggression : {profile.get('aggression_score', '?')} / 1.0")
        print(f"  Accuracy   : {profile.get('accuracy_rating', '?').upper()}")
        print(f"  Range Pref : {profile.get('preferred_range', '?').upper()}")
        print(f"  Enemy Tac  : {profile.get('enemy_strategy', '?').upper()}")
        print(f"  Weakness   : {profile.get('weakness', '?')}")
        print(f"  Upgrade Pri: {', '.join(profile.get('level_up_priority', []))}")
        print(f"  Summary    : {profile.get('summary', '?')}")
        print("========================================\n")

        save_dir = os.path.join(BASE_DIR, "replays", profile_name)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "profile.json")

        if os.path.exists(save_path):
            with open(save_path) as f:
                old = json.load(f)
            profile = merge_profiles(old, profile)
        with open(save_path, "w") as f:
            json.dump(profile, f, indent=2)

        print(f"Profile saved to: {save_path}")
        return profile

    except json.JSONDecodeError as e:
        print(f"Failed to parse groq response as JSON: {e}")
        print(f"Raw response was:\n{response.text}")
        return None
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None
