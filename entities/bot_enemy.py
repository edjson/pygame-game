import pygame
import random
from entities.enemy_list import types
from entities.projections import EnemyProjectile, enemy_projectiles
from settings import screen_height, screen_width, margin, bar_h, bar_w, color_health_bar, color_health_bg
enemies = []

class Enemy:
    def __init__(self, x, y, type_index):
        unit                 = types[type_index]
        self.pos             = pygame.Vector2(x, y)
        self.color           = unit["color"]
        self.health          = unit["hp"]
        self.maxhealth       = unit["hp"]
        self.damage          = unit["damage"]
        self.speed           = unit["speed"]
        self.radius          = unit["radius"]
        self.proj_radius     = unit["proj_radius"]
        self.attack_cooldown = 0
        self.fire_rate       = 0
        self.fire_cooldown   = 0
        self.fire_rate       = unit["fire_rate"]
        self.xp              = unit["xp"]
        enemies.append(self)

    def update(self, dt, target_pos):
        direction = pygame.Vector2((target_pos.x - self.pos.x), (target_pos.y - self.pos.y))
        if direction.length() > 0:
            direction = direction.normalize()
            self.pos += direction * self.speed * dt
        
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        if self.fire_cooldown > 0:
            self.fire_cooldown -= dt

    def can_attack(self, target_pos, attack_range):
        distance = self.pos.distance_to(target_pos)
        return distance <= attack_range and self.attack_cooldown <= 0
    
    def attack(self):
        self.attack_cooldown = self.attack_rate
        return self.damage
    
    def can_fire(self):
        return self.fire_cooldown <= 0
    
    def fire_at_target(self, target_pos, enemy):
        self.fire_cooldown = self.fire_rate
        direction = (pygame.Vector2(target_pos) - self.pos).normalize()

        if direction.length() > 0:
            direction = direction.normalize()
            enemy_projectiles.append(EnemyProjectile(self.pos.x, self.pos.y, direction.x, direction.y, self.proj_radius, enemy))

    def take_damage(self, damage):
        self.health -= damage
        return self.health <= 0
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, self.pos, self.radius)
        bar_x = self.pos.x - bar_w // 2
        bar_y = self.pos.y - self.radius - 10

        pygame.draw.rect(screen,color_health_bg, (bar_x, bar_y, bar_w, bar_h))

        hp_ratio = max(0, self.health / self.maxhealth)
        pygame.draw.rect(screen, color_health_bar, (bar_x, bar_y, bar_w * hp_ratio, bar_h))
    

def spawn_enemies(count):
    m = margin
    for _ in range(count):
        side = random.choice(["top", "bottom", "left", "right"])
        type_index = random.randint(0, len(types) - 2)

        if side  == "top":
            x = random.randint(m, screen_width - m)
            y = m

        elif side == "bottom":
            x = random.randint(m, screen_width - m)
            y = screen_height - m

        elif side == "left":
            x = m
            y = random.randint(m, screen_height - m)

        else:
            x = screen_width - m
            y = random.randint(m, screen_height - m)

        Enemy(x, y, type_index)


def spawn_tutorial_unit():
    m = margin
    side = random.choice(["top", "bottom", "left", "right"])
    if side  == "top":
        x = random.randint(m, screen_width - m)
        y = m

    elif side == "bottom":
        x = random.randint(m, screen_width - m)
        y = screen_height - m

    elif side == "left":
        x = m
        y = random.randint(m, screen_height - m)

    else:
        x = screen_width - m
        y = random.randint(m, screen_height - m)

    Enemy(x, y, 6)
    

            



