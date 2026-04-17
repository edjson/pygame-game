import pygame
import pygame_gui
from settings import (cx, cy, thirds, button_height, button_width, screen_height,
                      screen_width, font_big, font_small, describe, text_color,
                      record, text_passive, title, background)
from assets.assets import load_assets
import settings




class MainMenu:
    def __init__(self, manager, assets):
        self.start_button = pygame_gui.elements.UIButton(
            relative_rect = pygame.Rect((cx - 100, cy - 30), (button_width, button_height)),
            text = "Start Game",
            manager = manager
        )
        self.quit_button = pygame_gui.elements.UIButton(
            relative_rect = pygame.Rect((cx - 100, cy + 130), (button_width, button_height)),
            text = "Quit",
            manager = manager
        )
        self.settings_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 50), (button_width, button_height)),
            text = "Settings",
            manager = manager
        )
        self.simulation_button = pygame_gui.elements.UIButton(
            relative_rect = pygame.Rect((20, screen_height - 80), (button_width, button_height)),
            text = "Simuation",
            manager = manager
        )
        self.profile_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((20, screen_height- 160), (button_width, button_height)),
            text = "Tutorial",
            manager=manager
        )
        self.hide()


    def handle_event(self, event) -> str:
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.start_button: 
                return "playing"
            if event.ui_element == self.quit_button:  
                return "quit"
            if event.ui_element == self.settings_button: 
                return "settings"
            if event.ui_element == self.simulation_button: 
                return "simulation"
            if event.ui_element == self.profile_button: 
                return "tutorial"
        return None

    def draw(self, screen, manager):
        screen.fill(background)
        Title = font_big.render(title, True, text_color)
        sub = font_small.render("Enemies learn and coordinate in real time", True, text_passive)
        screen.blit(Title, Title.get_rect(center = (cx, thirds)))
        screen.blit(sub, sub.get_rect(center = (cx, thirds + 55)))
        record_score = font_small.render(f"Record: {settings.record}", True, text_passive)
        screen.blit(record_score, record_score.get_rect(topleft=(10, 10)))
        manager.draw_ui(screen)

    def hide(self):
        self.start_button.hide()
        self.quit_button.hide()
        self.settings_button.hide()
        self.simulation_button.hide()
        self.profile_button.hide()

    def show(self):
        self.start_button.show()
        self.quit_button.show()
        self.settings_button.show()
        self.simulation_button.show()
        self.profile_button.show()
