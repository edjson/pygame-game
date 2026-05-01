import pygame
import pygame_gui
import random
from settings import cx, cy, button_height, button_width, font_big, text_color, thirds

buffs = ["Speed", "Max Health", "Health Regen", "Damage", "Heal"]


class LevelUpMenu:
    """Level-up overlay that presents three random upgrade choices and applies the selected one."""

    def __init__(self, manager):
        """Create three horizontally spaced upgrade buttons and hide them until level-up."""
        gap = 220
        self.buff_list   = []
        self.last_chosen = None

        self.one = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(cx - gap - button_width // 2, cy - button_height // 2, button_width, button_height),
            text="...",
            manager=manager
        )
        self.two = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(cx - button_width // 2, cy - button_height // 2, button_width, button_height),
            text="...",
            manager=manager
        )
        self.three = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(cx + gap - button_width // 2, cy - button_height // 2, button_width, button_height),
            text="...",
            manager=manager
        )
        self.hide()

    def handle_event(self, event, player):
        """Apply the chosen buff, record it in last_chosen, and return 'playing', or 'level' while waiting."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            for btn, buff in zip([self.one, self.two, self.three], self.buff_list):
                if event.ui_element == btn:
                    self.buff_applied(buff, player)
                    self.last_chosen = buff
                    return "playing"
        return "level"

    def draw(self, screen, manager):
        """Draw the LEVEL UP title and upgrade buttons."""
        label = font_big.render("LEVEL UP", True, text_color)
        screen.blit(label, label.get_rect(center=(cx, thirds)))
        manager.draw_ui(screen)

    def buff_applied(self, buff, player):
        """Apply a named upgrade to the player in-place."""
        if buff == "Speed":       player.speed     += 5
        if buff == "Max Health":  player.maxhealth += 5
        if buff == "Health Regen":player.regen     += 10
        if buff == "Damage":      player.damage    += 5
        if buff == "Heal":        player.health     = player.maxhealth

    def hide(self):
        """Hide all three upgrade buttons."""
        self.one.hide()
        self.two.hide()
        self.three.hide()

    def show(self):
        """Sample three random upgrades, label the buttons, and show them."""
        self.buff_list = random.sample(buffs, 3)
        self.one.set_text(self.buff_list[0])
        self.two.set_text(self.buff_list[1])
        self.three.set_text(self.buff_list[2])
        self.one.show()
        self.two.show()
        self.three.show()