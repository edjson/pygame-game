import pygame
from settings import (background, screen_width, color_options,
                      font_small, input_color, color_health_bg, 
                      color_health_bar, text_color, player_projectile_color,
                      enemy_projectile_color
                      )
from game_environments.game import Game
from game_environments.tutorial import Tutorial
from game_environments.simulationenv import Simulation
from entities.enemy import enemies
import settings
import random


class renderer:
    """Handles all screen drawing: world entities, HUD health bar, stage info, and player stats."""

    def __init__(self, screen):
        """Store the pygame surface to draw onto."""
        self.screen = screen

    def draw_game(self, player, game):
        """Draw health bar, stage label, level, kill count, projectiles, trace and stat readouts."""
        self.screen.fill(background)
        player.draw(self.screen)
        for i in game.enemies:
            if i.health > 0:
                i.draw(self.screen)
        game.particles.draw(self.screen)
        for i in game.player_projectiles:
            if settings.trace == True:
                direction = i.velocity.normalize()
                end = i.pos + direction * screen_width
                pygame.draw.line(self.screen, random.choice(color_options), (int(i.pos.x), int(i.pos.y)), (int(end.x), int(end.y)), 1)
            pygame.draw.circle(self.screen, i.color, i.pos, i.radius)
        
        for i in game.enemy_projectiles:
            #trajectory lines
            if settings.trace == True:
                direction = i.velocity.normalize()
                end = i.pos + direction * screen_width
                pygame.draw.line(self.screen, random.choice(color_options), (int(i.pos.x), int(i.pos.y)), (int(end.x), int(end.y)), 1)
            pygame.draw.circle(self.screen, i.color, (int(i.pos.x), int(i.pos.y)), i.radius)

        bar_w = 250
        bar_h = 25
        x     = 50
        y     = 50
        stage_kills = getattr(game, "stage_kills", 0)
        stage_total = getattr(game, "stage_total", 1)

        ratio = player.health / player.maxhealth 
        pygame.draw.rect(self.screen, color_health_bg, (x, y, bar_w, bar_h))
        pygame.draw.rect(self.screen, color_health_bar,(x, y, int(bar_w * ratio), bar_h))

        stage       = font_small.render(f"stage {game.current_stage}", True, input_color)
        leveling    = font_small.render(f"level {player.level} - {player.xp} / {player.next}", True, input_color)
        health_int  = font_small.render(f"{int(player.health)}/{player.maxhealth}", True, "black")
        stage_count = font_small.render(f"{stage_kills} / {stage_total}", True, input_color)

        self.screen.blit(health_int, health_int.get_rect(center = (x + (bar_w // 2), (y + bar_h //2))))
        self.screen.blit(stage, stage.get_rect(topleft = (x, y + bar_h + 4)))
        self.screen.blit(leveling, leveling.get_rect(topleft = (x + (bar_w // 2) - (leveling.get_width() // 2), y + bar_h + 4 )))
        self.screen.blit(stage_count, stage_count.get_rect(topright=(x + bar_w, y + bar_h + 4)))


        value_x = screen_width - 50
        label_x = screen_width - 200

        stats = [
            ("Health Regen", player.regen),
            ("Damage", player.damage),
            ("Speed", player.speed)
        ]

        for i, (label, value) in enumerate(stats):
            y_pos = 50 + (i * 25)
            label = font_small.render(str(label), True, text_color)
            value = font_small.render(str(value), True, text_color)
            self.screen.blit(label, label.get_rect(topright = (label_x, y_pos)))
            self.screen.blit(value, value.get_rect(topright = (value_x, y_pos)))
        
        

