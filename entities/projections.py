import pygame
import math
from settings import projectile_speeds, screen_height, screen_width, color_options
import random 
class Projectile:
    """Moving circular projectile with damage, color, and screen-bounds detection."""
    def __init__(self, x, y, direction_x, direction_y, radius, damage, color):
        self.pos      = pygame.Vector2(x, y)
        self.velocity = pygame.Vector2(direction_x, direction_y) * projectile_speeds
        self.radius   = radius
        self.damage   = damage
        self.color    = random.choice(color_options)

    def update(self, dt):
        """advances position by velocity * dt"""
        self.pos += self.velocity * dt

    def out_of_bounds(self):
        """returns True if projectile has left the screen"""
        return (self.pos.x < -self.radius or
                self.pos.x > screen_width + self.radius or
                self.pos.y < -self.radius or
                self.pos.y > screen_height + self.radius)

    def draw(self, screen):
        """draws projectile"""
        pygame.draw.circle(screen, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)
