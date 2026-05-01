import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import math
import random
import pygame
import numpy as np
import json
import entities.enemy as _em
from settings import (screen_width, screen_height, player_radius,
                      player_next, player_xpRate, margin,
                      enemies_count_rate, spawn_decay_rate, min_spawn_delay,
                      current_spawn_delay, projectile_speeds)
from entities.enemy import Enemy, enemies as _global_enemies
from ai.dqn_enemy import build_state, compute_rewards, total_actions as ACTION_DIM
from entities.ai_player import AIPlayer, apply_buff, all_buffs


class SimProjectile:
    """Lightweight headless projectile that moves each tick and reports when it leaves the screen."""
    def __init__(self, x, y, dx, dy, radius, damage, source_enemy=None):
        self.pos          = pygame.Vector2(x, y)
        self.velocity     = pygame.Vector2(dx, dy) * projectile_speeds
        self.radius       = radius
        self.damage       = damage
        self.source_enemy = source_enemy

    def update(self, dt):
        """Advance position by velocity * dt."""
        self.pos += self.velocity * dt

    def out_of_bounds(self):
        """Return True if the projectile has fully exited the screen rectangle."""
        return (self.pos.x < -self.radius or self.pos.x > screen_width + self.radius or
                self.pos.y < -self.radius or self.pos.y > screen_height + self.radius)


class SimPlayer(AIPlayer):
    """Wraps AIPlayer for headless simulation — profile-driven dodge, targeting, and firing logic matches the real game so the DQN trains against its actual opponent."""
    def __init__(self, profile_name=None):
        """Initialise AIPlayer silently, then wire up the headless fire callback."""
        import sys, io
        _devnull = io.StringIO()
        _stdout, sys.stdout = sys.stdout, _devnull
        try:
            super().__init__(profile_name=profile_name)
        finally:
            sys.stdout = _stdout
        self._sim_proj_list: list = []
        self.set_fire_callback(self._fire)
        self.alive = True
        self.xp    = 0
        self.level = 1
        self.next  = player_next
        self.rate  = player_xpRate

    def _fire(self, from_pos, to_pos):
        """Append a SimProjectile to the shared list instead of drawing to screen."""
        d = pygame.Vector2(to_pos) - pygame.Vector2(from_pos)
        if d.length() > 0:
            d = d.normalize()
            self._sim_proj_list.append(
                SimProjectile(from_pos.x, from_pos.y, d.x, d.y,
                              player_radius, self.damage)
            )

    def update(self, dt, sim_enemies, enemy_projectiles, player_projectiles):
        """Drive the AIPlayer input() loop headlessly, temporarily swapping the global enemy list."""
        if not self.alive:
            return

        _orig_enemies = _em.enemies[:]
        try:
            _em.enemies[:]        = sim_enemies
            self._sim_proj_list   = player_projectiles
            self._enemy_proj_list = enemy_projectiles 
            self.input(dt)
            self.pos  += self.vel * dt
            self.pos.x = max(self.radius, min(screen_width  - self.radius, self.pos.x))
            self.pos.y = max(self.radius, min(screen_height - self.radius, self.pos.y))
        finally:
            _em.enemies[:] = _orig_enemies


def spawn_edge(margin):
    """Return a random (x, y) position on one of the four screen edges, inset by margin."""
    side = random.choice(["top", "bottom", "left", "right"])
    m    = margin
    if side == "top":    return random.randint(m, screen_width-m),  m
    if side == "bottom": return random.randint(m, screen_width-m),  screen_height-m
    if side == "left":   return m, random.randint(m, screen_height-m)
    if side == "right":  return screen_width-m, random.randint(m, screen_height-m)


class Simulation:
    """Self-contained headless environment that runs the game loop and exposes a step() RL interface."""

    def __init__(self, n_enemies: int = 3, max_steps: int = 3000, profile_name: str | None = None):
        """Store episode config; call reset() before the first step."""
        self.n_enemies    = n_enemies
        self.max_steps    = max_steps
        self.profile_name = profile_name
        self.step_count   = 0

    def reset(self):
        """Rebuild player, enemies, and projectile lists; return initial per-enemy state vectors."""
        profile_path = os.path.join("replays", self.profile_name, "profile.json") if self.profile_name else None
        if profile_path and os.path.exists(profile_path):
            with open(profile_path) as f:
                self.profile = json.load(f)
        else:
            self.profile = None

        _global_enemies.clear()
        self.step_count          = 0
        self.player_proj         = []
        self.enemy_proj          = []
        self.player              = SimPlayer(profile_name=self.profile_name)
        self.player._sim_proj_list = self.player_proj
        self.prev_player_hp      = self.player.health
        self.current_stage       = 1
        self.spawn_queue         = 0
        self.spawn_timer         = 0.0
        self.spawn_total         = 1
        self.current_spawn_delay = current_spawn_delay

        self._spawn_enemies(self.n_enemies)

        self.player.pos = pygame.Vector2(
            random.randint(200, screen_width  - 200),
            random.randint(200, screen_height - 200)
        )

        for e in _global_enemies:
            e.hit_this_step = False
            e.hit_landed    = False

        return self._get_states()

    def enemies(self):
        """Return the live global enemy list."""
        return _global_enemies

    def _spawn_enemies(self, count):
        """Spawn count enemies of random type at random edge positions."""
        for _ in range(count):
            type_index      = random.randint(0, 5)
            x, y            = spawn_edge(margin)
            e               = Enemy(x, y, type_index)
            e.hit_this_step = False
            e.hit_landed    = False

    def _level_up_player(self):
        """Apply a profile-driven (or random fallback) upgrade when the player levels up."""
        upgrade = self.player.pick_upgrade() if hasattr(self.player, "pick_upgrade") else random.choice(all_buffs)
        apply_buff(self.player, upgrade)

    def step(self, actions: list, dt: float = 1 / 60.0):
        self.step_count += 1

        alive_enemies = [e for e in _global_enemies if e.health > 0]

        for e in _global_enemies:
            e.hit_this_step = False
            e.hit_landed    = False

        for i, enemy in enumerate(_global_enemies):
            if enemy.health <= 0:
                continue
            if i < len(actions):
                entry = actions[i]
                if isinstance(entry, tuple):
                    action, lead_scale = entry
                else:
                    action     = entry
                    lead_scale = 0.5
            else:
                action     = 0
                lead_scale = 0.5

            from ai.dqn_enemy import movement as moves
            dx, dy = moves[action]
            length = math.hypot(dx, dy)
            if length > 0:
                dx /= length
                dy /= length
            enemy.vel    = pygame.Vector2(dx, dy) * enemy.speed
            enemy.pos.x += dx * enemy.speed * dt
            enemy.pos.y += dy * enemy.speed * dt
            enemy.pos.x  = max(enemy.radius, min(screen_width  - enemy.radius, enemy.pos.x))
            enemy.pos.y  = max(enemy.radius, min(screen_height - enemy.radius, enemy.pos.y))

            if enemy.attack_cooldown > 0:
                enemy.attack_cooldown -= dt
            if enemy.fire_cooldown > 0:
                enemy.fire_cooldown -= dt

            if enemy.can_fire():
                enemy.fire_cooldown = enemy.fire_rate
                distance      = enemy.pos.distance_to(self.player.pos)
                lead_time     = lead_scale * (distance / projectile_speeds)
                predicted_pos = pygame.Vector2(self.player.pos) + pygame.Vector2(self.player.vel) * lead_time
                d = predicted_pos - enemy.pos
                if d.length() > 0:
                    d = d.normalize()
                    self.enemy_proj.append(
                        SimProjectile(
                            enemy.pos.x, enemy.pos.y,
                            d.x, d.y,
                            radius       = enemy.proj_radius,
                            damage       = enemy.damage,
                            source_enemy = enemy
                        )
                    )

        self.player._sim_proj_list = self.player_proj
        self.player.update(dt, _global_enemies, self.enemy_proj, self.player_proj)

        killed = set()
        for i in self.player_proj[:]:
            i.update(dt)
            if i.out_of_bounds():
                self.player_proj.remove(i)
                continue
            for enemy in alive_enemies:
                if enemy.pos.distance_to(i.pos) <= i.radius + enemy.radius:
                    enemy.health -= i.damage
                    enemy.hit_this_step = True
                    if i in self.player_proj:
                        self.player_proj.remove(i)
                    if enemy.health <= 0:
                        enemy.health = 0
                        killed.add(enemy.enemy_id)
                        self.player.xp += enemy.xp
                        if self.player.xp >= self.player.next:
                            self.player.xp  -= self.player.next
                            self.player.next  = round(self.player.next * self.player.rate)
                            self.player.level += 1
                            self._level_up_player()
                    break

        for ep in self.enemy_proj[:]:
            ep.update(dt)
            if ep.out_of_bounds():
                self.enemy_proj.remove(ep)
                continue
            if self.player.pos.distance_to(ep.pos) <= ep.radius + self.player.radius:
                self.player.health -= ep.damage
                if ep.source_enemy is not None:
                    ep.source_enemy.hit_landed = True
                self.enemy_proj.remove(ep)

        for enemy in alive_enemies:
            d = enemy.pos.distance_to(self.player.pos)
            if d <= enemy.radius + self.player.radius and d > 0:
                direction        = (self.player.pos - enemy.pos).normalize()
                overlap          = (enemy.radius + self.player.radius) - d
                self.player.pos += direction * overlap
                self.player.health -= enemy.damage * dt

        # Enemy separation
        living = [e for e in _global_enemies if e.health > 0]
        for _ in range(5):
            for j in range(len(living)):
                for k in range(j + 1, len(living)):
                    a, b     = living[j], living[k]
                    dist     = a.pos.distance_to(b.pos)
                    min_dist = a.radius + b.radius
                    if 0 < dist < min_dist:
                        direction = (b.pos - a.pos).normalize()
                        overlap   = (min_dist - dist) / 2
                        a.pos    -= direction * overlap * 0.2
                        b.pos    += direction * overlap * 0.2

        if self.player.health <= 0:
            self.player.alive = False

        # Stage progression
        alive_count = sum(1 for e in _global_enemies if e.health > 0)
        if alive_count == 0 and self.spawn_queue == 0:
            self.current_stage      += 1
            total                    = round(self.current_stage * enemies_count_rate)
            self.spawn_total         = total
            self._spawn_enemies(1)
            self.spawn_queue         = total - 1
            self.spawn_timer         = self.current_spawn_delay
            self.current_spawn_delay = max(min_spawn_delay,
                                           self.current_spawn_delay * spawn_decay_rate)
            self.player.health       = min(self.player.health + self.player.regen,
                                           self.player.maxhealth)
        elif self.spawn_queue > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self._spawn_enemies(1)
                self.spawn_queue -= 1
                self.spawn_timer  = self.current_spawn_delay

        curr_player_hp = max(0.0, self.player.health)

        rewards = []
        for enemy in _global_enemies:
            if enemy.health <= 0:
                rewards.append(-5.0)
                continue
            r = compute_rewards(
                enemy              = enemy,
                player             = self.player,
                allies             = [e for e in _global_enemies if e is not enemy and e.health > 0],
                prev_player_health = self.prev_player_hp,
                curr_player_health = curr_player_hp,
                hit_by_projectile  = enemy.hit_this_step,
                died               = enemy.enemy_id in killed,
                profile            = self.profile
            )
            if enemy.hit_landed:
                r += 2.0
            rewards.append(r)

        self.prev_player_hp = curr_player_hp

        episode_over = (not self.player.alive) or self.step_count >= self.max_steps
        dones        = [True if e.health <= 0 else episode_over for e in _global_enemies]

        info = {
            "player_alive":  self.player.alive,
            "player_hp":     curr_player_hp,
            "player_level":  self.player.level,
            "enemies_alive": alive_count,
            "stage":         self.current_stage,
            "step":          self.step_count,
        }

        return self._get_states(), rewards, dones, info

    def _get_states(self):
        """Build and return a state vector for every enemy slot (zeros for dead enemies)."""
        states = []
        for enemy in _global_enemies:
            if enemy.health > 0:
                allies = [e for e in _global_enemies if e is not enemy and e.health > 0]
                s = build_state(
                    enemy      = enemy,
                    player     = self.player,
                    projectile = self.player_proj,
                    allies     = allies,
                    profile    = self.player.profile
                )
            else:
                s = np.zeros(30, dtype=np.float32)
            states.append(s)
        return states


if __name__ == "__main__":
    pygame.init()
    sim     = Simulation(n_enemies=3, max_steps=300)
    states  = sim.reset()
    total_r = [0.0] * 3
    steps   = 0

    while True:
        actions = [(random.randrange(ACTION_DIM), 0.5) for _ in range(len(sim.enemies()))]
        states, rewards, dones, info = sim.step(actions)
        for i, r in enumerate(rewards):
            total_r[i] += r
        steps += 1
        if all(dones):
            break

    print(f"Sanity check passed — {steps} steps")
    print(f"Total rewards per enemy: {[round(r,2) for r in total_r]}")
    print(f"Final info: {info}")
    pygame.quit()