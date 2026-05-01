import pygame
import pygame_gui
from settings import (screen_height, screen_width, text_color, cx, cy, background,
                      button_height, button_width, font_big, font_small, thirds)


class GameOverMenu:
    """Game-over overlay with Play Again, Settings, and Main Menu buttons."""

    def __init__(self, manager):
        """Create and immediately hide the three game-over buttons."""
        self.start_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy - 30), (button_width, button_height)),
            text="Play Again",
            manager=manager
        )
        self.settings_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 50), (button_width, button_height)),
            text="Settings",
            manager=manager
        )
        self.quit_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx - 100, cy + 130), (button_width, button_height)),
            text="Main Menu",
            manager=manager
        )
        self.hide()

    def handle_event(self, event):
        """Return 'restart', 'main', or 'settings' on button press, else None."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.start_button:
                return "restart"
            if event.ui_element == self.quit_button:
                return "main"
            if event.ui_element == self.settings_button:
                return "settings"

    def draw(self, screen, manager, survived_time: float = 0.0):
        """Draw a semi-transparent overlay, GAME OVER title, survival time, and UI buttons."""
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        label      = font_big.render("GAME OVER", True, "red")
        time_label = font_small.render(f"Survived: {survived_time:.1f}s", True, text_color)
        screen.blit(label,      label.get_rect(center=(cx, thirds)))
        screen.blit(time_label, time_label.get_rect(center=(cx, thirds + 60)))
        manager.draw_ui(screen)

    def hide(self):
        """Hide all buttons."""
        self.start_button.hide()
        self.quit_button.hide()
        self.settings_button.hide()

    def show(self):
        """Show all buttons."""
        self.start_button.show()
        self.quit_button.show()
        self.settings_button.show()