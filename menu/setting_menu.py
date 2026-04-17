import pygame
import pygame_gui
import settings
from settings import (cx, cy, screen_height, screen_width, button_height, button_width, 
                      font_big, font_small, text_color, thirds, font_big, font_small, transparent, volume,
                      button_width, button_height)



class SettingsMenu:
    def __init__(self, manager):
        self.volume_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect((cx - 150, cy), (300, 40)),
            start_value = 50,
            value_range = (0, 100),
            manager = manager
        )
        self.Back = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 50), (button_width, button_height)),
            text="Back",
            manager=manager
        )
        self.hide()    

    def handle_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.Back: return "back"
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == self.volume_slider:
                settings.volume = self.volume_slider.get_current_value()
                pygame.mixer.music.set_volume(settings.volume / 100)

    def hide(self):
        self.volume_slider.hide()
        self.Back.hide()
    def show(self):
        self.volume_slider.show()
        self.Back.show()
        return None

    def draw(self, screen, manager):
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill(transparent)
        screen.blit(overlay, (0, 0))
        label = font_big.render("Settings", True, text_color)
        volume_label = font_small.render("Volume", True, text_color)
        screen.blit(label, label.get_rect(center=(cx, thirds)))
        screen.blit(volume_label, volume_label.get_rect(center=(cx, cy - 50)))
        volume_value = font_small.render(f"{int(self.volume_slider.get_current_value())}%", True, text_color)
        screen.blit(volume_value, volume_value.get_rect(center=(cx, cy - 20)))
        manager.draw_ui(screen)

