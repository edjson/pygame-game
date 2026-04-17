import pygame
pygame.init()

# screen 
screen_width             = 1280
screen_height            = 720

# button variables
cx                       = screen_width // 2
cy                       = screen_height // 2
thirds                   = screen_height // 3
button_width             = 200
button_height            = 60
cbutton_width            = button_width // 2
cbutton_height           = button_height // 2
bar_w                    = 50
bar_h                    = 5

#text
title                    = "adaptive ememy player analysis"
describe                 = "creating model human profiles to for machine learning enemies"
transparent              = (0,0,0,180)
background               = "black"
text_color               = "white"
input_color              = "yellow"
text_passive             = "grey"
font_big                 = pygame.font.SysFont("consolas", 32)
font_small               = pygame.font.SysFont("consolas", 12)

# player
player_projectile_color  = "cyan"
warning_radius           = 180
player_radius            = 20
player_speed             = 300
player_health            = 100
player_damage            = 10
player_next              = 5
player_xpRate            = 1.5
player_regen             = 5
player_projectile_radius = 8
fire_rate                = 0.8
min_cooldown             = 50
max_cooldown             = 1000
profile_name             = "default_profile"   

# enemy
enemy_projectile_color   = "magenta"
enemies_count_rate       = 1.2
margin                   = 50
spawn_decay_rate         = 0.85
min_spawn_delay          = 0.2
current_spawn_delay      = 3
wall_penalty_margin      = 80 
detection_radius         = 300

# game variables
color_health_bar         = "green"
color_health_bg          = "red"
fps                      = 60 
projectile_speeds        = 500
record                   = 0
volume                   = 50
color_options            = ["red", "orange", "yellow", "green", "blue", "indigo", "violet"]
