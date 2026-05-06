import pygame
import pygame_gui
import settings
from settings import (screen_height, screen_width, title, fps, volume, font_big, font_small, cx, cy,
                      text_color, text_passive, input_color)
from menu.main_menu import MainMenu
from menu.level_up_menu import LevelUpMenu
from assets.assets import load_assets
from core.event_handler import EventHandler
from game_environments.game import Game
from core.render import renderer
from menu.game_over import GameOverMenu
from menu.pause_menu import PauseMenu
from menu.setting_menu import SettingsMenu
from game_environments.simulationenv import Simulation
from game_environments.tutorial import Tutorial
from menu.input_menu import InputMenu
from entities.enemy_list import build_types
import traceback
import threading
from core.profile_manager import init_profile
from assets.assets import Music

pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption(title)
clock  = pygame.time.Clock()

_load_done   = threading.Event()
_load_error  = None         
_load_status = ""         
_assets       = None
_manager      = None
_menus        = None
_music        = None
_profile_name = None
_saved_profile= None
_game         = None


def _background_loader():
    """Runs in a worker thread and writes to module-level names."""
    global _assets, _manager, _menus, _music
    global _profile_name, _saved_profile, _game, _load_status, _load_error

    try:
        _load_status = "Loading assets…"
        _assets = load_assets()

        _load_status = "Building enemy types…"
        build_types()

        _load_status = "Reading profile…"
        _profile_name, _saved_profile = init_profile()

        _load_status = "Creating UI…"
        _manager = pygame_gui.UIManager((screen_width, screen_height))

        _menus = {
            "main":       MainMenu(_manager, _assets),
            "game_over":  GameOverMenu(_manager),
            "pause":      PauseMenu(_manager),
            "settings":   SettingsMenu(_manager),
            "level":      LevelUpMenu(_manager),
            "input_menu": InputMenu(_manager),
        }

        _load_status = "Preparing music…"
        _music = Music()

        _load_status = "Setting up game…"
        _game = Game(profile_name=_profile_name)

        _load_status = "Done"
    except Exception as exc:
        _load_error = exc
        traceback.print_exc()
    finally:
        _load_done.set()

loader_thread = threading.Thread(target=_background_loader, daemon=True)
loader_thread.start()


def draw_loading_screen(progress_anim: float):
    """Draws a loading screen while the loader runs."""
    screen.fill((20, 20, 20))

    title_surf = font_big.render(title, True, text_color)
    screen.blit(title_surf, title_surf.get_rect(center=(cx, cy - 80)))

    status_surf = font_small.render(_load_status, True, text_passive)
    screen.blit(status_surf, status_surf.get_rect(center=(cx, cy)))
    bar_w  = 300
    bar_h  = 4
    bar_x  = cx - bar_w // 2
    bar_y  = cy + 40
    fill_w = int((0.5 + 0.5 * __import__('math').sin(progress_anim * 3.14)) * bar_w)
    pygame.draw.rect(screen, (60, 60, 60),  (bar_x, bar_y, bar_w, bar_h), border_radius=2)
    pygame.draw.rect(screen, (180, 180, 180), (bar_x, bar_y, fill_w, bar_h), border_radius=2)

    pygame.display.flip()


anim_t = 0.0
while not _load_done.is_set():
    dt_raw = clock.tick(fps) / 1000
    anim_t += dt_raw

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    draw_loading_screen(anim_t)

if _load_error is not None:
    print(f"[FATAL] Background loader failed: {_load_error}")
    pygame.quit()
    exit(1)

assets       = _assets
manager      = _manager
menus        = _menus
music        = _music
profile_name = _profile_name
saved_profile= _saved_profile
game         = _game

render  = renderer(screen)
handler = EventHandler(manager)

menus["main"].show()
state       = "main"
dt          = 0
back_state  = None
paused_from = None
last_mode   = "playing"
locked_mouse = False
tutorial    = None
simulation  = None

while state != "quit":

    if state == "tutorial" or (state == "level" and last_mode == "tutorial"):
        new_state = handler.process(state, menus, tutorial.player.pos, tutorial.player, paused_from, tutorial=tutorial)
    else:
        current_player = getattr(game, "player", None)
        new_state = handler.process(state, menus, None, current_player, paused_from)

    if new_state == "quit":
        state = "quit"

    # main -> playing
    if state == "main" and new_state == "playing":
        music.play()
        menus["main"].hide()
        game.reset()
        last_mode = "playing"
        state = "playing"
        continue

    if new_state != state:

        # main -> simulation
        if state == "main" and new_state == "simulation":
            simulation = Simulation(profile_name=settings.profile_name)
            menus["main"].hide()
            simulation.reset()
            state = "simulation"
            continue

        # main -> tutorial
        if state == "main" and new_state == "tutorial":
            music.play()
            tutorial = Tutorial(profile_name=settings.profile_name)
            menus["main"].hide()
            tutorial.reset()
            last_mode = "tutorial"
            state = "tutorial"
            continue

        # playing -> pause
        if state == "playing" and new_state == "pause":
            music.pause()
            paused_from = "playing"
            menus["pause"].show()
            state = "pause"
            continue

        # input_menu -> main
        if state == "input_menu" and new_state == "main":
            build_types()
            profile_name, saved_profile = init_profile()
            game = Game(profile_name=profile_name)
            menus["input_menu"].hide()
            menus["main"].show()
            state = "main"
            continue

        # tutorial -> pause
        if state == "tutorial" and new_state == "pause":
            music.pause()
            paused_from = "tutorial"
            menus["pause"].show()
            state = "pause"
            continue

        # pause -> playing
        if state == "pause" and new_state == "playing":
            paused_from = None
            music.unpause()
            menus["pause"].hide()
            state = "playing"
            continue

        # pause -> tutorial
        if state == "pause" and new_state == "tutorial":
            paused_from = None
            music.unpause()
            menus["pause"].hide()
            state = "tutorial"
            continue

        # main -> settings
        if state == "main" and new_state == "settings":
            back_state = "main"
            menus["main"].hide()
            menus["settings"].show()
            state = "settings"
            continue

        # game_over -> settings
        if state == "game_over" and new_state == "settings":
            back_state = "game_over"
            menus["game_over"].hide()
            menus["settings"].show()
            state = "settings"
            continue

        # pause -> settings
        if state == "pause" and new_state == "settings":
            back_state = "pause"
            menus["pause"].hide()
            menus["settings"].show()
            state = "settings"
            continue

        # pause -> main
        if state == "pause" and new_state == "main":
            music.stop()
            paused_from = None
            menus["pause"].hide()
            menus["main"].show()
            state = "main"
            continue

        # settings -> back
        if state == "settings" and new_state == "back":
            music.set_volume()
            menus["settings"].hide()
            if back_state == "main":
                menus["main"].show()
                state = "main"
            elif back_state == "game_over":
                menus["game_over"].show()
                state = "game_over"
            elif back_state == "pause":
                menus["pause"].show()
                state = "pause"
            back_state = None
            continue

        # playing -> game_over
        if state == "playing" and new_state == "game_over":
            music.stop()
            try:
                game.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
            continue

        # tutorial -> game_over
        if state == "tutorial" and new_state == "game_over":
            music.stop()
            try:
                tutorial.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
            continue

        if state == "game" and new_state == "game_over":
            music.stop()
            try:
                game.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
            continue

        # game_over -> main
        if state == "game_over" and new_state == "main":
            menus["game_over"].hide()
            menus["main"].show()
            state = "main"
            continue

        # game_over -> restart
        if state == "game_over" and new_state == "restart":
            music.restart()
            menus["game_over"].hide()
            game.reset()
            state = "playing"
            continue

        # level -> playing / tutorial
        if state == "level" and new_state == "playing":
            menus["level"].hide()
            if last_mode == "tutorial" and menus["level"].last_chosen:
                tutorial.level_up_choices[menus["level"].last_chosen] += 1
                menus["level"].last_chosen = None
            state = last_mode
            continue

        if state == "level" and new_state == "tutorial":
            menus["level"].hide()
            state = "tutorial"
            continue

        # simulation <-> pause
        if state == "simulation" and new_state == "pause":
            paused_from = "simulation"
            menus["pause"].show()
            state = "pause"
            continue

        if state == "pause" and new_state == "simulation":
            paused_from = None
            menus["pause"].hide()
            state = "simulation"
            continue

    manager.update(dt)

    if state == "playing" or (state == "pause" and paused_from == "playing"):
        render.draw_game(game.player, game)

    if state == "tutorial" or (state == "pause" and paused_from == "tutorial"):
        render.draw_game(tutorial.player, tutorial)
        tutorial.draw_tutorial(screen)

    if state == "main":
        menus["main"].draw(screen, manager)
        menus["main"].show()

    if state == "game_over":
        elapsed = tutorial.elapsed if (last_mode == "tutorial" and tutorial) else game.elapsed
        menus["game_over"].draw(screen, manager, elapsed)
        menus["game_over"].show()

    if state == "playing":
        locked_mouse = True
        pygame.event.set_grab(locked_mouse)
        result = game.update(dt)
        if result == "game_over":
            locked_mouse = False
            pygame.event.set_grab(locked_mouse)
            music.stop()
            try:
                game.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
        elif result == "level":
            last_mode = "playing"
            menus["level"].show()
            state = "level"
        elif result:
            state = result

    if state == "tutorial":
        locked_mouse = True
        pygame.event.set_grab(locked_mouse)
        result = tutorial.update(dt)
        if result == "game_over":
            locked_mouse = False
            pygame.event.set_grab(locked_mouse)
            music.stop()
            try:
                tutorial.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
        elif result == "level":
            last_mode = "tutorial"
            state = "level"
            menus["level"].show()
        elif result:
            state = result

    if state == "simulation":
        locked_mouse = False
        pygame.event.set_grab(locked_mouse)
        render.draw_game(simulation.player, simulation)
        result = simulation.update(dt)
        if result:
            state = result

    if state == "settings":
        locked_mouse = False
        pygame.event.set_grab(locked_mouse)
        menus["settings"].draw(screen, manager)
        menus["settings"].show()

    if state == "pause":
        locked_mouse = False
        pygame.event.set_grab(locked_mouse)
        menus["pause"].draw(screen, manager)
        menus["pause"].show()

    if state == "level":
        locked_mouse = True
        pygame.event.set_grab(locked_mouse)
        menus["level"].draw(screen, manager)

    if state == "input_menu":
        locked_mouse = False
        pygame.event.set_grab(locked_mouse)
        menus["input_menu"].draw(screen, manager)
        menus["input_menu"].show()

    pygame.display.flip()
    dt = clock.tick(fps) / 1000

pygame.quit()