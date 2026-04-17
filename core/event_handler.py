import pygame
import pygame_gui
from settings import min_cooldown, max_cooldown



def get_cooldown(fire_rate: float) -> int | None:
    """Convert 0.0-1.0 fire_rate to a ms cooldown. None = no firing."""
    if fire_rate == 0.0:
        return None
    fire_rate = max(0.0, min(1.0, fire_rate))
    return int(max_cooldown - (fire_rate * (max_cooldown - min_cooldown)))


class EventHandler:
    def __init__(self, manager, fire_rate: float = None):
        import settings
        self.manager        = manager
        self.mouse_held     = False
        self.last_fire_time = 0
        rate                = fire_rate if fire_rate is not None else settings.fire_rate
        self.fire_cooldown  = get_cooldown(rate)
        print(f"[EventHandler] fire_rate={rate}, cooldown={self.fire_cooldown}ms")

    def set_fire_rate(self, fire_rate: float):
        """Hot-update fire rate (called when live profile changes)."""
        self.fire_cooldown = get_cooldown(fire_rate)
        print(f"[EventHandler] fire_rate → {fire_rate}, cooldown={self.fire_cooldown}ms")

    def process(self, state: str, menus: dict, player_pos, player,
                paused_from=None, tutorial=None):
        current_time = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            self.manager.process_events(event)

            if state == "main":
                result = menus["main"].handle_event(event)
                if result == "simulation": return "simulation"
                if result == "playing":    return "playing"
                if result == "quit":       return "quit"
                if result == "settings":   return "settings"
                if result == "profile":    return "profile"
                if result == "tutorial":   return "tutorial"

            elif state in ("playing", "tutorial"):
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.mouse_held = False
                    return "pause"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.mouse_held = True
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self.mouse_held = False
                if state == "tutorial" and tutorial:
                    tutorial.handle_tutorial_event(event)

            elif state == "simulation":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return "pause"

            elif state == "pause":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return paused_from
                result = menus["pause"].handle_event(event)
                if result == "resume":   return paused_from if paused_from else "playing"
                if result == "main":     return "main"
                if result == "settings": return "settings"

            elif state == "game_over":
                result = menus["game_over"].handle_event(event)
                if result == "restart":  return "restart"
                if result == "main":     return "main"
                if result == "settings": return "settings"

            elif state == "settings":
                result = menus["settings"].handle_event(event)
                if result == "back": return "back"

            elif state == "level":
                result = menus["level"].handle_event(event, player)
                if result == "playing": return "playing"

            elif state == "input_menu":
                result = menus["input_menu"].handle_event(event, player)
                if result == "main": return "main"

        if state not in ("playing", "tutorial") and not pygame.mouse.get_pressed()[0]:
            self.mouse_held = False

        if self.mouse_held and state in ("playing", "tutorial"):
            if self.fire_cooldown is not None and player is not None:
                if current_time - self.last_fire_time >= self.fire_cooldown:
                    player.launch(pygame.mouse.get_pos())
                    self.last_fire_time = current_time
        elif not self.mouse_held:
            self.last_fire_time = 0

        return state