import pygame


# 여러 줄 텍스트를 화면 중심을 기준으로 자연스럽게 배치하는 흐름
# 줄 수에 맞춰 전체 높이를 계산하고 중심 y좌표에서 위아래로 나눠 그리는 방식
def draw_text_center(surface, text, font, color, center_pos):
    lines = text.split("\n")
    total_height = len(lines) * font.get_linesize()
    start_y = center_pos[1] - total_height // 2
    for i, line in enumerate(lines):
        surf = font.render(line, True, color)
        rect = surf.get_rect(center=(center_pos[0], start_y + i * font.get_linesize()))
        surface.blit(surf, rect)


# 사각형 내부에 여러 줄 텍스트를 넣을 때
# 전체 줄 높이를 맞추고 정렬 방식에 따라 좌우 위치를 다르게 배치하는 과정
def draw_multiline_rect(surface, text, font, color, rect, align="center"):
    lines = text.split("\n")
    x, y, w, h = rect
    line_height = font.get_linesize()
    total_height = len(lines) * line_height
    start_y = y + (h - total_height) // 2
    for i, line in enumerate(lines):
        surf = font.render(line, True, color)
        text_rect = surf.get_rect()
        if align == "center":
            text_rect.centerx = x + w // 2
        elif align == "left":
            text_rect.x = x + 10
        text_rect.y = start_y + i * line_height
        surface.blit(surf, text_rect)


# 버튼을 그릴 때 마우스 오버 여부에 따라 색을 바꾸고
# 배경과 테두리를 먼저 그린 뒤 텍스트를 중앙에 올리는 기본 구조
def draw_button(surface, rect, text, font, is_hover=False,base_color=(70,70,90),hover_color=(100,100,140)):

    color = hover_color if is_hover else base_color
    pygame.draw.rect(surface, color, rect, border_radius=10)
    pygame.draw.rect(surface, (200, 200, 220), rect, 2, border_radius=10)
    text_surf = font.render(text, True, (255, 255, 255))
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)