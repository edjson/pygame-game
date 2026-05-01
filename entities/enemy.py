import pygame
import itertools
import random
import math
from entities.projections import Projectile
from settings import (screen_height, screen_width, margin, bar_h, bar_w, color_health_bar,
                      color_health_bg, projectile_speeds, enemy_projectile_color)
from ai.dqn_enemy import build_state
import os
from ai.dqn_enemy import DQNagent
from entities.enemy_list import types, spriteCache

enemies = []

_id_counter = itertools.count()

_agent   = None
_profile = None


def init_agent(profile=None):
    global _agent, _profile
    _profile     = profile
    _agent       = DQNagent()
    BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    weights_path = os.path.join(BASE_DIR, "ai", "weights", "weights.pt")
    if os.path.exists(weights_path):
        _agent.load(weights_path)
        print(f"[Enemy] DQN weights loaded from {weights_path}")
    else:
        print(f"[Enemy] No weights found at {weights_path} — using random policy")


def update_profile(profile: dict):
    """Replace the module-level profile used for state-building and spawn scaling."""
    global _profile
    _profile = profile


moves = [
    ( 0,  0),  # 0 stay
    ( 0, -1),  # 1 N
    ( 1, -1),  # 2 NE
    ( 1,  0),  # 3 E
    ( 1,  1),  # 4 SE
    ( 0,  1),  # 5 S
    (-1,  1),  # 6 SW
    (-1,  0),  # 7 W
    (-1, -1),  # 8 NW
]


class Enemy:
    """A single enemy entity driven by the DQN agent, with a rule-based fallback."""

    def __init__(self, x, y, type_index):
        """Spawn at (x, y) with stats from types[type_index], apply profile scaling, and register globally."""
        self.enemy_id        = next(_id_counter)
        unit                 = types[type_index]
        self.pos             = pygame.Vector2(x, y)
        self.vel             = pygame.Vector2(0, 0)
        self.name            = unit["name"]
        self.color           = unit["color"]
        self.health          = unit["hp"]
        self.maxhealth       = unit["hp"]
        self.damage          = unit["damage"]
        self.speed           = unit["speed"]
        self.radius          = unit["radius"]
        self.proj_radius     = unit["proj_radius"] * 3
        self.attack_cooldown = 0
        self.fire_rate       = unit["fire_rate"]
        self.fire_cooldown   = 0
        self.attack_rate     = 1
        self.xp              = unit["xp"]
        self._apply_profile_scaling()
        enemies.append(self)
        # sprites
        self.image = None
        self.rect = None
        if os.environ.get("SDL_VIDEODRIVER") != "dummy":
            if unit["name"] not in spriteCache:
                spriteCache[unit["name"]] = pygame.image.load(unit["sprite"]).convert_alpha()
            originalImage = spriteCache[unit["name"]]
            diameter = self.radius * 2
            self.image = pygame.transform.scale(originalImage, (diameter, diameter))
            self.rect = self.image.get_rect(center=(self.pos.x, self.pos.y))

    def can_fire(self):
        """Return True if the fire cooldown has elapsed."""
        return self.fire_cooldown <= 0

    def _apply_profile_scaling(self):
        """Scale speed, damage, and fire rate from live profile multipliers if available."""
        if _profile is None:
            return
        self.speed     *= _profile.get("speed_multiplier",    1.0)
        self.damage    *= _profile.get("damage_multiplier",   1.0)
        self.fire_rate *= (1.0 / max(_profile.get("fire_rate_multiplier", 1.0), 0.1))

    def update(self, dt, player, player_projectiles=None, enemy_projectiles=None):
        """Tick movement and firing via DQN action, falling back to rule_based_update if no agent exists."""
        global _agent, _profile
        if enemy_projectiles is None:
            enemy_projectiles = []

        if _agent is None:
            self.rule_based_update(dt, player.pos, enemy_projectiles)
            return

        allies             = [e for e in enemies if e is not self and e.health > 0]
        player_projectiles = player_projectiles or []
        state              = build_state(
            enemy      = self,
            player     = player,
            projectile = player_projectiles,
            allies     = allies,
            profile    = _profile,
        )

        action, lead_scale = _agent.select_action(state, self.enemy_id)

        dx, dy = moves[action]
        length = math.hypot(dx, dy)
        if length > 0:
            dx /= length
            dy /= length

        self.vel    = pygame.Vector2(dx, dy) * self.speed
        self.pos.x += dx * self.speed * dt
        self.pos.y += dy * self.speed * dt
        self.pos.x  = max(self.radius, min(screen_width  - self.radius, self.pos.x))
        self.pos.y  = max(self.radius, min(screen_height - self.radius, self.pos.y))

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt

        if self.fire_cooldown <= 0:
            self.fire_cooldown = self.fire_rate
            distance      = self.pos.distance_to(player.pos)
            lead_time     = lead_scale * (distance / projectile_speeds)
            predicted_pos = pygame.Vector2(player.pos) + pygame.Vector2(player.vel) * lead_time
            direction     = predicted_pos - self.pos
            if direction.length() > 0:
                direction = direction.normalize()
                enemy_projectiles.append(
                    Projectile(
                        self.pos.x, self.pos.y,
                        direction.x, direction.y,
                        self.proj_radius, self.damage, "assets/sprites/EnemyBullet.png"
                    )
                )

    def rule_based_update(self, dt, target_pos, enemy_projectiles=None):
        """Chase and shoot the player directly, with no learned behaviour."""
        enemy_projectiles = enemy_projectiles or []
        direction = pygame.Vector2(target_pos) - self.pos
        if direction.length() > 0:
            direction  = direction.normalize()
            self.vel   = direction * self.speed
            self.pos  += direction * self.speed * dt
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt
        if self.fire_cooldown <= 0:
            self.fire_cooldown = self.fire_rate
            direction = pygame.Vector2(target_pos) - self.pos
            if direction.length() > 0:
                direction = direction.normalize()
                enemy_projectiles.append(Projectile(
                    self.pos.x, self.pos.y,
                    direction.x, direction.y,
                    self.proj_radius, self.damage, "assets/sprites/EnemyBullet.png"
                ))

    def take_damage(self, damage):
        """Subtract damage from health and return True if the enemy is now dead."""
        self.health -= damage
        return self.health <= 0

    def draw(self, screen):
        """Draw the enemy circle and a health bar above it."""
        # pygame.draw.circle(screen, self.color, self.pos, self.radius)
        if self.image is None:
            return
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        screen.blit(self.image, self.rect)

        bar_x    = self.pos.x - bar_w // 2
        bar_y    = self.pos.y - self.radius - 10
        pygame.draw.rect(screen, color_health_bg,  (bar_x, bar_y, bar_w, bar_h))
        hp_ratio = max(0, self.health / self.maxhealth)
        pygame.draw.rect(screen, color_health_bar, (bar_x, bar_y, bar_w * hp_ratio, bar_h))


def spawn_enemies(count):
    """Spawn count enemies of random type at random screen edges."""
    m = margin
    for _ in range(count):
        side       = random.choice(["top", "bottom", "left", "right"])
        type_index = random.randint(0, len(types) - 2)
        if side == "top":
            x = random.randint(m, screen_width - m);  y = m
        elif side == "bottom":
            x = random.randint(m, screen_width - m);  y = screen_height - m
        elif side == "left":
            x = m;  y = random.randint(m, screen_height - m)
        else:
            x = screen_width - m;  y = random.randint(m, screen_height - m)
        Enemy(x, y, type_index)


def spawn_tutorial_unit():
    """Spawn the fixed tutorial enemy (type 6) at a random edge position."""
    m    = margin
    side = random.choice(["top", "bottom", "left", "right"])
    if side == "top":
        x = random.randint(m, screen_width - m);  y = m
    elif side == "bottom":
        x = random.randint(m, screen_width - m);  y = screen_height - m
    elif side == "left":
        x = m;  y = random.randint(m, screen_height - m)
    else:
        x = screen_width - m;  y = random.randint(m, screen_height - m)
    Enemy(x, y, 6)