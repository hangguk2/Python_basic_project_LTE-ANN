import os

# 화면 크기
W, H = 1200, 900

# FPS
FPS = 60

# 버튼 크기
BUTTON_W, BUTTON_H = 240, 60
BUTTON_MARGIN = 20

# 게임 시간 (실제 3분 -> 7:00~17:00)
GAME_DURATION = 180 # 180(초)
GAME_START_HOUR = 7
GAME_END_HOUR = 17

# assets 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "assets", "images")
