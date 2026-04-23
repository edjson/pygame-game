import pygame
import settings
from entities.player import Player
from entities.projections import Projectile
from settings import (screen_width, screen_height, cx, cy, warning_radius, enemies_count_rate,
                      player_projectile_radius, player_damage, player_projectile_color, adapt_from_stage)
from entities.enemy import enemies, spawn_enemies, init_agent, update_profile
from ai.llm import synthesis
from core.behavior_tracker import compute_live_profile
import json
import os
import time
import threading
from entities.enemy_list import types



class Game:
    """Core game loop: manages player, enemies, projectiles, behavior logging, and stage progression."""

    current_stage = 1

    def __init__(self, profile_name=None):
        """Initialise the agent with no profile, then reset all game state."""
        self.profile_name = profile_name
        init_agent(profile=None) 
        self.reset()
        self.train_thread = None

    def reset(self):
        """Clear all entities and counters, ready for a fresh run."""
        if self.current_stage > settings.record:
            settings.record = self.current_stage

        enemies.clear()
        self.current_stage        = 1
        self.player               = Player()
        self.player.set_fire_callback(self._fire)
        self.player_projectiles   = []
        self.enemy_projectiles    = []
        self.enemies              = enemies
        self.elapsed              = 0.0
        self.spawn_delay          = 3
        self.spawn_queue          = 0
        self.spawn_timer          = 0.0
        self.spawn_total          = 1
        self.behavior_log         = []
        self.last_action          = "idle"
        self.shots_fired          = 0
        self.shots_hit            = 0
        self.last_proj_count      = 0
        self.frame_count          = 0
        self.level_up_choices     = {"Speed": 0, "Max Health": 0, "Health Regen": 0, "Damage": 0, "Heal": 0}
        self._last_health         = self.player.health
        self._last_pos            = [self.player.pos.x, self.player.pos.y]
        self._last_shot_frame     = 0
        self.tutorial_timer       = 0
        self._tracked_projectiles = {}
        self.evasions_attempted   = 0
        self.evasions_successful  = 0
        self.evasions_failed      = 0
        self.stage_kills          = 0
        self.stage_total          = 1
        self.live_profile         = None  

    def _fire(self, origin, target):
        """Spawn a player projectile from origin toward target."""
        direction = pygame.Vector2(target) - pygame.Vector2(origin)
        if direction.length() > 0:
            direction = direction.normalize()
            self.player_projectiles.append(Projectile(
                origin.x, origin.y, direction.x, direction.y,
                player_projectile_radius, player_damage, player_projectile_color
            ))


    # Live adaptation
    def _maybe_adapt(self):
        """Compute and push a live profile to enemies once adapt_from_stage has been reached."""
        if self.current_stage <= adapt_from_stage:
            return
        if not self.behavior_log:
            return
        profile = compute_live_profile(self.behavior_log, self.current_stage)
        if profile:
            self.live_profile = profile
            update_profile(profile)  

    # Frame capture
    def capture_frame(self):
        """Snapshot the current game state into a dict for the behavior log."""
        cursor        = pygame.mouse.get_pos()
        alive_enemies = [e for e in self.enemies if e.health > 0]
        distances     = [e.pos.distance_to(self.player.pos) for e in alive_enemies]
        nearest       = alive_enemies[distances.index(min(distances))] if distances else None
        health_delta  = round(self.player.health - self._last_health, 1)
        self._last_health = self.player.health
        displacement  = round(self.player.pos.distance_to(pygame.Vector2(self._last_pos)), 1)
        self._last_pos    = [self.player.pos.x, self.player.pos.y]
        max_dist      = pygame.Vector2(cx, cy).length()
        center_dist   = round(self.player.pos.distance_to(pygame.Vector2(cx, cy)) / max_dist, 3)
        edge_dist     = round(min(
            self.player.pos.x, screen_width  - self.player.pos.x,
            self.player.pos.y, screen_height - self.player.pos.y
        ) / screen_width, 5)
        frames_since_shot = self.frame_count - self._last_shot_frame
        if self.last_action == "shoot":
            self._last_shot_frame = self.frame_count

        return {
            "stage":             self.current_stage,
            "frame":             self.frame_count,
            "level_up_priority": dict(self.level_up_choices),
            "shots_fired":       self.shots_fired,
            "shots_hit":         self.shots_hit,
            "player_pos":        [round(self.player.pos.x, 1), round(self.player.pos.y, 1)],
            "player_health":     round(self.player.health, 1),
            "health_delta":      health_delta,
            "player_action":     self.last_action,
            "displacement":      displacement,
            "center_dist":       center_dist,
            "edge_dist":         edge_dist,
            "frames_since_shot": frames_since_shot,
            "player_level":      self.player.level,
            "aim_direction":     [round(cursor[0] - self.player.pos.x, 1),
                                  round(cursor[1] - self.player.pos.y, 1)],
            "nearest_enemy": {
                "type":     nearest.name if nearest else None,
                "dist":     round(nearest.pos.distance_to(self.player.pos), 1) if nearest else None,
                "hp":       nearest.health if nearest else None,
                "hp_ratio": round(nearest.health / nearest.maxhealth, 2) if nearest else None,
                "pos":      [round(nearest.pos.x, 1), round(nearest.pos.y, 1)] if nearest else None,
            },
            "enemy_count":   len(alive_enemies),
            "enemy_types":   {t["name"]: sum(1 for e in alive_enemies if e.name == t["name"]) for t in types},
            "enemies": [
                {"pos": [round(e.pos.x, 1), round(e.pos.y, 1)], "type": e.name,
                 "hp": e.health, "hp_ratio": round(e.health / e.maxhealth, 2),
                 "radius": e.radius, "dist_to_player": round(e.pos.distance_to(self.player.pos), 1)}
                for e in alive_enemies
            ],
            "projectiles": [
                {"pos": [round(p.pos.x, 1), round(p.pos.y, 1)],
                 "velocity": [round(p.velocity.x, 1), round(p.velocity.y, 1)]}
                for p in self.player_projectiles
            ],
            "enemy_projectiles": [
                {"pos": [round(ep.pos.x, 1), round(ep.pos.y, 1)],
                 "velocity": [round(ep.velocity.x, 1), round(ep.velocity.y, 1)],
                 "damage": ep.damage,
                 "dist_to_player": round(ep.pos.distance_to(self.player.pos), 1)}
                for ep in self.enemy_projectiles
            ],
            "incoming_projectile_count": len(self.enemy_projectiles),
            "evasions_attempted":  self.evasions_attempted,
            "evasions_successful": self.evasions_successful,
            "evasions_failed":     self.evasions_failed,
            "evasion_rate":        round(self.evasions_successful / max(self.evasions_attempted, 1), 2),
        }

    # Save + LLM synthesis (runs after game-over in background thread)
    def save_log(self):
        """Write the behavior log to disk and kick off LLM synthesis in a background thread."""
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path     = os.path.join(BASE_DIR, "replays", self.profile_name)
        os.makedirs(path, exist_ok=True)
        timestamp = int(time.time())
        filepath  = os.path.join(path, f"{self.profile_name}_run_{timestamp}.json")
        with open(filepath, "w") as f:
            json.dump(self.behavior_log, f)
        print(f"[Game] Behavior log saved: {filepath}  ({len(self.behavior_log)} frames)")
        thread = threading.Thread(target=self._run_synthesis, args=(filepath,), daemon=True)
        thread.start()
        return filepath

    def _run_synthesis(self, log_path):
        """Run LLM profile synthesis in a background thread, printing any traceback on failure."""
        try:
            synthesis(log_path, self.profile_name)
        except Exception:
            import traceback
            traceback.print_exc()


    # Evasion tracking
    def _update_evasion(self):
        """Track enemy projectiles entering warning range and record hits or successful dodges."""
        current_ids = {id(ep) for ep in self.enemy_projectiles}
        for ep in self.enemy_projectiles:
            eid  = id(ep)
            dist = self.player.pos.distance_to(ep.pos)
            if dist < warning_radius and eid not in self._tracked_projectiles:
                self._tracked_projectiles[eid] = {"hit": False}
                self.evasions_attempted += 1
        for eid in set(self._tracked_projectiles) - current_ids:
            tracked = self._tracked_projectiles.pop(eid)
            if tracked["hit"]:
                self.evasions_failed += 1
            else:
                self.evasions_successful += 1

    def _mark_evasion_hit(self):
        """Flag the first tracked projectile as having hit the player."""
        for ep in self.enemy_projectiles:
            eid = id(ep)
            if eid in self._tracked_projectiles:
                self._tracked_projectiles[eid]["hit"] = True
                break

    # Main update
    def update(self, dt):
        """Advance the game by dt; handles input, projectiles, enemy AI, stage progression, and logging. Returns 'game_over', 'level', or None."""
        if self.player.health <= 0:
            return "game_over"

        self.elapsed += dt
        self.player.update(dt)

        if len(self.player_projectiles) > self.last_proj_count:
            self.last_action = "shoot"
            self.shots_fired += 1
        else:
            keys = pygame.key.get_pressed()
            if   keys[pygame.K_w] or keys[pygame.K_UP]:    self.last_action = "move_up"
            elif keys[pygame.K_s] or keys[pygame.K_DOWN]:  self.last_action = "move_down"
            elif keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.last_action = "move_left"
            elif keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.last_action = "move_right"
            else:                                           self.last_action = "idle"
        self.last_proj_count = len(self.player_projectiles)

        self.frame_count += 1
        if self.frame_count % 10 == 0:
            self.behavior_log.append(self.capture_frame())

        self._update_evasion()

        for enemy in self.enemies:
            if enemy.health > 0:
                enemy.update(dt, self.player, self.player_projectiles, self.enemy_projectiles)

        # Stage clear → next wave + live adaptation
        if len(enemies) == 0 and self.spawn_queue == 0:
            self._maybe_adapt()                          # ← adapt before spawning next wave
            self.current_stage += 1
            total              = round(self.current_stage * enemies_count_rate)
            self.stage_kills   = 0
            self.stage_total   = total
            self.spawn_total   = total
            spawn_enemies(1)
            self.spawn_queue   = total - 1
            self.spawn_timer   = self.spawn_delay
            self.spawn_delay   = max(0.2, self.spawn_delay * 0.85)
            if self.current_stage > settings.record:
                settings.record = self.current_stage
            self.player.health = min(self.player.health + self.player.regen, self.player.maxhealth)
        elif self.spawn_queue > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                spawn_enemies(1)
                self.spawn_queue -= 1
                self.spawn_timer  = self.spawn_delay

        # Player projectile collisions
        for projectile in self.player_projectiles[:]:
            projectile.update(dt)
            if projectile.out_of_bounds():
                self.player_projectiles.remove(projectile)
                continue
            for enemy in enemies:
                distance = projectile.pos.distance_to(enemy.pos)
                if distance <= projectile.radius + enemy.radius:
                    if enemy.take_damage(self.player.damage):
                        self.shots_hit   += 1
                        self.player.xp   += enemy.xp
                        enemies.remove(enemy)
                        self.stage_kills += 1
                        if self.player.xp >= self.player.next:
                            self.player.xp  -= self.player.next
                            self.player.next = round(self.player.next * self.player.rate)
                            self.player.level += 1
                            return "level"
                        break
                    else:
                        self.shots_hit += 1
                    if projectile in self.player_projectiles:
                        self.player_projectiles.remove(projectile)
                    break

        # Enemy projectile collisions
        for ep in self.enemy_projectiles[:]:
            ep.update(dt)
            if ep.out_of_bounds():
                self.enemy_projectiles.remove(ep)
                continue
            distance = ep.pos.distance_to(self.player.pos)
            if distance <= ep.radius + self.player.radius:
                self.player.take_damage(ep.damage)
                self._mark_evasion_hit()
                self.enemy_projectiles.remove(ep)

        # Enemy–player collision (push player)
        for enemy in self.enemies:
            if enemy.health > 0:
                distance = enemy.pos.distance_to(self.player.pos)
                if distance <= enemy.radius + self.player.radius and distance > 0:
                    direction   = (self.player.pos - enemy.pos).normalize()
                    overlap     = (enemy.radius + self.player.radius) - distance
                    self.player.pos += direction * overlap

        # Enemy–enemy separation
        enemy_list = [e for e in self.enemies if e.health > 0]
        for _ in range(5):
            for j in range(len(enemy_list)):
                for k in range(j + 1, len(enemy_list)):
                    a, b     = enemy_list[j], enemy_list[k]
                    dist     = a.pos.distance_to(b.pos)
                    min_dist = a.radius + b.radius
                    if 0 < dist < min_dist:
                        direction = (b.pos - a.pos).normalize()
                        overlap   = (min_dist - dist) / 2
                        a.pos    -= direction * overlap * 0.2
                        b.pos    += direction * overlap * 0.2