import pygame
import os
import settings
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class sound_effects:
    def __init__(self, filename):
        """initialize the sound effects"""
        path = os.path.join(BASE_DIR, "assets", "audio", filename)
        if not os.path.exists(path):
            print(f"[sfx] not found: {path}")
            self.sound = None
        else:
            try:
                self.sound = pygame.mixer.Sound(path)
            except pygame.error as e:
                print(f"[sfx] failed to load {filename}: {e}")
                self.sound = None

    def play(self, volume=1.0):
        """play sound effect instance"""
        if self.sound is None:
            return
        try:
            self.sound.set_volume((settings.volume / 100) * volume)
            self.sound.play()
        except pygame.error as e:
            print(f"[sfx] play failed: {e}")


class Music:
    def __init__(self):
        """initialize the music"""
        path = os.path.join(BASE_DIR, "assets", "audio", "music.ogg")
        if not os.path.exists(path):
            path = os.path.join(BASE_DIR, "assets", "audio", "In Dreamland by Chillpeach.mp3")
        self.path = path if os.path.exists(path) else None

    def play(self, loops=-1):
        """plays the music in a loop"""
        if self.path is None:
            return
        try:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(self.path)
            pygame.mixer.music.set_volume(settings.volume / 100)
            pygame.mixer.music.play(loops)
        except pygame.error as e:
            print(f"[music] play failed: {e}")

    def set_volume(self):
        """gets the volume level from settings"""
        try:
            pygame.mixer.music.set_volume(settings.volume / 100)
        except pygame.error as e:
            print(f"[music] set_volume failed: {e}")

    def pause(self):
        """pauses music"""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
        except pygame.error as e:
            print(f"[music] pause failed: {e}")

    def unpause(self):
        """unpauses music"""
        try:
            pygame.mixer.music.unpause()
        except pygame.error as e:
            print(f"[music] unpause failed: {e}")

    def stop(self):
        """stops music"""
        try:
            pygame.mixer.music.stop()
        except pygame.error as e:
            print(f"[music] stop failed: {e}")

    def restart(self):
        """restarts music"""
        try:
            pygame.mixer.music.rewind()
            pygame.mixer.music.play(-1)
        except pygame.error as e:
            print(f"[music] restart failed: {e}")

def load_assets():
    """loads sound effect files"""
    return {
        "shoot_sfx": sound_effects("47313572-ui-pop-sound-316482.mp3"),
        "death_sfx": sound_effects("floraphonic-happy-pop-2-185287.mp3"),
    }