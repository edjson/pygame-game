import random
import settings

types = []
spriteCache = {}

def build_types():
    """Call this after the player picks their color in input_menu. Shuffles the remaining colors and assigns one to each enemy type."""

    colors = settings.color_options[:] 
    random.shuffle(colors)
    while len(colors) < 6:
        colors.append(random.choice(colors))
    types.clear()
    types.extend([
        {"name": "Scout",       "color": colors[0], "hp": 30,  "damage": 5,  "speed": 190, "radius": 10, "proj_radius": 5,  "fire_rate": 7, "xp": 1, "sprite": "assets/sprites/Enemy1.png"},
        {"name": "Tank",        "color": colors[1], "hp": 150, "damage": 20, "speed": 35,  "radius": 60, "proj_radius": 15, "fire_rate": 1, "xp": 5, "sprite": "assets/sprites/Enemy3.png"},
        {"name": "Skirmisher",  "color": colors[2], "hp": 80,  "damage": 10, "speed": 95,  "radius": 20, "proj_radius": 5,  "fire_rate": 4, "xp": 2, "sprite": "assets/sprites/Enemy7.png"},
        {"name": "Glass Cannon","color": colors[3], "hp": 20,  "damage": 25, "speed": 135, "radius": 10, "proj_radius": 15, "fire_rate": 1, "xp": 3, "sprite": "assets/sprites/Enemy4.png"},
        {"name": "Bruiser",     "color": colors[4], "hp": 110, "damage": 10, "speed": 75,  "radius": 40, "proj_radius": 5,  "fire_rate": 5, "xp": 3, "sprite": "assets/sprites/Enemy5.png"},
        {"name": "Assassin",    "color": colors[5], "hp": 45,  "damage": 15, "speed": 155, "radius": 15, "proj_radius": 5,  "fire_rate": 3, "xp": 2, "sprite": "assets/sprites/Enemy6.png"},
        {"name": "tutorial",    "color": colors[0], "hp": 100, "damage": 5,  "speed": 5,   "radius": 30, "proj_radius": 1,  "fire_rate": 0, "xp": 0, "sprite": "assets/sprites/Enemy2.png"},
    ])