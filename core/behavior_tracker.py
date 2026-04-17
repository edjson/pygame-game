"""
core/behavior_tracker.py

Computes a live behavior profile from game.behavior_log after each stage.
Keys match exactly what build_state() and compute_rewards() expect in dqn_enemy.py.
"""

def compute_live_profile(behavior_log: list, stage: int) -> dict:
    """
    Derives a live profile from accumulated frame data.
    Called after stage >= ADAPT_FROM_STAGE in game.py.

    Keys produced:
      aggression_score   — used by build_state + compute_rewards
      avg_displacement   — used by build_state
      avg_center_dist    — used by build_state
      evasion_rate       — used by build_state
      accuracy           — used by build_state
      session_count      — used by build_state
      enemy_strategy     — used by compute_rewards (rush/flank/surround)
      playstyle          — informational
      preferred_range    — informational
      fire_rate          — used by EventHandler.set_fire_rate()
      speed_multiplier   — applied at enemy spawn in enemy.py
      damage_multiplier  — applied at enemy spawn in enemy.py
      fire_rate_multiplier — applied at enemy spawn in enemy.py
    """
    if not behavior_log:
        return {}

    total = len(behavior_log)
    last  = behavior_log[-1]

    # ── accuracy ──────────────────────────────────────────────────────────────
    shots_fired = last.get("shots_fired", 1)
    shots_hit   = last.get("shots_hit",   0)
    accuracy    = round(shots_hit / max(shots_fired, 1), 3)

    # ── aggression: shot density relative to frames ───────────────────────────
    aggression_score = round(min(shots_fired / max(total, 1), 1.0), 3)

    # ── avg_displacement (px per sample frame, matches llm.py key name) ───────
    avg_displacement = round(
        sum(f.get("displacement", 0) for f in behavior_log) / total, 2
    )

    # ── avg_center_dist (0=center, 1=corner — matches llm.py + build_state) ──
    avg_center_dist = round(
        sum(f.get("center_dist", 0.5) for f in behavior_log) / total, 3
    )

    # ── evasion rate ──────────────────────────────────────────────────────────
    evasion_rate = last.get("evasion_rate", 0.0)

    # ── session_count: treat each stage-3+ adaptation as one session tick ─────
    session_count = max(1, stage - 2)

    # ── preferred range ───────────────────────────────────────────────────────
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

    # ── playstyle ─────────────────────────────────────────────────────────────
    mobility = avg_displacement / 5.0   # normalise ~0-1 (300px/s at 60fps ≈ 5px/frame)
    if aggression_score > 0.6 and mobility > 0.5:
        playstyle = "aggressive"
    elif evasion_rate > 0.6 or mobility > 0.7:
        playstyle = "defensive"
    else:
        playstyle = "random"

    # ── enemy strategy to counter the player ─────────────────────────────────
    if playstyle == "aggressive":
        enemy_strategy = "surround"   # aggressive player → cut off escape
    elif playstyle == "defensive":
        enemy_strategy = "rush"       # defensive/mobile  → close gap fast
    else:
        enemy_strategy = "flank"

    # ── adapted player fire_rate (for EventHandler) ───────────────────────────
    # More accurate player → slightly slower enemy fire (give a chance)
    # Less accurate        → ramp up pressure
    adapted_fire_rate = round(max(0.1, min(1.0, 0.5 + (0.5 - accuracy))), 3)

    # ── enemy spawn multipliers ───────────────────────────────────────────────
    speed_multiplier        = round(1.0 + min(mobility, 1.0) * 0.4,           3)  # up to 1.4×
    damage_multiplier       = round(1.0 + aggression_score * 0.3,             3)  # up to 1.3×
    fire_rate_multiplier    = round(1.0 + (1.0 - evasion_rate) * 0.5,        3)  # bad evader → more fire

    profile = {
        # ── build_state keys (must match exactly) ────────────────────────────
        "aggression_score":      aggression_score,
        "avg_displacement":      avg_displacement,
        "avg_center_dist":       avg_center_dist,
        "evasion_rate":          evasion_rate,
        "accuracy":              accuracy,
        "session_count":         session_count,
        # ── compute_rewards key ──────────────────────────────────────────────
        "enemy_strategy":        enemy_strategy,
        # ── informational ────────────────────────────────────────────────────
        "playstyle":             playstyle,
        "preferred_range":       preferred_range,
        # ── EventHandler fire rate ────────────────────────────────────────────
        "fire_rate":             adapted_fire_rate,
        # ── enemy spawn scaling (applied in enemy._apply_profile_scaling) ─────
        "speed_multiplier":      speed_multiplier,
        "damage_multiplier":     damage_multiplier,
        "fire_rate_multiplier":  fire_rate_multiplier,
    }

    print(
        f"[BehaviorTracker] stage={stage} | playstyle={playstyle} | "
        f"aggression={aggression_score} accuracy={accuracy} "
        f"evasion={evasion_rate} strategy={enemy_strategy} | "
        f"spd×{speed_multiplier} dmg×{damage_multiplier} fr×{fire_rate_multiplier}"
    )

    return profile