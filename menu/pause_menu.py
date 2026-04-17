import pygame
import pygame_gui
from settings import (cx, cy, screen_height, screen_width, button_height, button_width, 
                      font_big, font_small, text_color, thirds)

class PauseMenu:
    def __init__(self, manager):

        self.resume_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy - 30), (button_width, button_height)),
            text="Resume",
            manager=manager
        )

        self.quit_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 130), (button_width, button_height)),
            text = "Main Menu",
            manager = manager
        )
        self.settings_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 50), (button_width, button_height)),
            text = "Settings",
            manager = manager
        )
        self.hide()    

    def handle_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.resume_button: 
                return "resume"
            if event.ui_element == self.quit_button:   
                return "main"
            if event.ui_element == self.settings_button:   
                return "settings"
        return None

    def draw(self, screen, manager):
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        label = font_big.render("PAUSED", True, text_color)
        screen.blit(label, label.get_rect(center = (cx, thirds)))
        manager.draw_ui(screen)

    def hide(self):
        self.resume_button.hide()
        self.quit_button.hide()
        self.settings_button.hide()

    def show(self):
        self.resume_button.show()
        self.quit_button.show()
        self.settings_button.show()
