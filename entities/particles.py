import pygame
import random
import math


class Particle(pygame.sprite.Sprite):
    def __init__(self, groups, pos, color, direction, speed):
        super().__init__(groups)
        self.pos        = pygame.Vector2(pos)
        self.color      = color
        self.direction  = direction
        self.speed      = speed
        self.alpha      = 255
        self.fade_speed = 300
        self.size       = 4
        self.create_surf()

    def create_surf(self):
        self.image = pygame.Surface((self.size, self.size)).convert_alpha()
        self.image.set_colorkey("black")
        pygame.draw.circle(self.image, self.color, (self.size // 2, self.size // 2), self.size // 2)
        self.rect = self.image.get_rect(center=self.pos)

    def move(self, dt):
        self.pos       += self.direction * self.speed * dt
        self.rect.center = self.pos

    def fade(self, dt):
        self.alpha -= self.fade_speed * dt
        self.image.set_alpha(max(0, int(self.alpha)))

    def update(self, dt):
        self.move(dt)
        self.fade(dt)
        if self.alpha <= 0:
            self.kill()


def effect(enemy, particle_group):
    for _ in range(20):
        angle     = random.uniform(0, 2 * math.pi)
        direction = pygame.Vector2(math.cos(angle), math.sin(angle))
        speed     = random.uniform(50, 200)
        Particle(particle_group, enemy.pos, enemy.color, direction, speed)