import pygame
from assets import load_image, rect_hits_block
from config import FPS


class Player:
    def __init__(self, x, y):
        # 7:1 스케일
        def scale_15to1(img): #여기서 변수 이름 실수로 15to1이지만 실제로는 7to1입니다 ㅎㅎ
            w, h = img.get_size()
            return pygame.transform.smoothscale(
                img,
                (max(1, w // 7), max(1, h // 7))
            )

        self.images = {
            "down": scale_15to1(load_image("juingong_down.png")),
            "up": scale_15to1(load_image("juingong_up.png")),
            "left": scale_15to1(load_image("juingong_left.png")),
            "right": scale_15to1(load_image("juingong_right.png")),
        }

        self.direction = "down"
        self.image = self.images[self.direction]
        # self.rect = self.image.get_rect(center=(x, y))
        # print(self.rect)
        # self.rect.top+=50
        self.rect=pygame.rect.Rect(586,472,28,4)
        print(self.rect)
        self.speed = 9000//FPS  # px/s

    def update(self, dt, keys, screen_rect):
        vx = 0
        vy = 0

        # 방향키로만 이동
        if keys[pygame.K_LEFT]:
            vx = -self.speed
            self.direction = "left"
        elif keys[pygame.K_RIGHT]:
            vx = self.speed
            self.direction = "right"

        if keys[pygame.K_UP]:
            vy = -self.speed
            self.direction = "up"
        elif keys[pygame.K_DOWN]:
            vy = self.speed
            self.direction = "down"

        # x축 이동 시도
        if vx != 0:
            new_rect = self.rect.move(vx * dt, 0)
            if not rect_hits_block(new_rect):
                self.rect = new_rect

        # y축 이동 시도
        if vy != 0:
            new_rect = self.rect.move(0, vy * dt)
            if not rect_hits_block(new_rect):
                self.rect = new_rect

        # 화면 밖 방지
        self.rect.clamp_ip(screen_rect)

        self.image = self.images[self.direction]

    def draw(self, surface):
        surface.blit(self.image, (self.rect.x, self.rect.y-45))
