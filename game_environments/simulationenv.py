import pygame
import settings
import os
import json
from entities.ai_player import AIPlayer
from entities.projections import Projectile
from entities.enemy import enemies, spawn_enemies, init_agent, update_profile
from core.behavior_tracker import compute_live_profile
from settings import (enemies_count_rate, spawn_decay_rate, min_spawn_delay, current_spawn_delay,
                      player_projectile_radius, player_damage, player_projectile_color,
                      screen_width, screen_height, cx, cy)

ADAPT_FROM_STAGE = 3


def get_all_profiles():
    BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    replays_dir = os.path.join(BASE_DIR, "replays")
    if not os.path.exists(replays_dir):
        return []
    profiles = []
    for name in sorted(os.listdir(replays_dir)):
        folder = os.path.join(replays_dir, name)
        if os.path.isdir(folder) and os.path.exists(os.path.join(folder, "profile.json")):
            profiles.append(name)
    return profiles


def get_replay_paths(profile_name):
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder   = os.path.join(BASE_DIR, "replays", profile_name)
    if not os.path.exists(folder):
        return []
    return sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.startswith(f"{profile_name}_run_") and f.endswith(".json")
    ])


class Simulation:
    current_stage = 1
    spawn_total   = 1

    def __init__(self, profile_name=None):
        all_profiles = get_all_profiles()
        if profile_name and profile_name not in all_profiles:
            all_profiles.insert(0, profile_name)
        self.profiles      = all_profiles if all_profiles else [profile_name]
        self.profile_index = 0
        self.profile_name  = self.profiles[0]
        self.replay_paths  = get_replay_paths(self.profile_name)
        self.replay_index  = 0
        self.run_results   = []
        print(f"[Simulation] {len(self.profiles)} profile(s) found: {self.profiles}")
        print(f"[Simulation] Starting with profile: {self.profile_name}")
        print(f"[Simulation] Found {len(self.replay_paths)} replays for '{self.profile_name}'")
        self.reset()

    def current_replay_label(self):
        if not self.replay_paths:
            return "no replays"
        return os.path.basename(self.replay_paths[self.replay_index % len(self.replay_paths)])

    def reset(self):
        # Save result from previous run
        if hasattr(self, "elapsed") and self.elapsed > 0:
            label = self.current_replay_label()
            self.run_results.append((label, self.current_stage))
            print(f"[Simulation] Run {self.replay_index + 1} ({label}) ended at stage {self.current_stage}")
            self.replay_index += 1
            if self.replay_index >= max(len(self.replay_paths), 1):
                self.replay_index  = 0
                self._print_summary()
                self.profile_index = (self.profile_index + 1) % len(self.profiles)
                self.profile_name  = self.profiles[self.profile_index]
                self.replay_paths  = get_replay_paths(self.profile_name)
                self.run_results   = []
                print(f"[Simulation] Switching to profile: {self.profile_name} ({len(self.replay_paths)} replays)")

        # Fresh agent each reset
        init_agent(profile=None)

        self.current_stage       = 1
        self.player              = AIPlayer(profile_name=self.profile_name)
        self.player.set_fire_callback(self._ai_fire)
        self.player._enemy_proj_list = []
        enemies.clear()
        self.player_projectiles  = []
        self.enemy_projectiles   = []
        self.enemies             = enemies
        self.elapsed             = 0.0
        self.current_spawn_delay = current_spawn_delay
        self.spawn_queue         = 0
        self.spawn_timer         = self.current_spawn_delay
        self.spawn_total         = 1
        self.behavior_log        = []
        self.frame_count         = 0
        self.shots_fired         = 0
        self.shots_hit           = 0
        self.live_profile        = None
        self._last_pos           = [self.player.pos.x, self.player.pos.y]
        self._last_health        = self.player.health
        self._last_proj_count    = 0
        spawn_enemies(1)

        if self.replay_paths:
            print(f"[Simulation] Starting run {self.replay_index + 1}/{len(self.replay_paths)}: {self.current_replay_label()}")

    def _print_summary(self):
        if not self.run_results:
            return
        print("\n========================================")
        print(f"  SIMULATION SUMMARY: {self.profile_name}")
        print("========================================")
        for i, (label, stage) in enumerate(self.run_results):
            print(f"  Run {i+1:2} | {label:40} | Stage {stage}")
        avg  = sum(s for _, s in self.run_results) / len(self.run_results)
        best = max(s for _, s in self.run_results)
        print(f"  ----------------------------------------")
        print(f"  Avg stage: {avg:.1f}   Best: {best}")
        print("========================================\n")

    def _ai_fire(self, origin, target):
        direction = pygame.Vector2(target) - pygame.Vector2(origin)
        if direction.length() > 0:
            direction = direction.normalize()
            self.player_projectiles.append(Projectile(
                origin.x, origin.y, direction.x, direction.y,
                player_projectile_radius, player_damage, player_projectile_color
            ))

    def _maybe_adapt(self):
        """Compute and push live profile after ADAPT_FROM_STAGE."""
        if self.current_stage <= ADAPT_FROM_STAGE or not self.behavior_log:
            return
        profile = compute_live_profile(self.behavior_log, self.current_stage)
        if profile:
            self.live_profile = profile
            update_profile(profile)

            # Update AIPlayer fire rate based on live profile
            adapted = profile.get("fire_rate")
            if adapted is not None:
                self.player.fire_rate = adapted
                print(f"[Simulation] AIPlayer fire_rate adapted to {adapted}")

    def _capture_frame(self):
        """Lightweight frame capture for behavior_tracker."""
        alive     = [e for e in self.enemies if e.health > 0]
        distances = [e.pos.distance_to(self.player.pos) for e in alive]
        nearest   = alive[distances.index(min(distances))] if distances else None

        displacement      = round(self.player.pos.distance_to(pygame.Vector2(self._last_pos)), 1)
        self._last_pos    = [self.player.pos.x, self.player.pos.y]
        health_delta      = round(self.player.health - self._last_health, 1)
        self._last_health = self.player.health

        max_dist    = pygame.Vector2(cx, cy).length()
        center_dist = round(self.player.pos.distance_to(pygame.Vector2(cx, cy)) / max_dist, 3)

        return {
            "stage":        self.current_stage,
            "frame":        self.frame_count,
            "shots_fired":  self.shots_fired,
            "shots_hit":    self.shots_hit,
            "player_health":         round(self.player.health, 1),
            "health_delta":          health_delta,
            "displacement":          displacement,
            "center_dist":           center_dist,
            "nearest_enemy": {
                "dist": round(nearest.pos.distance_to(self.player.pos), 1) if nearest else None,
            },
            "enemies":               [{"dist_to_player": round(e.pos.distance_to(self.player.pos), 1)} for e in alive],
            "evasions_attempted":    0,
            "evasions_successful":   0,
            "evasion_rate":          0.0,
            "incoming_projectile_count": len(self.enemy_projectiles),
        }

    def update(self, dt):
        if self.player.health <= 0:
            self.reset()
            return

        self.elapsed     += dt
        self.frame_count += 1

        # Inject enemy projectiles so AIPlayer.dodge_projectiles() works
        self.player._enemy_proj_list = self.enemy_projectiles

        # Track shots
        if len(self.player_projectiles) > self._last_proj_count:
            self.shots_fired     += len(self.player_projectiles) - self._last_proj_count
        self._last_proj_count = len(self.player_projectiles)

        # Log behavior every 10 frames
        if self.frame_count % 10 == 0:
            self.behavior_log.append(self._capture_frame())

        self.player.update(dt)

        for enemy in self.enemies:
            if enemy.health > 0:
                enemy.update(dt, self.player, self.player_projectiles, self.enemy_projectiles)

        # Stage clear
        if len(enemies) == 0 and self.spawn_queue == 0:
            self._maybe_adapt()
            self.current_stage      += 1
            total                    = round(self.current_stage * enemies_count_rate)
            self.spawn_total         = total
            spawn_enemies(1)
            self.spawn_queue         = total - 1
            self.spawn_timer         = self.current_spawn_delay
            self.current_spawn_delay = max(min_spawn_delay, self.current_spawn_delay * spawn_decay_rate)
            self.player.health       = min(self.player.health + self.player.regen, self.player.maxhealth)
        elif self.spawn_queue > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                spawn_enemies(1)
                self.spawn_queue -= 1
                self.spawn_timer  = self.current_spawn_delay

        # Player projectile collisions
        for proj in self.player_projectiles[:]:
            proj.update(dt)
            if proj.out_of_bounds():
                self.player_projectiles.remove(proj)
                continue
            for enemy in enemies[:]:
                distance = proj.pos.distance_to(enemy.pos)
                if distance <= proj.radius + enemy.radius:
                    if enemy.take_damage(self.player.damage):
                        self.shots_hit   += 1
                        self.player.xp   += enemy.xp
                        enemies.remove(enemy)
                        if self.player.xp >= self.player.next:
                            self.player.xp  -= self.player.next
                            self.player.next = round(self.player.next * self.player.rate)
                            self.player.level += 1
                            self.player.pick_upgrade()
                    if proj in self.player_projectiles:
                        self.player_projectiles.remove(proj)
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
                self.enemy_projectiles.remove(ep)

        # Enemy–player push
        for enemy in self.enemies:
            if enemy.health > 0:
                distance = enemy.pos.distance_to(self.player.pos)
                if distance <= enemy.radius + self.player.radius and distance > 0:
                    direction        = (self.player.pos - enemy.pos).normalize()
                    overlap          = (enemy.radius + self.player.radius) - distance
                    self.player.pos += direction * overlap

        # Enemy separation
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