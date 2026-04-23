import pygame
import pygame_gui
import settings
from settings import (cx, cy, screen_height, screen_width, button_height, button_width,
                      font_big, font_small, text_color, thirds, transparent, volume)


class SettingsMenu:
    """Settings overlay with a volume slider Trace and Back button."""

    def __init__(self, manager):
        """Create the volume slider, Trace and Back button, then hide them."""
        self.volume_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect((cx - 150, cy), (300, 40)),
            start_value=50,
            value_range=(0, 100),
            manager=manager
        )
        self.Back = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 130), (button_width, button_height)),
            text="Back",
            manager=manager
        )
        self.trace_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx-100, cy + 50), (button_width, button_height)),
            text=f"Trace: {settings.trace}",
            manager=manager
        )
        self.hide()

    def handle_event(self, event):
        """Return 'back' on Back press; update settings.volume when the slider moves; toggles Trace on Trace press."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.Back:
                return "back"
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if event.ui_element == self.volume_slider:
                settings.volume = self.volume_slider.get_current_value()
                pygame.mixer.music.set_volume(settings.volume / 100)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.trace_button:
                settings.trace = not settings.trace
                self.trace_button.set_text(f"Trace: {settings.trace}")

    def hide(self):
        """Hide the slider, Back button and Trace button."""
        self.volume_slider.hide()
        self.Back.hide()
        self.trace_button.hide()

    def show(self):
        """Show the slider, Back button and trace button."""
        self.volume_slider.show()
        self.Back.show()
        self.trace_button.show()

    def draw(self, screen, manager):
        """Draw the transparent overlay, Settings title, volume label, current value, and UI."""
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill(transparent)
        screen.blit(overlay, (0, 0))
        label        = font_big.render("Settings", True, text_color)
        volume_label = font_small.render("Volume", True, text_color)
        volume_value = font_small.render(f"{int(self.volume_slider.get_current_value())}%", True, text_color)
        screen.blit(label,        label.get_rect(center=(cx, thirds)))
        screen.blit(volume_label, volume_label.get_rect(center=(cx, cy - 50)))
        screen.blit(volume_value, volume_value.get_rect(center=(cx, cy - 20)))
        manager.draw_ui(screen)