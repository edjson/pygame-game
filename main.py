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
import json
import os
from entities.enemy_list import types
from core.profile_manager import init_profile

locked_mouse = False
pygame.init()
pygame.mixer.init() 

#music controls
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
audio_path = os.path.join(BASE_DIR, "assets", "audio", "music.ogg")
if not os.path.exists(audio_path):
    audio_path = os.path.join(
        BASE_DIR, "assets", "audio",
        "GlitchCat, prodBigMike - whatdoyousee [NCS Release].mp3"
    )
    if not os.path.exists(audio_path):
        audio_path = None  


def music_play(loops=-1):
    """Load and start music from scratch."""
    if audio_path is None:
        return
    try:
        if not pygame.mixer.music.get_busy():
            pygame.mixer.music.load(audio_path)
        pygame.mixer.music.set_volume(settings.volume / 100) 
        pygame.mixer.music.play(loops)
    except pygame.error as e:
        print(f"[audio] play failed: {e}")

def music_set_volume():
    """Apply current settings.volume to the mixer."""
    try:
        pygame.mixer.music.set_volume(settings.volume / 100)  
    except pygame.error as e:
        print(f"[audio] set_volume failed: {e}")

def music_pause():
    """Pause only if actually playing."""
    try:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
    except pygame.error as e:
        print(f"[audio] pause failed: {e}")

def music_unpause():
    """Resume only if paused (not if stopped)."""
    try:
        pygame.mixer.music.unpause()
    except pygame.error as e:
        print(f"[audio] unpause failed: {e}")

def music_stop():
    """Stops music."""
    try:
        pygame.mixer.music.stop()
    except pygame.error as e:
        print(f"[audio] stop failed: {e}")

def music_restart():
    """Restart from beginning (used on game-over → restart)."""
    try:
        pygame.mixer.music.rewind()
        pygame.mixer.music.play(-1)
    except pygame.error as e:
        print(f"[audio] restart failed: {e}")

def get_profile_name(screen, clock):
    """Render a name-entry screen and return the typed string when the player presses Enter."""
    name = ""
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and name.strip():
                    return name.strip()
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif len(name) < 16:
                    name += event.unicode

        screen.fill((20, 20, 20))
        label      = font_big.render("Enter Your Name:", True, text_color)
        input_surf = font_big.render(name + "|", True, input_color)
        hint       = font_small.render("Press ENTER to confirm", True, text_passive)

        screen.blit(label,      label.get_rect(center=(cx, cy - 60)))
        screen.blit(input_surf, input_surf.get_rect(center=(cx, cy)))
        screen.blit(hint,       hint.get_rect(center=(cx, cy + 50)))

        pygame.display.flip()
        clock.tick(fps)


def load_profile(profile_name):
    """Return the profile dict from replays/<profile_name>/profile.json, or None if not found."""
    path = os.path.join("replays", profile_name, "profile.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


# setup
screen  = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption(title)
clock   = pygame.time.Clock()
assets  = load_assets(screen_width, screen_height)
manager = pygame_gui.UIManager((screen_width, screen_height))
tutorial   = None
simulation = None
render     = renderer(screen)
handler    = EventHandler(manager)

menus = {
    "main":       MainMenu(manager, assets),
    "game_over":  GameOverMenu(manager),
    "pause":      PauseMenu(manager),
    "settings":   SettingsMenu(manager),
    "level":      LevelUpMenu(manager),
    "input_menu": InputMenu(manager)
}
menus["input_menu"].show()
state       = "input_menu"
dt          = 0
back_state  = None
paused_from = None
last_mode   = "playing"
game = None
# Transisiton handler
while state != "quit":

    if state == "tutorial" or (state == "level" and last_mode == "tutorial"):
        new_state = handler.process(state, menus, tutorial.player.pos, tutorial.player, paused_from, tutorial=tutorial)
    else:
        current_player = getattr(game, "player", None)
        new_state = handler.process(state, menus, None, current_player, paused_from)

    if new_state == "quit":
        state = "quit"

    # main → playing
    if state == "main" and new_state == "playing":
        music_play(-1)
        menus["main"].hide()
        game.reset()
        last_mode = "playing"
        state = "playing"
        continue

    if new_state != state:
        
        # main → simulation
        if state == "main" and new_state == "simulation":
            simulation = Simulation(profile_name=settings.profile_name)
            menus["main"].hide()
            simulation.reset()
            state = "simulation"
            continue

        # main → tutorial
        if state == "main" and new_state == "tutorial":
            music_play(-1)
            tutorial = Tutorial(profile_name=settings.profile_name)
            menus["main"].hide()
            tutorial.reset()
            last_mode = "tutorial"
            state = "tutorial"
            continue

        # playing → pause
        if state == "playing" and new_state == "pause":
            music_pause()
            paused_from = "playing"
            menus["pause"].show()
            state = "pause"
            continue

        # input_menu → main
        if state == "input_menu" and new_state == "main":
            build_types()
            profile_name, saved_profile = init_profile()
            game = Game(profile_name=profile_name)
            menus["input_menu"].hide()
            menus["main"].show()
            state = "main"
            continue

        # tutorial → pause
        if state == "tutorial" and new_state == "pause":
            music_pause()
            paused_from = "tutorial"
            menus["pause"].show()
            state = "pause"
            continue

        # pause → playing
        if state == "pause" and new_state == "playing":
            paused_from = None
            music_unpause()
            menus["pause"].hide()
            state = "playing"
            continue

        # pause → tutorial
        if state == "pause" and new_state == "tutorial":
            paused_from = None
            music_unpause()
            menus["pause"].hide()
            state = "tutorial"
            continue

        # main → settings
        if state == "main" and new_state == "settings":
            back_state = "main"
            menus["main"].hide()
            menus["settings"].show()
            state = "settings"
            continue

        # game_over → settings
        if state == "game_over" and new_state == "settings":
            back_state = "game_over"
            menus["game_over"].hide()
            menus["settings"].show()
            state = "settings"
            continue

        # pause → settings
        if state == "pause" and new_state == "settings":
            back_state = "pause"
            menus["pause"].hide()
            menus["settings"].show()
            state = "settings"
            continue

        # pause → main 
        if state == "pause" and new_state == "main":
            music_stop()
            paused_from = None
            menus["pause"].hide()
            menus["main"].show()
            state = "main"
            continue

        # settings → back
        if state == "settings" and new_state == "back":
            music_set_volume()  
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

        # playing → game_over
        if state == "playing" and new_state == "game_over":
            music_stop()
            try:
                game.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
            continue

        # tutorial → game_over
        if state == "tutorial" and new_state == "game_over":
            music_stop()
            try:
                tutorial.save_log()
            except Exception:
                traceback.print_exc()
            menus["game_over"].show()
            state = "game_over"
            continue

        # game_over → main
        if state == "game_over" and new_state == "main":
            menus["game_over"].hide()
            menus["main"].show()
            state = "main"
            continue

        # game_over → restart  (restart music from beginning)
        if state == "game_over" and new_state == "restart":
            music_restart()
            menus["game_over"].hide()
            game.reset()
            state = "playing"
            continue

        # level → playing / tutorial
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

        # simulation ↔ pause
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

    # update and draw
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
        if result:
            if result == "level":
                last_mode = "playing"
                menus["level"].show()
            state = result

    if state == "tutorial":
        locked_mouse = True
        pygame.event.set_grab(locked_mouse)
        result = tutorial.update(dt)
        if result == "game_over":
            locked_mouse = False
            pygame.event.set_grab(locked_mouse)
            music_stop()
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