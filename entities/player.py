import pygame
from settings import player_radius, player_speed, player_health, color_health_bg, color_health_bar, player_damage, cx, cy, player_next, player_xpRate, player_regen, screen_height, screen_width
import settings
from entities.projections import Projectile
from assets.assets import sound_effects
import os
shoot_sfx = None
if os.environ.get("SDL_AUDIODRIVER") != "dummy":
    shoot_sfx = sound_effects("47313572-ui-pop-sound-316482.mp3")

class Player:
    """Human-controlled player with WASD movement, health, XP, and callback-based firing."""

    def __init__(self):
        """Initialise position, stats, and XP progression from settings defaults."""
        self.pos           = pygame.Vector2(cx, cy)
        self.vel           = pygame.Vector2(0,0)
        self.radius        = player_radius
        self.speed         = player_speed
        self.damage        = player_damage
        self.health        = player_health
        self.maxhealth     = player_health
        self.regen         = player_regen
        self.xp            = 0
        self.next          = player_next
        self.rate          = player_xpRate
        self.level         = 1
        self.fire_callback = None
        # sprites
        self.image = None
        self.rect = None
        if os.environ.get("SDL_VIDEODRIVER") != "dummy":
            originalImage = pygame.image.load("assets/sprites/PlayerSprite.png").convert_alpha()
            diameter = self.radius * 2
            self.image = pygame.transform.scale(originalImage, (diameter, diameter))
            self.rect = self.image.get_rect(center=(self.pos.x, self.pos.y))

    def input(self, dt):
        """Initialise position, stats, and XP progression from settings defaults."""
        keys = pygame.key.get_pressed()
        self.vel = pygame.Vector2(0, 0)

        if keys[pygame.K_w]: self.vel.y -= 1
        if keys[pygame.K_a]: self.vel.x -= 1
        if keys[pygame.K_s]: self.vel.y += 1
        if keys[pygame.K_d]: self.vel.x += 1
        if keys[pygame.K_ESCAPE]:
            return "pause"

        if self.vel.length() > 0:
            self.vel = self.vel.normalize() * self.speed

        self.pos.x = max(self.radius, min(screen_width - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(screen_height - self.radius, self.pos.y))

    def update(self, dt):
        """Advance position each frame; firing is handled by EventHandler."""
        self.input(dt)
        self.pos += self.vel * dt
        self.pos.x = max(self.radius, min(screen_width - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(screen_height - self.radius, self.pos.y))

    def draw_health_bar(self, screen):
        """Draw a small health bar centred above the player circle."""
        if self.image is None:
            return
        bar_w = 50
        bar_h = 6
        x     = int(self.pos.x) - bar_w // 2
        y     = int(self.pos.y) - self.radius - 12
        ratio = self.health / self.maxhealth
        pygame.draw.rect(screen, color_health_bg, (x, y, bar_w, bar_h))
        pygame.draw.rect(screen, color_health_bar, (x, y, int(bar_w * ratio), bar_h))

    def take_damage(self, amount):
        """Subtract amount from current health."""
        self.health -= amount

    def draw(self, screen):
        """Register the function invoked when the player fires; signature: callback(from_pos, cursor_pos)."""
        # pygame.draw.circle(screen, settings.player_color, (int(self.pos.x), int(self.pos.y)), self.radius)
        if self.image is None:
            return
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        screen.blit(self.image, self.rect)
        self.draw_health_bar(screen)

    def set_fire_callback(self, callback):
        self.fire_callback = callback

    def launch(self, cursor_pos):
        """Fire a projectile toward cursor_pos via the registered fire callback."""
        if self.fire_callback:
            self.fire_callback(self.pos, cursor_pos)
            if shoot_sfx:
                shoot_sfx.play()
