import pygame
from settings import player_radius, player_speed, player_health, color_health_bg, color_health_bar, player_damage, cx, cy, player_next, player_xpRate, player_regen, screen_height, screen_width
import settings
from entities.projections import Projectile

class Player:
    def __init__(self):
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

    def input(self, dt):
        """takes wasd movement, and escape to pause"""
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
        """per frame update — firing is handled by EventHandler, not here"""
        self.input(dt)
        self.pos += self.vel * dt
        self.pos.x = max(self.radius, min(screen_width - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(screen_height - self.radius, self.pos.y))

    def draw_health_bar(self, screen):
        """creates hp bar"""
        bar_w = 50
        bar_h = 6
        x     = int(self.pos.x) - bar_w // 2
        y     = int(self.pos.y) - self.radius - 12
        ratio = self.health / self.maxhealth
        pygame.draw.rect(screen, color_health_bg, (x, y, bar_w, bar_h))
        pygame.draw.rect(screen, color_health_bar, (x, y, int(bar_w * ratio), bar_h))

    def take_damage(self, amount):
        """applies damage"""
        self.health -= amount

    def draw(self, screen):
        """displays player and hp bar"""
        pygame.draw.circle(screen, settings.player_color, (int(self.pos.x), int(self.pos.y)), self.radius)
        self.draw_health_bar(screen)

    def set_fire_callback(self, callback):
        self.fire_callback = callback

    def launch(self, cursor_pos):
        """fires a projectile toward cursor via fire callback"""
        if self.fire_callback:
            self.fire_callback(self.pos, cursor_pos)