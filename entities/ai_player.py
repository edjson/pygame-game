import pygame
import random
import json
import os
from entities.player import Player
from entities.enemy import enemies
from settings import screen_height, screen_width, cy, cx, detection_radius, margin
import settings

def apply_buff(player, buff_name):
    """Apply buffs to ai player."""
    if buff_name == "Speed":
        player.speed += 5
    elif buff_name == "Max Health":
        player.maxhealth += 5
    elif buff_name == "Health Regen":
        player.regen += 10
    elif buff_name == "Damage":
        player.damage += 5
    elif buff_name == "Heal":
        player.health = player.maxhealth

all_buffs = ["Speed", "Max Health", "Health Regen", "Damage", "Heal"]


def load_profile(profile_name):
    """Load profile."""
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(BASE_DIR, "replays", profile_name, "profile.json")
    if not os.path.exists(path):
        print(f"[AIPlayer] No profile found at {path}, using defaults")
        return None
    with open(path) as f:
        return json.load(f)


def build_weights(profile):
    """Build weights from buff priority list."""
    if not profile:
        return {b: 1 for b in all_buffs}
    priority = profile.get("level_up_priority", all_buffs)
    for b in all_buffs:
        if b not in priority:
            priority.append(b)
    n = len(priority)
    return {buff: (n - i) for i, buff in enumerate(priority)}


class AIPlayer(Player):
    def __init__(self, profile_name=None):
        super().__init__()

        self.fire_callback    = None
        self._fire_timer      = 0.0
        self.priority_type    = None
        self._enemy_proj_list = []   # injected by SimPlayer before each update

        profile = load_profile(profile_name) if profile_name else None
        self.profile = profile
        self.upgrade_weights = build_weights(profile)
        self.apply_profile(profile)
        print(f"[AIPlayer] Profile loaded: {profile_name}")
        print(f"[AIPlayer] Weights:       {self.upgrade_weights}")
        print(f"[AIPlayer] Range:         {self.preferred_range}")
        print(f"[AIPlayer] Aggression:    {self.aggression_score}")
        print(f"[AIPlayer] Fire rate:     {self.fire_rate}")
        print(f"[AIPlayer] Aim noise:     {self.aim_noise}")
        print(f"[AIPlayer] Target mode:   {self.target_mode}")
        print(f"[AIPlayer] Evasion radius:{self.dodge_radius}")
        print(f"[AIPlayer] Center bias:   {self.center_bias}")
        print(f"[AIPlayer] Mobility:      {self.mobility}")

    def apply_profile(self, profile):
        """Apply profile stats, or defaults if missing."""
        if not profile:
            self.last_vel             = pygame.Vector2(0, 0)
            self.preferred_range      = 200
            self.aggression_score     = 0.5
            self.aim_noise            = 30
            self.fire_rate            = 0.4
            self.retreat_threshold    = 0.5
            self.target_mode          = "rush"
            self.dodge_radius         = detection_radius
            self.center_bias          = 0.5
            self.mobility             = 1.0
            self.evasion_aggression   = 0.5
            self._target_switch_timer = 0.0
            self._current_target      = None
            return

        accuracy_defaults = {
            "poor":      (60, 0.6),
            "average":   (30, 0.4),
            "good":      (12, 0.25),
            "excellent": (2,  0.15),
        }
        playstyle_defaults = {
            "aggressive": 0.2,
            "defensive":  0.5,
            "random":     random.uniform(0.2, 0.6),
        }
        range_defaults = {"close": 100, "medium": 200, "far": 350}

        self.preferred_range           = range_defaults.get(profile.get("preferred_range", "medium"), 200)
        self.aggression_score          = profile.get("aggression_score", 0.5)
        self.aim_noise, self.fire_rate = accuracy_defaults.get(profile.get("accuracy_rating", "average"), (30, 0.4))
        self.retreat_threshold         = playstyle_defaults.get(profile.get("playstyle", "defensive"), 0.5)
        self.target_mode               = profile.get("enemy_strategy", "rush")
        self._target_switch_timer      = 0.0
        self._current_target           = None
        evasion_rate                   = profile.get("evasion_rate", 0.5)
        self.dodge_radius              = int(80 + evasion_rate * 120)
        self.evasion_aggression        = evasion_rate
        self.center_bias               = 1.0 - profile.get("avg_center_dist", 0.5)
        self.mobility                  = min(1.5, max(1, profile.get("avg_displacement", 3.0) / 5.0))
        self.speed                     = settings.player_speed
        self.retreat_threshold         = max(0.1, self.retreat_threshold - min(0.2, abs(profile.get("avg_damage_taken", -2.0)) / 100.0))
        self.last_vel                  = pygame.Vector2(0, 0)
        engagement                     = profile.get("enemy_type_engagement", {})
        self.priority_type             = max(engagement, key=engagement.get) if engagement else None

    def set_fire_callback(self, callback):
        self.fire_callback = callback

    def pick_upgrade(self):
        """Use weights to pick and apply a buff."""
        buffs   = list(self.upgrade_weights.keys())
        weights = [self.upgrade_weights[b] for b in buffs]
        chosen  = random.choices(buffs, weights=weights, k=1)[0]
        apply_buff(self, chosen)
        return chosen

    def select_target(self, dt):
        """Select target based on strategy (rush, flank, surround)."""
        alive = [e for e in enemies if e.health > 0]
        if not alive:
            return None

        if self.priority_type:
            priority = [e for e in alive if e.name == self.priority_type]
            if priority:
                alive = priority

        if self.target_mode == "rush":
            return min(alive, key=lambda e: self.pos.distance_to(e.pos))

        elif self.target_mode == "flank":
            if self.last_vel.length() > 0:
                forward = self.last_vel.normalize()
                def flank_score(e):
                    diff = e.pos - self.pos
                    if diff.length() == 0:
                        return float("inf")
                    return abs(forward.dot(diff.normalize()))
                return min(alive, key=flank_score)
            return min(alive, key=lambda e: self.pos.distance_to(e.pos))

        elif self.target_mode == "surround":
            self._target_switch_timer -= dt
            if self._target_switch_timer <= 0 or self._current_target not in alive:
                self._current_target      = random.choice(alive)
                self._target_switch_timer = 2.0
            return self._current_target

        return min(alive, key=lambda e: self.pos.distance_to(e.pos))

    def dodge_projectiles(self):
        """Compute dodge vector from incoming projectiles."""
        dodge = pygame.Vector2(0, 0)

        ep_list = self._enemy_proj_list if self._enemy_proj_list else []

        for ep in ep_list:
            dist = self.pos.distance_to(ep.pos)
            if 0 < dist < self.dodge_radius:
                away           = (self.pos - ep.pos).normalize()
                proximity_scale = (self.dodge_radius / dist) ** 2
                proj_vel       = pygame.Vector2(ep.velocity.x, ep.velocity.y)

                if proj_vel.length() > 0:
                    toward_player    = (self.pos - ep.pos).normalize()
                    alignment        = proj_vel.normalize().dot(toward_player)
                    threat_multiplier = max(0.2, alignment)
                else:
                    threat_multiplier = 1.0

                if proj_vel.length() > 0:
                    perp  = pygame.Vector2(-proj_vel.normalize().y, proj_vel.normalize().x)
                    alive = [e for e in enemies if e.health > 0]
                    if alive:
                        avg_enemy = pygame.Vector2(
                            sum(e.pos.x for e in alive) / len(alive),
                            sum(e.pos.y for e in alive) / len(alive)
                        )
                        away_from_enemies = self.pos - avg_enemy
                        if away_from_enemies.length() > 0:
                            away_from_enemies = away_from_enemies.normalize()
                        if perp.dot(away_from_enemies) > 0:
                            dodge_dir = (away * 0.4 + perp * 0.6).normalize()
                        else:
                            dodge_dir = (away * 0.4 + (-perp) * 0.6).normalize()
                    else:
                        dodge_dir = away
                else:
                    dodge_dir = away

                strength = self.evasion_aggression * proximity_scale * threat_multiplier
                dodge   += dodge_dir * min(strength, 3.0)

        proj_count = sum(1 for ep in ep_list
                         if self.pos.distance_to(ep.pos) < self.dodge_radius)
        if proj_count > 1:
            dodge *= min(1.5, 1.0 + proj_count * 0.15)

        if dodge.length() > 0:
            dodge = dodge.normalize()

        wall_strength = 1.5 + self.center_bias
        if self.pos.x < margin:
            dodge.x += wall_strength * (margin - self.pos.x) / margin
        if self.pos.x > screen_width - margin:
            dodge.x -= wall_strength * (self.pos.x - (screen_width - margin)) / margin
        if self.pos.y < margin:
            dodge.y += wall_strength * (margin - self.pos.y) / margin
        if self.pos.y > screen_height - margin:
            dodge.y -= wall_strength * (self.pos.y - (screen_height - margin)) / margin

        if dodge.length() > 1:
            dodge = dodge.normalize()
        return dodge

    def input(self, dt):
        """Orchestrate AI player behavior."""
        self.last_vel    = self.vel
        self.vel         = pygame.Vector2(0, 0)
        self._fire_timer = max(0.0, self._fire_timer - dt)
        target           = self.select_target(dt)
        dodge_vec        = self.dodge_projectiles()
        health_ratio     = self.health / self.maxhealth
        dynamic_range    = self.preferred_range * (1.0 - self.aggression_score * health_ratio * 0.5)
        is_retreating    = health_ratio < self.retreat_threshold

        if dodge_vec.length() > 0:
            self.vel = dodge_vec.normalize()
        elif is_retreating and target:
            away = self.pos - target.pos
            if away.length() > 0:
                self.vel = away.normalize()
        elif target:
            dist      = self.pos.distance_to(target.pos)
            direction = target.pos - self.pos
            if dist > dynamic_range:
                self.vel = direction.normalize()
            elif dist < dynamic_range - 40:
                self.vel = -direction.normalize()
        else:
            to_center = pygame.Vector2(cx, cy) - self.pos
            if to_center.length() > 5 and self.center_bias > 0.3:
                self.vel = to_center.normalize()

        if target and self.fire_callback and self._fire_timer <= 0:
            noise_x = random.uniform(-self.aim_noise, self.aim_noise)
            noise_y = random.uniform(-self.aim_noise, self.aim_noise)
            self.fire_callback(self.pos, (target.pos.x + noise_x, target.pos.y + noise_y))
            self._fire_timer = self.fire_rate

        if self.vel.length() > 0:
            self.vel = self.vel.normalize() * self.speed

        self.pos.x = max(self.radius, min(screen_width  - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(screen_height - self.radius, self.pos.y))