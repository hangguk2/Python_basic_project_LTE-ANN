import pygame
from config import W, H, IMG_DIR
import os

# 전역 이미지들
main_map = None
collision_map = None
interact_map = None
wolf=None
sheep=None

def load_image(filename):
    full_path = os.path.join(IMG_DIR, filename)
    try:
        img = pygame.image.load(full_path).convert_alpha()
    except Exception as e:
        print("이미지 로드 실패:", full_path, e)
        img = pygame.Surface((32, 32), pygame.SRCALPHA)
        img.fill((255, 0, 255, 180))
    return img


def init_assets():
    """게임 시작 시 한 번만 호출해서 이미지 로드."""
    global main_map, collision_map, interact_map

    main_map = load_image("main_map.png")
    main_map = pygame.transform.smoothscale(main_map, (W, H))

    # 충돌 맵 (빨간색 영역 = 막힌 곳)
    global_collision = load_image("main_map_collision.png")
    collision_map_surface = pygame.transform.scale(global_collision, (W, H))

    # 상호작용 맵 (파란색 영역 = CCTV 상호작용)
    global_interact = load_image("main_map_interact.png")
    interact_map_surface = pygame.transform.scale(global_interact, (W, H))

    collision_map = collision_map_surface
    interact_map = interact_map_surface

def load_sheep(w):
    global sheep,wolf
    sheep = load_image("sheep.png")
    sheep = pygame.transform.smoothscale(sheep, (w, w*88//98))
    wolf = load_image("wolff.png")
    wolf = pygame.transform.smoothscale(wolf, (w, w*58//67))

def is_block_color(color):
    # 빨간색이면 막힌 구역
    r, g, b, *rest = color
    return r > 200 and g < 80 and b < 80


def is_interact_color(color):
    # 파란색이면 상호작용 구역
    r, g, b, *rest = color
    return b > 200 and r < 80 and g < 80


def rect_sample_points(rect):
    # 네 구석 + 중앙 5점
    return [
        rect.topleft,
        rect.topright,
        rect.bottomleft,
        rect.bottomright,
        rect.center,
    ]


def rect_hits_block(rect):
    """rect가 막힌 구역과 닿았는지 판정."""
    if collision_map is None:
        return False

    for (x, y) in rect_sample_points(rect):
        if x < 0 or x >= W or y < 0 or y >= H:
            continue
        color = collision_map.get_at((int(x), int(y)))
        if is_block_color(color):
            return True
    return False


def rect_hits_interact(rect):
    """rect가 상호작용(파란색) 구역과 닿았는지 판정."""
    if interact_map is None:
        return False

    for (x, y) in rect_sample_points(rect):
        if x < 0 or x >= W or y < 0 or y >= H:
            continue
        color = interact_map.get_at((int(x), int(y)))
        if is_interact_color(color):
            return True
    return False
