def compute_live_profile(behavior_log: list, stage: int) -> dict:
    """Derives a live profile from accumulated frame data. Called after stage >= ADAPT_FROM_STAGE in game.py."""
    if not behavior_log:
        return {}

    total = len(behavior_log)
    last  = behavior_log[-1]

    shots_fired      = last.get("shots_fired", 1)
    shots_hit        = last.get("shots_hit", 0)
    accuracy         = round(shots_hit / max(shots_fired, 1), 3)
    aggression_score = round(min(shots_fired / max(total, 1), 1.0), 3)
    avg_displacement = round(sum(f.get("displacement", 0) for f in behavior_log) / total, 2)
    avg_center_dist  = round(sum(f.get("center_dist", 0.5) for f in behavior_log) / total, 3)
    evasion_rate     = last.get("evasion_rate", 0.0)

    range_samples = [
        f["nearest_enemy"]["dist"]
        for f in behavior_log
        if f.get("nearest_enemy") and f["nearest_enemy"].get("dist") is not None
    ]
    avg_range = sum(range_samples) / max(len(range_samples), 1)
    if avg_range < 150:
        preferred_range = "close"
    elif avg_range < 300:
        preferred_range = "medium"
    else:
        preferred_range = "far"

    mobility = avg_displacement / 5.0
    if aggression_score > 0.6 and mobility > 0.5:
        playstyle = "aggressive"
    elif evasion_rate > 0.6 or mobility > 0.7:
        playstyle = "defensive"
    else:
        playstyle = "random"

    enemy_strategy = {"aggressive": "surround", "defensive": "rush"}.get(playstyle, "flank")

    adapted_fire_rate    = round(max(0.1, min(1.0, 0.5 + (0.5 - accuracy))), 3)
    speed_multiplier     = round(1.0 + min(mobility, 1.0) * 0.4, 3)
    damage_multiplier    = round(1.0 + aggression_score * 0.3, 3)
    fire_rate_multiplier = round(1.0 + (1.0 - evasion_rate) * 0.5, 3)

    profile = {
        "aggression_score":     aggression_score,
        "avg_displacement":     avg_displacement,
        "avg_center_dist":      avg_center_dist,
        "evasion_rate":         evasion_rate,
        "accuracy":             accuracy,
        "enemy_strategy":       enemy_strategy,
        "playstyle":            playstyle,
        "preferred_range":      preferred_range,
        "fire_rate":            adapted_fire_rate,
        "speed_multiplier":     speed_multiplier,
        "damage_multiplier":    damage_multiplier,
        "fire_rate_multiplier": fire_rate_multiplier,
    }

    print(
        f"[BehaviorTracker] stage={stage} | playstyle={playstyle} | "
        f"aggression={aggression_score} accuracy={accuracy} "
        f"evasion={evasion_rate} strategy={enemy_strategy} | "
        f"spd×{speed_multiplier} dmg×{damage_multiplier} fr×{fire_rate_multiplier}"
    )

    return profile