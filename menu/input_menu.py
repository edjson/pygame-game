import pygame
import pygame_gui
from settings import cx, cy, button_height, button_width, cbutton_height, cbutton_width, font_big, text_color, thirds, background
import settings


class InputMenu:
    """Colour-picker screen shown on first launch so the player can choose their player colour."""

    def __init__(self, manager):
        """Create the colour buttons and hide them until the menu is shown."""
        self.manager = manager
        self.gap     = 220
        self.visible = False
        self.buttons = {}
        self.color_buttons()
        self.hide()

    def color_buttons(self):
        """Lay out one button per colour in a two-row grid centred on screen."""
        gap = self.gap
        color_layout = [
            ("red",    cx - gap - cbutton_width, cy - cbutton_height),
            ("orange", cx - cbutton_width,        cy - cbutton_height),
            ("yellow", cx + gap - cbutton_width,  cy - cbutton_height),
            ("green",  cx - gap - cbutton_width,  cy - cbutton_height + 80),
            ("blue",   cx - cbutton_width,         cy - cbutton_height + 80),
            ("indigo", cx + gap - cbutton_width,   cy - cbutton_height + 80),
            ("violet", cx - cbutton_width,          cy - cbutton_height + 160),
        ]
        for name, x, y in color_layout:
            self.buttons[name] = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(x, y, button_width, button_height),
                text=name.capitalize(),
                manager=self.manager
            )

    def handle_event(self, event, player):
        """Apply the chosen colour to settings and return 'main', or 'input_menu' while waiting."""
        if not self.visible:
            return "input_menu"
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            for name, btn in self.buttons.items():
                if event.ui_element == btn:
                    settings.player_color = name
                    settings.color_options.remove(name)
                    return "main"
        return "input_menu"

    def draw(self, screen, manager):
        """Draw the background, title, and colour buttons."""
        screen.fill(background)
        label = font_big.render("Choose Your Color", True, text_color)
        screen.blit(label, label.get_rect(center=(cx, thirds)))
        manager.draw_ui(screen)

    def hide(self):
        """Hide all colour buttons and mark the menu inactive."""
        self.visible = False
        for btn in self.buttons.values():
            btn.hide()

    def show(self):
        """Show all colour buttons and mark the menu active."""
        self.visible = True
        for btn in self.buttons.values():
            btn.show()