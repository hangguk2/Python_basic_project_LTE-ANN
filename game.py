import pygame
import sys
import numpy as np
from random import random,randrange,randint
from config import (
    W, H,
    FPS,
    BUTTON_W, BUTTON_H, BUTTON_MARGIN,
    GAME_DURATION, GAME_START_HOUR, GAME_END_HOUR,
)
import assets
from assets import rect_hits_interact, load_image
from player import Player
from ui import draw_text_center, draw_multiline_rect, draw_button


# =====================================================================
# 게임 내 시간 계산을 담당하는 클래스
# 실제 경과 시간(game_minutes)을 게임 속 시:분(7:00~17:00)으로 변환하는 역할만 맡는다.
# 기존 Game.get_game_clock_hm 로직을 그대로 옮겨 담았다.
# =====================================================================
class ClockSystem:
    def __init__(self):
        # 게임 내 흐른 시간(분 단위, 실수)
        self.game_minutes = 0.0

    def reset(self):
        # 새 게임을 시작할 때 시간을 처음으로 되돌린다.
        self.game_minutes = 0.0

    def get_hm(self):
        # 현재 game_minutes를 게임 속 시각(hour, minute)으로 변환한다.
        total_minutes_span = (GAME_END_HOUR - GAME_START_HOUR) * 60
        if total_minutes_span <= 0:
            return GAME_START_HOUR, 0
        m = self.game_minutes % total_minutes_span
        hour = GAME_START_HOUR + int(m) // 60
        minute = int(m) % 60
        return hour, minute


# =====================================================================
# 세로 게이지 바(심심도 / 신뢰도 / 생존율)를 그리는 클래스
# 화면 좌표와 색상 규칙만 보관하고, 실제 값은 그릴 때마다 넘겨받는다.
# 기존 draw_game 안에서 세 번 반복되던 게이지 그리기 코드를 하나로 묶은 것으로,
# 픽셀 계산식/색상 공식은 원본과 완전히 동일하다.
# =====================================================================
class GaugeBar:
    def __init__(self, label, x, y, fill_color_fn, bg_color, w=20, h=200):
        self.label = label            # 게이지 위에 표시할 이름
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.bg_color = bg_color      # 게이지 배경(빈 부분) 색
        self.fill_color_fn = fill_color_fn  # 현재 비율을 받아 채움 색을 돌려주는 함수

    def draw(self, surface, small_font, value, max_value):
        bar_w = self.w
        bar_h = self.h
        bar_x = self.x
        bar_y = self.y

        label = small_font.render(self.label, True, (230, 230, 230))
        surface.blit(label, label.get_rect(center=(bar_x + bar_w // 2, bar_y - 15)))

        pygame.draw.rect(surface, self.bg_color, (bar_x, bar_y, bar_w, bar_h))

        ratio = value / max_value if max_value > 0 else 0
        ratio = max(0.0, min(1.0, ratio))
        fill_h = int((bar_h - 4) * ratio + 4)

        if fill_h > 0:
            fill_rect = pygame.Rect(
                bar_x + 2,
                bar_y + bar_h - fill_h + 2,
                bar_w - 4,
                fill_h - 4
            )
            pygame.draw.rect(surface, self.fill_color_fn(value, max_value), fill_rect)

        bd_text = small_font.render(f"{int(value / max_value * 100)}%", True, (230, 230, 230))
        surface.blit(bd_text, bd_text.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h + 15)))


# =====================================================================
# CCTV 화면에 등장하는 양/늑대 무리를 관리하는 클래스
# 무리 생성(maintain), 이동(move), 그리기(blit)를 담당한다.
# sheep 리스트의 각 항목 구조와 난수/속도/조건식은 원본 로직을 그대로 옮겼다.
# 늑대가 오래 방치되면 game에 신고(3번)를 요청해야 하므로 game 참조를 들고 있는다.
# =====================================================================
class Flock:
    def __init__(self, game):
        self.game = game
        # 양(늑대 포함) 리스트와 늑대 위치 리스트
        self.sheep = []
        self.wolf_location = []

    def clear(self):
        # 무리 정보를 비운다(신고 후/새 게임 시작 시 사용).
        self.sheep = []
        self.wolf_location = []

    def maintain(self, cctvcount_x, cctvcount_y, cctvw, cctvh, surv, max_surv):
        # cctv 화면마다 일정 수의 양을 유지하려는 관리 루프, 생존율에 따라 총 양 수가 달라지고
        # 부족한 만큼만 새 양을 생성해서 화면에 자연스럽게 채우는 구조
        while len(self.sheep) < cctvcount_x * cctvcount_y * 6 * surv / max_surv:
            # 왼쪽오른쪽위아래에서 등장 방향을 결정하기 위한 난수, 양이 어느 방향에서 들어올지 정하는 역할
            r = random() * .8
            w, xx, yy = (random() < 1 / (cctvcount_x * cctvcount_y * 30)), randrange(cctvcount_x), randrange(cctvcount_y)
            # 아래 조건문들은 등장 방향별 초기 위치와 이동 속도를 랜덤으로 다르게 주어
            # 화면마다 양이 자연스럽게 흘러 들어오는 느낌을 만드는 흐름
            if r < .2:
                self.sheep.append([xx,
                                   yy,
                                   randrange(-cctvw // 3, -cctvw // 6),
                                   randrange(cctvh // 4, cctvh * 3 // 4),
                                   randrange(150, 300) / 100,
                                   randrange(100) * (1 if random() < .5 else -1) / 100,
                                   randrange(3 * FPS, 4 * FPS),
                                   w,
                                   randrange(FPS // 2, FPS // 3 * 2),
                                   0, 10 * FPS])
            elif r < .4:
                self.sheep.append([xx,
                                   yy,
                                   randrange(cctvw * 7 // 6, cctvw * 4 // 3),
                                   randrange(cctvh // 4, cctvh * 3 // 4),
                                   randrange(-300, -150) / 100,
                                   randrange(100) * (1 if random() < .5 else -1) / 100,
                                   randrange(3 * FPS, 4 * FPS),
                                   w,
                                   randrange(FPS // 2, FPS // 3 * 2),
                                   0, 10 * FPS])
            elif r < .6:
                self.sheep.append([xx,
                                   yy,
                                   randrange(cctvw // 4, cctvw * 3 // 4),
                                   randrange(-cctvh // 3, -cctvh // 6),
                                   randrange(100) * (1 if random() < .5 else -1) / 100,
                                   randrange(150, 300) / 100,
                                   randrange(3 * FPS, 4 * FPS),
                                   w,
                                   randrange(FPS // 2, FPS // 3 * 2),
                                   0, 10 * FPS])
            elif r < .8:
                self.sheep.append([xx,
                                   yy,
                                   randrange(cctvw // 4, cctvw * 3 // 4),
                                   randrange(cctvh * 7 // 6, cctvh * 4 // 3),
                                   randrange(100) * (1 if random() < .5 else -1) / 100,
                                   randrange(-300, -150) / 100,
                                   randrange(3 * FPS, 4 * FPS),
                                   w,
                                   randrange(FPS // 2, FPS // 3 * 2),
                                   0, 10 * FPS])
            if w:
                self.wolf_location.append(xx + yy * cctvcount_y + 1)
            # [a,b,c,d,e,...]라하면
            # (a,b)위치의 cctv에서 (c,d)좌표에 배치한다.
            # (e,f)속도로 이동한다.
            # g는 남은 랜덤이동 쿨타임이다.
            # h=1이면 늑대다.
            # i는 남은 늑대이상행동 쿨타임이다.
            # j는 현재 이상행동 여부이다.

    def move(self, cctvw, cctvh):
        # 양과 늑대가 화면 안에서 계속 움직이도록 하는 핵심 이동 함수
        # 각각의 이동 속도와 남은 이동 시간 등을 갱신하면서 상태 변화도 함께 처리
        for i, sheeep in enumerate(self.sheep):
            # 화면 비율에 따라 이동량을 보정해서 각 화면 크기 변화에도 자연스럽게 이동하도록 설정
            sheeep[2] += sheeep[4] * cctvw / W
            sheeep[3] += sheeep[5] * cctvh / H
            sheeep[6] -= 1
            # 늑대일 때는 이상 행동 타이머도 동시에 감소
            if sheeep[7]:
                sheeep[8] -= 1
                sheeep[10] -= 1
            if sheeep[6] < 0:
                sheeep[4], sheeep[5], sheeep[6] = (randrange(200, 400) * (1 if random() < .5 else -1) / 100,
                                                   randrange(200, 400) * (1 if random() < .5 else -1) / 100,
                                                   randrange(1 * FPS, 3 * FPS))
            # 늑대일 때 이상 행동을 일정 주기로 반복하거나 멈추도록 하는 패턴
            if sheeep[7] and sheeep[8] < 0:
                if sheeep[9]:
                    sheeep[9] = 0
                    sheeep[8] = randrange(FPS * 2, FPS * 5)
                else:
                    sheeep[9] = 1
                    sheeep[8] = randrange(FPS // 10, FPS // 5)
            if sheeep[7] and sheeep[10] < 0:
                self.game.paused = True
                self.game.start_report(3)
            # 일반 양이 화면 범위를 벗어나면 자연스럽게 삭제해서 화면 정리
            if sheeep[7] == 0 and (sheeep[2] > cctvw * 3 / 2 or sheeep[3] > cctvh * 3 / 2 or sheeep[2] < -cctvw / 2 or sheeep[3] < -cctvh / 2):
                del self.sheep[i]

    def blit(self, cctvies):
        for i, sheeep in enumerate(self.sheep):
            cctvies[sheeep[0]][sheeep[1]].blit((assets.wolf if sheeep[9] else assets.sheep), (sheeep[2], sheeep[3]))


class Game:
    def __init__(self):
        pygame.init()

        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("뭘봐")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font('assets/fonts/malgun.ttf', 28)
        self.small_font = pygame.font.Font('assets/fonts/malgun.ttf', 20)
        self.lesson_font = pygame.font.Font('assets/fonts/malgunbd.ttf', 32)
        self.cctv_font = None
        self.small_cctv_font = pygame.font.Font('assets/fonts/font.ttf', 40)

        # 이미지 로드
        assets.init_assets()

        self.menu_bg = load_image("menu_background.png")
        self.menu_bg = pygame.transform.smoothscale(self.menu_bg, (W, H))
        # 상태들
        # intro, menu, settings_popup, notice_popup,
        # story, dialog, game, cctv,
        # ending_dialog, ending_lesson
        self.ingame=False #인게임 여부
        self.paused=False #인게임 시간 일시정지 여부 (신고 또는 늑대 습격 시 dialog 발생할 때)
        self.sheepsheep=30 # 양 소환 시작 시간
        self.current_screen = "intro"
        self.current_level = 1
        self.min_level = 1
        self.max_level = 10

        self.game_elapsed = 0.0
        # 게임 내 시간(분)은 별도의 ClockSystem이 관리한다.
        self.clock_system = ClockSystem()

        # 심심도
        self.boredom = 0.0
        self.max_boredom = 100.0

        # 신뢰도
        self.rely = 90.0
        self.max_rely = 100.0

        # 양 생존율
        self.surv = 100.0
        self.max_surv = 100.0
        #배경음 초기화
        pygame.mixer.init()
        self.current_bgm = None

        self.story_lines = [
            "양치기 소년들은 시간이 흐르고 세대를 거쳐",
            "어느덧 21세기,\n양치기 소년들은 여전히 양을 돌보고 있다",
            "기술의 발전으로 요즘은\nCCTV로 늑대가 오는 지 아닌지를 감시한다고 한다",
            "그러나, 소년의 거짓말은 여전히 줄지를 않는데.."
        ]
        self.story_index = 0

        # 대화씬 스크립트
        self.dialog_script = [
            ("서하찮-주인공", "유후 드디어 양치기 소년으로서의 첫날!!\n너무 기대된다!!"),
            ("영포티-빡친 농부", "너, 처음 보는 얼굴이군.\n혹시 너가 이번에 새로 온 양치기 소년?"),
            ("서하찮-주인공", "맞아요ㅎㅎ너무 기대돼요.\n저 양들을 돌보는 것을 엄청 좋아하거든요"),
            ("영포티-빡친 농부", "그래? 좋네.\n다만 너희 아버지처럼 늑대가 왔다는 거짓말을 하진 않았으면.."),
            ("서하찮-주인공", "에엥? 저는 절대 안 그럴 거에요!\n양들을 돌보고 늑대를 감시하며 살 거에요!"),
            ("영포티-빡친 농부", "휴우.. 이번에 새로 왔으니까 믿어봐야지..\n이번에는 우리 마을 사람들이 고생을 하진 않겠지..?"),
            ("서하찮-주인공", "(혼잣말) 아 근데 좀 심심할 것 같긴 한데.."),
            ("영포티-빡친 농부", "지금부터 30분 후부터 양들이 올 것이니 잘 지키고 있어라!"),
            ("서하찮-주인공", "알겠습니다!!"),
        ]
        self.dialog_speaker_side = {
            "서하찮-주인공": "left",
            "영포티-빡친 농부": "right",
        }
        self.dialog_index = 0

        # 대화용 이미지
        self.story_background = load_image("background_side.png")
        self.story_background = pygame.transform.smoothscale(self.story_background, (W, H))

        self.story_character = load_image("juingong_down.png")
        self.story_character = pygame.transform.smoothscale(self.story_character, (260, 360))
        self.story_farmer = load_image("youngforty.png")
        self.story_farmer = pygame.transform.smoothscale(self.story_farmer, (260, 360))

        # 마을 회관 위치 (중앙 큰 집 좌표)
        # 이미지 기준 중앙집 문 위치에 맞게 Rect 생성
        self.townhall_rect = pygame.Rect(0, 0, 90, 90)
        self.townhall_rect.center = (W // 2, 300)

        # 설명서(3페이지)
        self.manual_pages = [
            {
                "text": (
                    "1. 게임 목표\n\n"
                    "- 마을 회관에 놓아진 CCTV를 활용하여\n"
                    "- 사람들의 당신에 대한 신뢰도를 지키면서\n"
                    "  양들 사이에 숨은 늑대를 감시하며 양들을 지켜냅니다.\n"
                    "- 플레이어의 심심도가 너무 높아지지 않도록\n"
                    "  각 집에서 나오는 물약을 잘 활용하세요."
                ),
                # 이미지 없음 → None
                "image": None,
            },
            {
                "text": (
                    "2. 조작법\n\n"
                    "- 방향키: 이동\n"
                    "- A 키: 상호작용 (CCTV / 집 문)\n"
                    "- ESC: 메뉴로 돌아가기\n\n"
                    "※ 마을 회관 근처에서 A를 누르면 CCTV 화면으로,\n"
                    "   집 문 근처에서 A를 누르면 물약을 얻을 수 있습니다."
                ),
                "image": load_image("manual2.png"),
            },
            {
                "text": (
                    "3. CCTV\n\n"
                    "- CCTV를 통해 각 마을의 어디 부분에 늑대가 있는지 발견하고,\n"
                    "  늑대가 등장함을 신고합니다.\n"
                    "- 늑대가 양들 사이에 몰래 등장할 수 있으니 조심하세요.\n"
                    "- 거짓 신고도 가능하니, 신뢰를 잃지 않도록 선택해야 합니다."
                ),
                "image":  load_image("manual4.png"),
            },
            {
                "text": (
                    "4. 심심도 / 물약\n\n"
                    "- 심심도는 시간에 따라 서서히 증가합니다. 레벨이 높아질수록 더 빠르게 증가합니다.\n"
                    "- 집 문에서 얻는 물약을 먹으면 심심도가 30~50 감소합니다. 레벨이 높아질수록 수치는 감소합니다.\n"
                    "- 각 집은 6시간마다 물약을 하나씩 리필합니다.\n"
                    "  (대기 시간 동안 문 근처에 가면 남은 시간을 확인할 수 있습니다.)\n"
                    "- CCTV에서 정확한 신고를 할 시 심심도가 50 감소합니다!\n"
                    "- CCTV에서 거짓 신고를 하면 심심도가 0으로 초기화됩니다!!"
                ),
                "image": load_image("manual3.png"),
            },
            {
                "text": (
                    "5. 신뢰도 / 생존율\n\n"
                    "- CCTV에서 정확한 신고를 하면, 신뢰도가 상승합니다!\n"
                    "- CCTV에서 거짓 신고를 하면, 신뢰도가 감소합니다.\n"
                    "- 아예 늑대를 검거하지 못할 경우, 신뢰도가 대폭 감소합니다.\n"
                    "  또한 늑대를 검거하지 못한 경우 양의 생존률이 크게 감소하므로 주의하세요!\n\n\n"
                    "행운을 빕니다."
                ),
                "image": None,
            },
        ]
        self.manual_page_index = 0
        self.manual_rect = pygame.Rect((W - 1000) // 2, (H - 750) // 2, 1000, 750)
        self.notice_text = "게임 설명서"

        self.report_state = None # None / "ok" / "fail" / "wolf"
        # 게임 중간 dialog
        self.report_capture_sheep = [
            ("영포티-빡친 농부", "고맙다! 덕분에 늑대를 잡았다. 양이 모두 살아있군."),
            ("서하찮-주인공", "제가 진짜 위험할 때만\n진실만 말한다고 했죠ㅎㅎ"),
            ("영포티-빡친 농부", "양은 15분 후부터 다시 몰 게다."),
        ]

        self.report_lose = [
            ("영포티-빡친 농부", "늑대가 없잖아!"),
            ("서하찮-주인공", "전 있는 줄 알았어요;;"),
            ("영포티-빡친 농부", "핑계 그만! 이번은 봐줄 테니\n앞으로 다시는 거짓말 하지 말아라."),
            ("영포티-빡친 농부", "양은 15분 후부터 다시 몰 게다."),
        ]

        self.report_lose_wolf = [
            ("영포티-빡친 농부", "늑대를 못 잡았잖아! 많은 양들이 죽었어."),
            ("서하찮-주인공", "전 없는 줄 알았어요;;"),
            ("영포티-빡친 농부", "핑계 그만! 이번은 봐줄 테니\n앞으로 다시는 거짓말 하지 말아라."),
            ("영포티-빡친 농부", "양은 15분 후부터 다시 몰 게다."),
        ]

        self.report_script = None
        self.report_bg = load_image("moravian-tuscany-kyjov-ma-eul-geuncheo-molabia-nambuui-aleumdaun-bom-pung-gyeong-cheko-e.jpg")

        self.report_speaker_side = {
            "서하찮-주인공": "left",
            "영포티-빡친 농부": "right",
        }
        # 엔딩 관련 ---------------------------------
        self.ending_state = None # None / "win" / "lose"
        self.ending_bg_win = load_image("background_win.png")
        self.ending_bg_win = pygame.transform.smoothscale(self.ending_bg_win, (W, H))
        self.ending_bg_lose = load_image("background_lose.png")
        self.ending_bg_lose = pygame.transform.smoothscale(self.ending_bg_lose, (W, H))

        self.ending_dialog_win = [
            ("영포티-빡친 농부", "오늘도 늑대는 오지 않았구나.\n그래도 네 덕분에 모두 안심하고 지냈다."),
            ("서하찮-주인공", "당연하죠! 거짓말은 안 하고,\n대신 제대로 감시만 열심히 했으니까요."),
            ("영포티-빡친 농부", "그래, 사람들은 이제 네 말을 믿기 시작했어.\n신뢰를 쌓는다는 건 그런 거란다."),
            ("서하찮-주인공", "앞으로도 진짜 위험할 때만\n진실만 말할게요!"),
        ]
        self.ending_dialog_win_wolf = [
            ("영포티-빡친 농부", "늑대를 잘 잡아주었구나.\n네 덕분에 모두 안심하고 지냈다."),
            ("서하찮-주인공", "당연하죠! 거짓말은 안 하고,\n대신 제대로 감시만 열심히 했으니까요."),
            ("영포티-빡친 농부", "그래, 사람들은 이제 네 말을 믿기 시작했어.\n신뢰를 쌓는다는 건 그런 거란다."),
            ("서하찮-주인공", "앞으로도 진짜 위험할 때만\n진실만 말할게요!"),
        ]
        self.ending_dialog_lose = [
            ("영포티-빡친 농부", "사람들에게 원성이 자자하다.\n아무래도 나가주어야 할 것 같다."),
            ("서하찮-주인공", "그냥 심심해서 장난친 것뿐인데,\n이렇게 큰 일이 될 줄은..."),
            ("영포티-빡친 농부", "신뢰는 잃기는 쉽지만,\n다시 얻기는 아주 어렵단다."),
        ]
        self.ending_dialog_lose_sheep = [
            ("서하찮-주인공", "진짜 늑대가 왔다고 말했는데...\n아무도 안 믿어줬어..."),
            ("영포티-빡친 농부", "네가 평소에 한 거짓말들이\n사람들의 귀를 막아버린 거야."),
            ("서하찮-주인공", "그냥 심심해서 장난친 것뿐인데,\n이렇게 큰 일이 될 줄은..."),
            ("영포티-빡친 농부", "신뢰는 잃기는 쉽지만,\n다시 얻기는 아주 어렵단다."),
        ]
        self.ending_dialog_bored = [
            ("영포티-빡친 농부", "어이, 정신 좀 차려라. 너 또 거짓말이라도\n하다 쓰러진 줄 알았는데… 이번엔 그런 것도 아니었구나."),
            ("서하찮-주인공", "거짓말은 정말 안 하려고 했어요…\n진짜로 열심히 지키고 있었는데…"),
            ("서하찮-주인공", "혼자 감당하려다 보니까 너무…\n지쳐버렸네요…"),
            ("영포티-빡친 농부", "그래, 이번엔 네가 거짓말 하나 없이\n최선을 다했다는 걸 다들 알고 있다."),
            ("영포티-빡친 농부", "우리도 너를 도와주려고 했던 거고."),
            ("영포티-빡친 농부", "그러니 이제 혼자 버티려 하지 마라.\n아무리 성실한 사람이라도… 마음이 지치면 쓰러지는 법이니까."),
        ]
        self.active_ending_script = None
        self.active_ending_bg = None
        self.ending_dialog_index = 0

        self.ending_lesson_text_win = (
            "거짓말을 하지 않아도,\n사람들은 결국 당신을 믿게 됩니다.\n\n"
            "신뢰는 한순간의 장난이 아니라,\n조금씩 쌓아 올리는 선택입니다."
        )
        self.ending_lesson_text_lose = (
            "거짓말은 한 번의 장난으로 끝나지 않습니다.\n\n"
            "신뢰를 잃어버리면,\n아무리 진실을 외쳐도 아무도 듣지 않습니다."
        )
        self.ending_lesson_text = ""
        self.lesson_start_time = 0.0
        self.lesson_speed = 20.0  # 초당 글자 수

        # 인트로 버튼
        self.intro_button = pygame.Rect(0, 0, 260, 90)
        self.intro_button.center = (W // 2, H - 160)

        # 메뉴 버튼들
        self.menu_buttons = {
            "level": pygame.Rect((W // 2 - BUTTON_W // 2, 300), (BUTTON_W, BUTTON_H)),
            "notice": pygame.Rect((W // 2 - BUTTON_W // 2, 300 + (BUTTON_H + BUTTON_MARGIN)), (BUTTON_W, BUTTON_H)),
            "start": pygame.Rect((W // 2 - BUTTON_W // 2, 300 + 2 * (BUTTON_H + BUTTON_MARGIN)), (BUTTON_W, BUTTON_H)),
        }
        self.menu_back_button = pygame.Rect(W // 2 - 80,
                                            300 + 3 * (BUTTON_H + BUTTON_MARGIN) + 40,
                                            160, 40)

        # 설정 팝업
        self.popup_rect = pygame.Rect(W // 2 - 250, H // 2 - 150, 500, 300)

        self.settings_buttons = {
            "minus": pygame.Rect(self.popup_rect.x + 60, self.popup_rect.y + 140, 60, 40),
            "plus": pygame.Rect(self.popup_rect.x + 380, self.popup_rect.y + 140, 60, 40),
            "ok": pygame.Rect(self.popup_rect.x + 110, self.popup_rect.y + 220, 100, 40),
            "cancel": pygame.Rect(self.popup_rect.x + 290, self.popup_rect.y + 220, 100, 40),
        }

        # 설명서 버튼
        self.notice_buttons = {
            "prev": pygame.Rect(self.manual_rect.x + 200, self.manual_rect.bottom - 70, 120, 40),
            "next": pygame.Rect(self.manual_rect.right - 320, self.manual_rect.bottom - 70, 120, 40),
            "ok": pygame.Rect(self.manual_rect.centerx - 60, self.manual_rect.bottom - 70, 120, 40),
        }

        self.story_buttons = {
            "back": pygame.Rect(20, H - 70, 160, 40),
            "skip": pygame.Rect(W - 180, H - 70, 160, 40),
        }

        # CCTV 버튼
        self.cctv_buttons = {
            "back": pygame.Rect(20, H - 80, 150, 50),
            "report": pygame.Rect(W - 220, H - 80, 200, 50)
        }

        # 양 속성들
        # 양/늑대 무리는 별도의 Flock 객체가 관리한다.
        # (self.sheep / self.wolf_location 은 아래 property를 통해 Flock 내부 리스트를 가리킨다.)
        self.flock = Flock(self)
        self.sheepasset=None
        self.cctvcount_x = 2
        self.cctvcount_y = 2
        self.cctvgap = 10
        self.cctvw = 0
        self.cctvh = 0
        self.cctvies = []

        self.player = None
        self.can_interact_now = False

        # 문/물약 ----------------------------------------
        door_positions = [
            (215, 165),
            (260, 435),
            (315, 680),
            (837, 170),
            (1005, 190),
            (880, 475),
            (785, 670),
        ]

        self.door_rects = []
        self.door_size = (60, 60)
        for (x, y) in door_positions:
            r = pygame.Rect(0, 0, *self.door_size)
            r.center = (x, y)
            self.door_rects.append(r)

        self.door_image = load_image("door.png")

        self.door_interacted = [False] * len(self.door_rects)
        self.door_has_potion = [False] * len(self.door_rects)
        self.next_refill_minute = [0.0] * len(self.door_rects)

        self.moolyak_image = load_image("moolyak.png")
        base_size = 40
        new_size = int(base_size * 2 / 3)  # 2/3 크기
        self.moolyak_image = pygame.transform.smoothscale(self.moolyak_image, (new_size, new_size))
        self.moolyak_positions = [None] * len(self.door_rects)

        self.current_door_index = -1

        # 게이지 바들 (심심도 / 신뢰도 / 생존율)
        # 좌표·색상·채움 공식은 기존 draw_game 안에 있던 값과 동일하다.
        self.boredom_gauge = GaugeBar(
            "심심도", W - 60, 200,
            lambda v, m: (220 * v / m, 0, 0),
            (80, 80, 120),
        )
        self.rely_gauge = GaugeBar(
            "신뢰도", 40, 150,
            lambda v, m: (220 - 220 * v / m, 220 * v / m, 220),
            (80, 120, 80),
        )
        self.surv_gauge = GaugeBar(
            "생존율", 40, 500,
            lambda v, m: (220 - 220 * v / m, 220 * v / m, 0),
            (80, 120, 120),
        )

    # ----------------- 위임용 property -----------------
    # game_minutes / sheep / wolf_location 은 각각 ClockSystem, Flock 이 실제로 소유하지만
    # 기존 코드가 self.game_minutes 등으로 직접 접근하므로 property로 그대로 노출한다.
    @property
    def game_minutes(self):
        return self.clock_system.game_minutes

    @game_minutes.setter
    def game_minutes(self, value):
        self.clock_system.game_minutes = value

    @property
    def sheep(self):
        return self.flock.sheep

    @sheep.setter
    def sheep(self, value):
        self.flock.sheep = value

    @property
    def wolf_location(self):
        return self.flock.wolf_location

    @wolf_location.setter
    def wolf_location(self, value):
        self.flock.wolf_location = value

    # ----------------- 공통 유틸 -----------------
    def get_game_clock_hm(self):
        # 실제 시간 변환은 ClockSystem에 위임한다.
        return self.clock_system.get_hm()

    # ----------------- 인트로 -----------------
    def handle_intro_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.intro_button.collidepoint(e.pos):
                    self.current_screen = "menu"

    def draw_intro(self):
        self.screen.blit(self.menu_bg, (0, 0))

        title1 = self.font.render("양치기 소년", True, (0, 0, 0))
        title2 = self.small_font.render("[신뢰가 먼저다]", True, (0, 0, 0))
        self.screen.blit(title1, title1.get_rect(center=(W // 2, 160)))
        self.screen.blit(title2, title2.get_rect(center=(W // 2, 200)))

        mx, my = pygame.mouse.get_pos()
        hovered = self.intro_button.collidepoint(mx, my)

        base_color = (60, 120, 210)
        hover_color = (90, 150, 240)
        color = hover_color if hovered else base_color

        pygame.draw.rect(self.screen, color, self.intro_button, border_radius=15)
        pygame.draw.rect(self.screen, (20, 40, 80), self.intro_button, 3, border_radius=15)

        btn_text = self.small_font.render("플레이하기", True, (0, 0, 0))
        self.screen.blit(btn_text, btn_text.get_rect(center=self.intro_button.center))

    # ----------------- 메뉴 -----------------
    def handle_menu_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.menu_buttons["level"].collidepoint(mx, my):
                    self.current_screen = "settings_popup"
                elif self.menu_buttons["notice"].collidepoint(mx, my):
                    self.manual_page_index = 0
                    self.current_screen = "notice_popup"
                elif self.menu_buttons["start"].collidepoint(mx, my):
                    self.story_index = 0
                    self.game_elapsed = 0.0
                    self.game_minutes = 0.0
                    self.boredom = 0.0
                    self.current_screen = "story"
                elif self.menu_back_button.collidepoint(mx, my):
                    self.current_screen = "intro"


    def draw_menu(self):
        self.screen.blit(self.menu_bg, (0, 0))

        title = self.font.render("메인 메뉴", True, (0, 0, 0))
        self.screen.blit(title, title.get_rect(center=(W // 2, 150)))

        panel_w, panel_h = 420, 420
        panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
        panel_rect.center = (W // 2, H // 2 + 40)

        pygame.draw.rect(self.screen, (25, 25, 35), panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, (180, 180, 200), panel_rect, 2, border_radius=10)

        mx, my = pygame.mouse.get_pos()
        draw_button(self.screen, self.menu_buttons["level"], "레벨 조절",
                    self.small_font, self.menu_buttons["level"].collidepoint(mx, my))
        draw_button(self.screen, self.menu_buttons["notice"], "설명서",
                    self.small_font, self.menu_buttons["notice"].collidepoint(mx, my))
        draw_button(self.screen, self.menu_buttons["start"], "게임 시작",
                    self.small_font, self.menu_buttons["start"].collidepoint(mx, my))

        info = self.small_font.render(f"현재 레벨: {self.current_level}", True, (220, 220, 220))
        self.screen.blit(info, info.get_rect(center=(W // 2, self.menu_back_button.top - 25)))

        hovered_back = self.menu_back_button.collidepoint(mx, my)
        back_color = (90, 90, 120) if hovered_back else (60, 60, 80)
        pygame.draw.rect(self.screen, back_color, self.menu_back_button, border_radius=10)
        pygame.draw.rect(self.screen, (200, 200, 220), self.menu_back_button, 2, border_radius=10)

        back_text = self.small_font.render("처음 화면으로", True, (255, 255, 255))
        self.screen.blit(back_text, back_text.get_rect(center=self.menu_back_button.center))

    # ----------------- 설정 팝업 -----------------
    def handle_settings_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.settings_buttons["minus"].collidepoint(mx, my):
                    self.current_level = max(self.min_level, self.current_level - 1)
                elif self.settings_buttons["plus"].collidepoint(mx, my):
                    self.current_level = min(self.max_level, self.current_level + 1)
                elif self.settings_buttons["ok"].collidepoint(mx, my):
                    self.current_screen = "menu"
                elif self.settings_buttons["cancel"].collidepoint(mx, my):
                    self.current_screen = "menu"

    def draw_settings_popup(self):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, (0, 0, 0), self.popup_rect, border_radius=15)
        pygame.draw.rect(self.screen, (255, 255, 255), self.popup_rect, 2, border_radius=15)

        draw_text_center(
            self.screen,
            "레벨 조절",
            self.font,
            (255, 255, 255),
            (self.popup_rect.centerx, self.popup_rect.y + 50)
        )

        level_text = self.font.render(f"현재 레벨: {self.current_level}", True, (255, 255, 0))
        self.screen.blit(level_text, level_text.get_rect(center=(self.popup_rect.centerx, self.popup_rect.y + 120)))

        mx, my = pygame.mouse.get_pos()
        draw_button(self.screen, self.settings_buttons["minus"], "-",
                    self.small_font, self.settings_buttons["minus"].collidepoint(mx, my))
        draw_button(self.screen, self.settings_buttons["plus"], "+",
                    self.small_font, self.settings_buttons["plus"].collidepoint(mx, my))
        draw_button(self.screen, self.settings_buttons["ok"], "확인",
                    self.small_font, self.settings_buttons["ok"].collidepoint(mx, my))
        draw_button(self.screen, self.settings_buttons["cancel"], "취소",
                    self.small_font, self.settings_buttons["cancel"].collidepoint(mx, my))

    # ----------------- 설명서 팝업 -----------------
    def handle_notice_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.notice_buttons["prev"].collidepoint(mx, my):
                    if self.manual_page_index > 0:
                        self.manual_page_index -= 1
                elif self.notice_buttons["next"].collidepoint(mx, my):
                    if self.manual_page_index < len(self.manual_pages) - 1:
                        self.manual_page_index += 1
                elif self.notice_buttons["ok"].collidepoint(mx, my):
                    self.current_screen = "menu"

    def draw_notice_popup(self):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        pygame.draw.rect(self.screen, (30, 30, 50), self.manual_rect, border_radius=15)
        pygame.draw.rect(self.screen, (220, 220, 240), self.manual_rect, 3, border_radius=15)

        title = self.font.render(self.notice_text, True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(self.manual_rect.centerx, self.manual_rect.y + 40)))

        # 현재 페이지
        page = self.manual_pages[self.manual_page_index]

        # 텍스트 그릴 영역
        text_rect = pygame.Rect(
            self.manual_rect.x + 40,
            self.manual_rect.y + 100,
            self.manual_rect.width - 80,
            250
        )

        draw_multiline_rect(
            self.screen,
            page["text"],
            self.small_font,
            (230, 230, 230),
            text_rect,
            align="left"
        )

        # 이미지 처리 (이미지가 있을 때만, 그리고 팝업 안에만 들어오도록)
        img = page.get("image", None)
        if img is not None:
            # 텍스트 아래에 들어갈 수 있는 최대 영역 계산
            max_w = self.manual_rect.width - 80
            # 아래쪽에 버튼 영역(대략 120px) 남겨두고 그 위까지만 사용
            max_h = self.manual_rect.bottom - 120 - text_rect.bottom
            if max_h > 0:
                iw, ih = img.get_size()
                # 비율 유지하며 manual_rect 안에 들어가도록 스케일
                scale = min(max_w / iw, max_h / ih, 1.0)
                new_w = int(iw * scale)
                new_h = int(ih * scale)
                if scale < 1.0:
                    img = pygame.transform.smoothscale(img, (new_w, new_h))

                img_rect = img.get_rect()
                img_rect.centerx = self.manual_rect.centerx
                img_rect.top = text_rect.bottom + 20  # 텍스트와 약간 간격
                # 혹시라도 아래로 살짝 넘치면 버튼 영역을 침범하지 않도록 보정
                if img_rect.bottom > self.manual_rect.bottom - 80:
                    diff = img_rect.bottom - (self.manual_rect.bottom - 80)
                    img_rect.y -= diff
                self.screen.blit(img, img_rect)


        # 페이지 번호
        page_str = f"{self.manual_page_index + 1} / {len(self.manual_pages)}"
        page_surf = self.small_font.render(page_str, True, (220, 220, 220))
        self.screen.blit(page_surf, page_surf.get_rect(center=(self.manual_rect.centerx, self.manual_rect.bottom - 110)))

        mx, my = pygame.mouse.get_pos()
        draw_button(self.screen, self.notice_buttons["prev"], "앞 장",
                    self.small_font, self.notice_buttons["prev"].collidepoint(mx, my) and self.manual_page_index > 0)
        draw_button(self.screen, self.notice_buttons["next"], "뒷 장",
                    self.small_font, self.notice_buttons["next"].collidepoint(mx, my) and self.manual_page_index < len(self.manual_pages) - 1)
        draw_button(self.screen, self.notice_buttons["ok"], "닫기",
                    self.small_font, self.notice_buttons["ok"].collidepoint(mx, my))

    # ----------------- 스토리 -----------------
    # 스토리 화면에서 실제 게임으로 넘어가기 전 필요한 변수들을 초기화하고
    # 플레이어 위치와 각종 게이지 값을 리셋하며 cctv 관련 설정을 다시 잡아주는 준비 단계
    def go_to_game(self): #게임 시작 준비
        self.game_elapsed = 0.0
        self.game_minutes = 0.0
        self.boredom = 0.0
        self.rely = 50
        self.surv = 100
        self.sheepsheep = 30.0
        self.player = Player(W // 2, H // 2)

        # 문 관련 정보 초기화, 리필 시간이나 상호작용 여부를 새 게임 기준으로 초기화
        self.door_interacted = [False] * len(self.door_rects)
        self.door_has_potion = [False] * len(self.door_rects)
        self.next_refill_minute = [0.0] * len(self.door_rects)
        self.moolyak_positions = [None] * len(self.door_rects)

        # 엔딩 상태와 화면 모드를 게임 화면으로 전환하고 cctv 화면 설정도 다시 구성
        self.ending_state = None
        self.current_screen = "game"
        self.cctv_init()

        self.ingame = True
        self.paused=False

        # cctv 영역에서 보여줄 양 리스트와 늑대 위치 리스트도 초기화
        self.sheep=[]
        self.wolf_location=[]

        # cctv 글꼴 크기를 현재 분할 수에 맞게 조정하고 양 이미지도 해당 크기에 맞춰 로드
        self.cctv_font = pygame.font.Font('assets/fonts/font.ttf', max(self.cctvh//16,8))
        assets.load_sheep(self.cctvw/5)

    # 스토리 화면에서 클릭을 받아 다음 문장으로 넘기거나
    # 스토리 스킵과 같은 버튼 처리를 담당하는 부분
    def handle_story_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos

                # 뒤로가기 버튼을 누르면 스토리 초기화 후 메뉴로 이동
                if self.story_buttons["back"].collidepoint(mx, my):
                    self.story_index = 0
                    self.current_screen = "menu"
                    return

                # 스킵 버튼을 누르면 바로 대화씬으로 넘어가기
                if self.story_buttons["skip"].collidepoint(mx, my):
                    self.start_dialog()
                    return

                # 일반 클릭 시 스토리 문장을 하나씩 넘기고 끝나면 대화씬 진입
                if self.story_index < len(self.story_lines) - 1:
                    self.story_index += 1
                else:
                    self.start_dialog()

    # 실제 스토리 화면을 그리고 텍스트 박스와 버튼, 현재 페이지 수 등을 표시하는 작업
    def draw_story(self):
        self.screen.fill((10, 10, 30))

        # 상단 제목 표시
        title = self.font.render("스토리", True, (255, 255, 255))
        self.screen.blit(title, title.get_rect(center=(W // 2, 80)))

        # 중앙에 스토리 텍스트 박스를 만들고 그 안에 현재 문장을 출력
        story_rect = pygame.Rect(80, 140, W - 160, H - 260)
        pygame.draw.rect(self.screen, (30, 30, 60), story_rect, border_radius=15)
        pygame.draw.rect(self.screen, (180, 180, 220), story_rect, 2, border_radius=15)

        draw_multiline_rect(
            self.screen,
            self.story_lines[self.story_index],
            self.small_font,
            (255, 255, 255),
            story_rect,
            align="left"
        )

        # 페이지 수 표시
        page_text = self.small_font.render(
            f"{self.story_index + 1} / {len(self.story_lines)}",
            True,
            (200, 200, 200)
        )
        self.screen.blit(page_text, page_text.get_rect(bottomright=(W - 30, story_rect.bottom - 10)))

        # 버튼 표시, 마우스 위치에 따라 hover 적용
        mx, my = pygame.mouse.get_pos()
        draw_button(self.screen, self.story_buttons["back"], "메뉴로 돌아가기",
                    self.small_font, self.story_buttons["back"].collidepoint(mx, my))
        draw_button(self.screen, self.story_buttons["skip"], "스토리 스킵하기",
                    self.small_font, self.story_buttons["skip"].collidepoint(mx, my))

        # 다음 문장으로 넘어갈 수 있는 힌트 문구 표시
        hint = self.small_font.render("배경을 클릭하면 다음 문장으로 진행됩니다.", True, (200, 200, 200))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

    # ----------------- 일반 대화 -----------------
    # 스토리 종료 후 캐릭터 간 대화 흐름을 시작할 때 항상 index를 처음으로 맞추고 화면 모드를 dialog로 전환
    def start_dialog(self):
        self.dialog_index = 0
        self.current_screen = "dialog"

    # 대화 화면에서 마우스 클릭을 받아 대사를 넘기고
    # 대사가 끝나면 실제 게임으로 이동시키는 처리
    def handle_dialog_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.dialog_index < len(self.dialog_script) - 1:
                    self.dialog_index += 1
                else:
                    self.go_to_game()

    # 대화 씬을 그리는 부분, 캐릭터 이미지와 말풍선, 대사 텍스트를 출력
    def draw_dialog(self):
        self.screen.blit(self.story_background, (0, 0))

        # 좌우 캐릭터 표시 위치 설정
        hero_rect = self.story_character.get_rect()
        hero_rect.bottomleft = (60, H - 40)
        farmer_rect = self.story_farmer.get_rect()
        farmer_rect.bottomright = (W - 60, H - 40)
        self.screen.blit(self.story_character, hero_rect)
        self.screen.blit(self.story_farmer, farmer_rect)

        # 말풍선 생성
        bubble_rect = pygame.Rect(120, 40, W - 240, 200)
        pygame.draw.rect(self.screen, (255, 255, 255), bubble_rect, border_radius=15)
        pygame.draw.rect(self.screen, (0, 0, 0), bubble_rect, 3, border_radius=15)

        # 현재 대화 화자와 텍스트를 가져오고, 어느 쪽 캐릭터인지에 따라 말풍선 꼬리 위치 조정
        speaker, text = self.dialog_script[self.dialog_index]
        side = self.dialog_speaker_side.get(speaker, "left")

        if side == "left":
            tail_points = [
                (bubble_rect.left + 80, bubble_rect.bottom),
                (bubble_rect.left + 140, bubble_rect.bottom),
                (hero_rect.right - 40, hero_rect.top + 40),
            ]
        else:
            tail_points = [
                (bubble_rect.right - 80, bubble_rect.bottom),
                (bubble_rect.right - 140, bubble_rect.bottom),
                (farmer_rect.left + 40, farmer_rect.top + 40),
            ]
        pygame.draw.polygon(self.screen, (255, 255, 255), tail_points)
        pygame.draw.polygon(self.screen, (0, 0, 0), tail_points, 3)

        # 화자 이름 표시
        name_text = f"<{speaker}>"
        name_surf = self.small_font.render(name_text, True, (170, 170, 170))
        self.screen.blit(name_surf, (bubble_rect.x + 20, bubble_rect.y + 15))

        # 말풍선 안에 대사 텍스트를 여러 줄로 출력
        text_rect = pygame.Rect(
            bubble_rect.x + 20,
            bubble_rect.y + 50,
            bubble_rect.width - 40,
            bubble_rect.height - 60,
        )
        draw_multiline_rect(
            self.screen,
            text,
            self.small_font,
            (0, 0, 0),
            text_rect,
            align="left",
        )

        # 클릭하면 다음 대사로 넘어간다는 안내 표시
        hint = self.small_font.render("아무 곳이나 클릭하여 다음 대사", True, (230, 230, 230))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))
    # ----------------- 일반 대화 -----------------
    def start_dialog(self):
        self.dialog_index = 0
        self.current_screen = "dialog"

    def handle_dialog_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.dialog_index < len(self.dialog_script) - 1:
                    self.dialog_index += 1
                else:
                    self.go_to_game()

    def draw_dialog(self):
        self.screen.blit(self.story_background, (0, 0))

        hero_rect = self.story_character.get_rect()
        hero_rect.bottomleft = (60, H - 40)
        farmer_rect = self.story_farmer.get_rect()
        farmer_rect.bottomright = (W - 60, H - 40)
        self.screen.blit(self.story_character, hero_rect)
        self.screen.blit(self.story_farmer, farmer_rect)

        bubble_rect = pygame.Rect(120, 40, W - 240, 200)
        pygame.draw.rect(self.screen, (255, 255, 255), bubble_rect, border_radius=15)
        pygame.draw.rect(self.screen, (0, 0, 0), bubble_rect, 3, border_radius=15)

        speaker, text = self.dialog_script[self.dialog_index]
        side = self.dialog_speaker_side.get(speaker, "left")

        if side == "left":
            tail_points = [
                (bubble_rect.left + 80, bubble_rect.bottom),
                (bubble_rect.left + 140, bubble_rect.bottom),
                (hero_rect.right - 40, hero_rect.top + 40),
            ]
        else:
            tail_points = [
                (bubble_rect.right - 80, bubble_rect.bottom),
                (bubble_rect.right - 140, bubble_rect.bottom),
                (farmer_rect.left + 40, farmer_rect.top + 40),
            ]
        pygame.draw.polygon(self.screen, (255, 255, 255), tail_points)
        pygame.draw.polygon(self.screen, (0, 0, 0), tail_points, 3)

        name_text = f"<{speaker}>"
        name_surf = self.small_font.render(name_text, True, (170, 170, 170))
        self.screen.blit(name_surf, (bubble_rect.x + 20, bubble_rect.y + 15))

        text_rect = pygame.Rect(
            bubble_rect.x + 20,
            bubble_rect.y + 50,
            bubble_rect.width - 40,
            bubble_rect.height - 60,
        )
        draw_multiline_rect(
            self.screen,
            text,
            self.small_font,
            (0, 0, 0),
            text_rect,
            align="left",
        )

        hint = self.small_font.render("아무 곳이나 클릭하여 다음 대사", True, (230, 230, 230))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

    # ----------------- 일반 대화 -----------------
    def start_report(self,result):
        self.report_index = 0
        self.current_screen = "report"
        self.report_state=result
        if result == 1:
            self.report_script=self.report_capture_sheep
        elif result == 2:
            self.report_script=self.report_lose
        elif result == 3:
            self.report_script=self.report_lose_wolf
        else:
            self.report_script = [
            ("서하찮-주인공", "성제현쌤사랑해요"), #### 이스터에그를찾으셨군용축하드립니다 (인게임에서 나올 일 없음)
        ]
    def handle_dialog2_events(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.report_index < len(self.report_script) - 1:
                    self.report_index += 1
                else:
                    if self.report_state==1:
                        self.boredom=max(self.boredom-50,0)
                        self.rely=min(self.rely+randrange(6,15),100)
                        # self.surv=max(self.surv-randrange(5,10),0)
                    elif self.report_state==2:
                        self.boredom=0
                        self.rely=max(self.rely-randrange(20,30),0)
                    elif self.report_state==3:
                        self.boredom=1
                        self.rely=max(self.rely-randrange(40,50),0)
                        self.surv=max(self.surv - randrange(40, 50), 0)
                    self.sheepsheep=self.game_minutes+15
                    self.sheep=[]
                    self.wolf_location=[]
                    self.paused=False
                    self.current_screen = "game"

    def draw_dialog2(self):
        self.screen.blit(self.report_bg, (0, 0))

        hero_rect = self.story_character.get_rect()
        hero_rect.bottomleft = (60, H - 40)
        farmer_rect = self.story_farmer.get_rect()
        farmer_rect.bottomright = (W - 60, H - 40)
        self.screen.blit(self.story_character, hero_rect)
        self.screen.blit(self.story_farmer, farmer_rect)

        bubble_rect = pygame.Rect(120, 40, W - 240, 200)
        pygame.draw.rect(self.screen, (255, 255, 255), bubble_rect, border_radius=15)
        pygame.draw.rect(self.screen, (0, 0, 0), bubble_rect, 3, border_radius=15)

        speaker, text = self.report_script[self.report_index]
        side = self.report_speaker_side.get(speaker, "left")

        if side == "left":
            tail_points = [
                (bubble_rect.left + 80, bubble_rect.bottom),
                (bubble_rect.left + 140, bubble_rect.bottom),
                (hero_rect.right - 40, hero_rect.top + 40),
            ]
        else:
            tail_points = [
                (bubble_rect.right - 80, bubble_rect.bottom),
                (bubble_rect.right - 140, bubble_rect.bottom),
                (farmer_rect.left + 40, farmer_rect.top + 40),
            ]
        pygame.draw.polygon(self.screen, (255, 255, 255), tail_points)
        pygame.draw.polygon(self.screen, (0, 0, 0), tail_points, 3)

        name_text = f"<{speaker}>"
        name_surf = self.small_font.render(name_text, True, (170, 170, 170))
        self.screen.blit(name_surf, (bubble_rect.x + 20, bubble_rect.y + 15))

        text_rect = pygame.Rect(
            bubble_rect.x + 20,
            bubble_rect.y + 50,
            bubble_rect.width - 40,
            bubble_rect.height - 60,
        )
        draw_multiline_rect(
            self.screen,
            text,
            self.small_font,
            (0, 0, 0),
            text_rect,
            align="left",
        )

        hint = self.small_font.render("아무 곳이나 클릭하여 다음 대사", True, (230, 230, 230))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

    # ----------------- 게임 -----------------
    def handle_game_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.current_screen = "menu"
                    self.ingame = False

                elif e.key == pygame.K_a:
                    # 1) 파란 인터랙트 구역 → CCTV
                    if self.player and rect_hits_interact(self.player.rect):
                        self.current_screen = "cctv"

                    # 2) 마을회관 → CCTV
                    elif self.player and self.player.rect.colliderect(self.townhall_rect):
                        self.current_screen = "cctv"

                    # 3) 그 외에는 기존 문/물약 처리
                    elif self.player and self.current_door_index != -1:
                        door_id = self.current_door_index
                        if 0 <= door_id < len(self.door_rects):
                            if self.game_minutes >= self.next_refill_minute[door_id] and not self.door_has_potion[
                                door_id]:
                                dx, dy = self.door_rects[door_id].center
                                offset = 30
                                spawn_x = dx + randint(-offset, offset)
                                spawn_y = dy + randint(-offset, offset)
                                self.moolyak_positions[door_id] = (spawn_x, spawn_y)
                                self.door_has_potion[door_id] = True
                                self.door_interacted[door_id] = True
                                self.next_refill_minute[door_id] = self.game_minutes + 6 * 60

    def draw_game(self):


        self.screen.blit(assets.main_map, (0, 0))

        if self.player:
            self.player.draw(self.screen)

        hour, minute = self.get_game_clock_hm()
        t = self.small_cctv_font.render(f"{hour:02d}:{minute:02d}", True, (255, 255, 255))
        self.screen.blit(t, t.get_rect(topright=(W - 20, 20)))
        if self.sheepsheep>self.game_minutes:
            tt = self.small_font.render(f"{int(self.sheepsheep-self.game_minutes):02d} 분 후 양 출몰", True, (255, 255, 255))
            self.screen.blit(tt, tt.get_rect(topright=(W - 20, 70)))

        info = self.small_font.render(f"레벨 {self.current_level}", True, (230, 230, 230))
        self.screen.blit(info, (20, 20))

        # 심심도 / 신뢰도 / 생존율 게이지는 각 GaugeBar 객체가 그린다.
        # (좌표·색상·수치 계산은 원본과 동일하며, 반복 코드를 객체로 묶은 것뿐이다.)
        self.boredom_gauge.draw(self.screen, self.small_font, self.boredom, self.max_boredom)
        self.rely_gauge.draw(self.screen, self.small_font, self.rely, self.max_rely)
        self.surv_gauge.draw(self.screen, self.small_font, self.surv, self.max_surv)

        ############################

        hint = self.small_font.render("방향키 이동, A: 상호작용, ESC: 메뉴로", True, (230, 230, 230))
        self.screen.blit(hint, hint.get_rect(left=20, top=50))


        # 도어 텍스트
        if self.player and self.current_door_index != -1:
            door_id = self.current_door_index
            if 0 <= door_id < len(self.door_rects):
                door_rect = self.door_rects[door_id]
                if not self.door_interacted[door_id] or self.next_refill_minute[door_id] - self.game_minutes<=0:
                    msg = "혹시 심심해? 'A' 눌러"
                else:
                    if self.door_has_potion[door_id]:
                        msg = "아직도 심심해..?"
                    else:
                        remain = max(0.0, self.next_refill_minute[door_id] - self.game_minutes)
                        r_h = int(remain // 60)
                        r_m = int(remain % 60)
                        msg = f"아직도 심심해..?(남은시간: {r_h:02d}:{r_m:02d})"

                surf = self.small_font.render(msg, True, (255, 255, 255))
                bg = surf.get_rect(midbottom=(door_rect.centerx, door_rect.top - 5))
                bg.inflate_ip(10, 6)
                pygame.draw.rect(self.screen, (0, 0, 0), bg)
                self.screen.blit(surf, bg.inflate(-10, -6))

        # 마을회관 안내
        if self.player and self.player.rect.colliderect(self.townhall_rect):
            msg = "CCTV 보려면 'A' 눌러"
            surf = self.small_font.render(msg, True, (255, 255, 0))
            bg = surf.get_rect(midbottom=(self.townhall_rect.centerx, self.townhall_rect.top - 5))
            bg.inflate_ip(10, 6)
            pygame.draw.rect(self.screen, (0, 0, 0), bg)
            self.screen.blit(surf, bg.inflate(-10, -6))
        # CCTV 안내 — 파란 인터랙트 구역일 때만
        if self.player and rect_hits_interact(self.player.rect):
            prompt = self.small_font.render("A 버튼: CCTV 보기", True, (255, 255, 0))
            p_rect = prompt.get_rect(center=(W // 2, H - 40))
            bg_rect = p_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
            self.screen.blit(prompt, p_rect)

        # 물약 그리기
        for pos in self.moolyak_positions:
            if pos is not None:
                self.screen.blit(self.moolyak_image, pos)

    # ----------------- 엔딩 대화 -----------------
    def start_ending(self, result):
        self.paused = True
        self.ingame = False
        self.ending_state = result
        if result == "win":
            self.active_ending_script = self.ending_dialog_win
            self.active_ending_bg = self.ending_bg_win
            self.ending_lesson_text = self.ending_lesson_text_win
        elif result == "win2":
            self.active_ending_script = self.ending_dialog_win_wolf
            self.active_ending_bg = self.ending_bg_win
            self.ending_lesson_text = self.ending_lesson_text_win
        elif result == "bored":
            self.active_ending_script = self.ending_dialog_bored
            self.active_ending_bg = self.ending_bg_lose
            self.ending_lesson_text = self.ending_lesson_text_lose
        elif result == "lose":
            self.active_ending_script = self.ending_dialog_lose
            self.active_ending_bg = self.ending_bg_lose
            self.ending_lesson_text = self.ending_lesson_text_lose
        elif result == "sheep":
            self.active_ending_script = self.ending_dialog_lose_sheep
            self.active_ending_bg = self.ending_bg_lose
            self.ending_lesson_text = self.ending_lesson_text_lose

        self.ending_dialog_index = 0
        self.current_screen = "ending_dialog"

    def handle_ending_dialog_events(self, events):
        if self.active_ending_script is None:
            return
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if self.ending_dialog_index < len(self.active_ending_script) - 1:
                    self.ending_dialog_index += 1
                else:
                    self.start_ending_lesson()

    def draw_ending_dialog(self):
        self.screen.blit(self.active_ending_bg, (0, 0))

        hero_rect = self.story_character.get_rect()
        hero_rect.bottomleft = (60, H - 40)
        farmer_rect = self.story_farmer.get_rect()
        farmer_rect.bottomright = (W - 60, H - 40)
        self.screen.blit(self.story_character, hero_rect)
        self.screen.blit(self.story_farmer, farmer_rect)

        bubble_rect = pygame.Rect(120, 40, W - 240, 200)
        pygame.draw.rect(self.screen, (255, 255, 255), bubble_rect, border_radius=15)
        pygame.draw.rect(self.screen, (0, 0, 0), bubble_rect, 3, border_radius=15)

        speaker, text = self.active_ending_script[self.ending_dialog_index]
        side = self.dialog_speaker_side.get(speaker, "left")

        if side == "left":
            tail_points = [
                (bubble_rect.left + 80, bubble_rect.bottom),
                (bubble_rect.left + 140, bubble_rect.bottom),
                (hero_rect.right - 40, hero_rect.top + 40),
            ]
        else:
            tail_points = [
                (bubble_rect.right - 80, bubble_rect.bottom),
                (bubble_rect.right - 140, bubble_rect.bottom),
                (farmer_rect.left + 40, farmer_rect.top + 40),
            ]
        pygame.draw.polygon(self.screen, (255, 255, 255), tail_points)
        pygame.draw.polygon(self.screen, (0, 0, 0), tail_points, 3)

        name_text = f"<{speaker}>"
        name_surf = self.small_font.render(name_text, True, (200, 200, 60))
        self.screen.blit(name_surf, (bubble_rect.x + 20, bubble_rect.y + 15))

        text_rect = pygame.Rect(
            bubble_rect.x + 20,
            bubble_rect.y + 50,
            bubble_rect.width - 40,
            bubble_rect.height - 60,
        )
        draw_multiline_rect(
            self.screen,
            text,
            self.small_font,
            (0, 0, 0),
            text_rect,
            align="left",
        )

        hint = self.small_font.render("아무 곳이나 클릭하여 다음 대사", True, (240, 240, 240))
        self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 30)))

    # ----------------- 엔딩 교훈(타이핑) -----------------
    def start_ending_lesson(self):
        self.lesson_start_time = pygame.time.get_ticks() / 1000.0
        self.current_screen = "ending_lesson"

    def handle_ending_lesson_events(self, events):
        # 텍스트가 다 나오기 전에는 건너뛰기 안 됨
        elapsed = pygame.time.get_ticks() / 1000.0 - self.lesson_start_time
        visible_len = int(elapsed * self.lesson_speed)
        finished = visible_len >= len(self.ending_lesson_text)

        if not finished:
            return

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.current_screen = "menu"

    def draw_ending_lesson(self):
        self.screen.fill((0, 0, 0))

        elapsed = pygame.time.get_ticks() / 1000.0 - self.lesson_start_time
        visible_len = int(elapsed * self.lesson_speed)
        visible_len = max(0, min(len(self.ending_lesson_text), visible_len))
        visible_text = self.ending_lesson_text[:visible_len]

        rect = pygame.Rect(100, 150, W - 200, H - 300)
        draw_multiline_rect(
            self.screen,
            visible_text,
            self.lesson_font,
            (230, 220, 80),
            rect,
            align="left"
        )

        finished = visible_len >= len(self.ending_lesson_text)
        if finished:
            hint = self.small_font.render("클릭하거나 SPACE/ENTER로 메인 메뉴로", True, (230, 230, 230))
            self.screen.blit(hint, hint.get_rect(center=(W // 2, H - 60)))

        title = self.font.render("교훈", True, (230, 230, 230))
        self.screen.blit(title, title.get_rect(center=(W // 2, 80)))

    # ----------------- CCTV -----------------ㅅㅅㅌㅂ
    def handle_cctv_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.current_screen = "menu"
                    self.ingame = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.cctv_buttons["back"].collidepoint(mx, my):
                    self.current_screen = "game"
                    # self.cctv_init()
                if self.cctv_buttons["report"].collidepoint(mx, my):
                    self.paused=True
                    if self.wolf_location:
                        self.start_report(1)
                    else:
                        self.start_report(2)

                    # self.cctv_init()

    def cctv_init(self):
        self.cctvcount_x=self.current_level + 1
        self.cctvcount_y=self.current_level + 1
        self.cctvgap=10
        self.cctvw=(W-self.cctvgap*(self.cctvcount_x+1))//self.cctvcount_x
        self.cctvh=(H-self.cctvgap*(self.cctvcount_y+1))//self.cctvcount_y
        self.cctvies=[[pygame.Surface((self.cctvw, self.cctvh), pygame.SRCALPHA) for _ in range(self.cctvcount_y)]for _ in range(self.cctvcount_x)]

    def sheep_maintain(self):
        # 실제 양 유지 로직은 Flock 객체에 위임한다.
        self.flock.maintain(self.cctvcount_x, self.cctvcount_y,
                            self.cctvw, self.cctvh, self.surv, self.max_surv)

    def sheep_move(self):
        # 실제 이동 로직은 Flock 객체에 위임한다.
        self.flock.move(self.cctvw, self.cctvh)

    def sheep_blit(self):
        # 실제 그리기 로직은 Flock 객체에 위임한다.
        self.flock.blit(self.cctvies)
    def draw_cctv(self):
        # self.screen.blit(assets.main_map, (0, 0))
        # 실제 cctv 전체 화면을 그리기 위한 초기화, 화면을 검정색으로 채우고
        # 이후 여러 cctv 격자를 하나씩 채워 넣는 방식으로 화면 구성
        # self.screen.blit(assets.main_map, (0, 0))
        self.screen.fill((0, 0, 0))

        # 화면
        for i in range(self.cctvcount_x):
            for j in range(self.cctvcount_y):
                self.cctvies[i][j].fill((64,64,64))

        # 양
        self.sheep_blit()

        # cctv blit하기
        for i in range(self.cctvcount_x):
            for j in range(self.cctvcount_y):
                a=self.cctv_font.render(f'CCTV [{self.cctvcount_x*j+i+1:03d}]', True, (255, 255, 255))
                a.set_alpha(192)
                self.cctvies[i][j].blit(a,(0.02*self.cctvw,0.02*self.cctvh))
                self.screen.blit(self.cctvies[i][j], (self.cctvgap*(i+1)+self.cctvw*i, self.cctvgap*(j+1)+self.cctvh*j))

        # 개쩌는필터만들기 (gpt도움약간받음)

        ## 스캔라인
        scan = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 2):
            pygame.draw.line(scan, (0, 0, 0, 50), (0, y), (W, y))
        self.screen.blit(scan, (0,0))

        ## 노이즈
        #gpt시작
        noise = pygame.Surface((W, H), pygame.SRCALPHA)
        arr = pygame.surfarray.pixels_alpha(noise)
        arr[:, :] = np.random.randint(0, 80, (W,H))
        del arr
        self.screen.blit(noise, (0,0), special_flags=pygame.BLEND_RGBA_ADD)
        #gpt끝

        ## 녹색
        tint = pygame.Surface((W, H), pygame.SRCALPHA)
        tint.fill((0, 40, 0, 30))  # 초록빛 약간
        self.screen.blit(tint, (0,0), special_flags=pygame.BLEND_RGBA_ADD)

        # 개쩌는필터만들기 끝

        hour, minute = self.get_game_clock_hm()
        time_str = f"{hour:02d}:{minute:02d}"
        time_surf = self.small_cctv_font.render(time_str, True, (255, 255, 255))
        time_surf.set_alpha(128)
        time_rect = time_surf.get_rect(topright=(W - 20, 20))
        self.screen.blit(time_surf, time_rect)
        mx, my = pygame.mouse.get_pos()

        btnbtn = pygame.Surface((W, H), pygame.SRCALPHA)
        draw_button(btnbtn, self.cctv_buttons["back"], "<< Back",
                    self.small_font, self.cctv_buttons["back"].collidepoint(mx, my),base_color=(70,70,70),hover_color=(100,100,100))
        draw_button(btnbtn, self.cctv_buttons["report"], "Report >>",
                    self.small_font, self.cctv_buttons["report"].collidepoint(mx, my),base_color=(100,60,60),hover_color=(1000/6,100,100))
        btnbtn.set_alpha(128)
        self.screen.blit(btnbtn, (0,0), special_flags=pygame.BLEND_RGBA_ADD)

    # ----------------- 메인 루프 -----------------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            # BGM 스위칭
            if self.current_screen == "intro":
                if self.current_bgm != "intro":
                    pygame.mixer.music.load("assets/sounds/intro.mp3")
                    pygame.mixer.music.play(-1)  # 반복 재생
                    self.current_bgm = "intro"

            elif self.current_screen == "game":
                if self.current_bgm != "gameplay":
                    pygame.mixer.music.load("assets/sounds/gameplay.mp3")
                    pygame.mixer.music.play(-1)
                    self.current_bgm = "gameplay"

            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    running = False

                # 화면별 이벤트 처리
                if self.current_screen == "intro":
                    self.handle_intro_events(events)
                elif self.current_screen == "menu":
                    self.handle_menu_events(events)
                elif self.current_screen == "settings_popup":
                    self.handle_settings_events(events)
                elif self.current_screen == "notice_popup":
                    self.handle_notice_events(events)
                elif self.current_screen == "story":
                    self.handle_story_events(events)
                elif self.current_screen == "dialog":
                    self.handle_dialog_events(events)
                elif self.current_screen == "game":
                    self.handle_game_events(events)
                elif self.current_screen == "cctv":
                    self.handle_cctv_events(events)
                elif self.current_screen == "report":
                    self.handle_dialog2_events(events)
                elif self.current_screen == "ending_dialog":
                    self.handle_ending_dialog_events(events)
                elif self.current_screen == "ending_lesson":
                    self.handle_ending_lesson_events(events)

            # 업데이트(게임 화면일 때만)
            if self.ingame:
                if not self.paused:
                    if self.sheepsheep <= self.game_minutes:
                        print('sheep maintain')
                        self.sheep_maintain()
                        self.sheep_move()
                    self.game_elapsed += dt
                if self.game_elapsed > GAME_DURATION:
                    self.game_elapsed = GAME_DURATION

                total_minutes_span = (GAME_END_HOUR - GAME_START_HOUR) * 60
                # minutes_delta = total_minutes_span * dt / GAME_DURATION <- 이새키너무작아서반올림버그있음;;;;;;;
                # self.game_minutes += minutes_delta
                self.game_minutes = total_minutes_span *self.game_elapsed / GAME_DURATION

                if self.current_level > 0:
                    self.boredom += (self.current_level+10) * total_minutes_span * dt / GAME_DURATION /25
                self.boredom = max(0.0, min(self.max_boredom, self.boredom))
            if self.current_screen == "game":
                if self.player:
                    keys = pygame.key.get_pressed()
                    self.player.update(dt, keys, self.screen.get_rect())


                # 물약 먹었는지 체크
                if self.player:
                    for i, pos in enumerate(self.moolyak_positions):
                        if pos is None:
                            continue
                        pot_rect = self.moolyak_image.get_rect(topleft=pos)
                        if self.player.rect.colliderect(pot_rect):
                            self.moolyak_positions[i] = None
                            self.door_has_potion[i] = False
                            self.boredom -= int(55-2.5*self.current_level)
                            if self.boredom < 0:
                                self.boredom = 0

                if self.player and (
                        rect_hits_interact(self.player.rect) or
                        self.player.rect.colliderect(self.townhall_rect)
                ):
                    self.can_interact_now = True
                else:
                    self.can_interact_now = False

                # CCTV 영역
                if self.player and rect_hits_interact(self.player.rect):
                    self.can_interact_now = True
                else:
                    self.can_interact_now = False

                # 문 충돌
                if self.player:
                    idx = self.player.rect.collidelist(self.door_rects)
                    self.current_door_index = idx if idx != -1 else -1
                else:
                    self.current_door_index = -1

                # 엔딩 조건
                if self.ending_state is None:
                    if self.rely <= 0:
                        self.start_ending("lose")
                    if self.boredom >= self.max_boredom:
                        self.start_ending("bored")
                    elif self.game_elapsed >= GAME_DURATION:
                        if self.boredom < self.max_boredom:
                            self.start_ending("win")
                        else:
                            self.start_ending("bored")

            else:
                self.can_interact_now = False
                if self.current_screen not in ("ending_dialog", "ending_lesson"):
                    self.current_door_index = -1

            # 그리기
            if self.current_screen == "intro":
                self.draw_intro()
            elif self.current_screen == "menu":
                self.draw_menu()
            elif self.current_screen == "settings_popup":
                self.draw_menu()
                self.draw_settings_popup()
            elif self.current_screen == "notice_popup":
                self.draw_menu()
                self.draw_notice_popup()
            elif self.current_screen == "story":
                self.draw_story()
            elif self.current_screen == "dialog":
                self.draw_dialog()
            elif self.current_screen == "game":
                self.draw_game()
            elif self.current_screen == "cctv":
                self.draw_cctv()
            elif self.current_screen == "report":
                self.draw_dialog2()
            elif self.current_screen == "ending_dialog":
                self.draw_ending_dialog()
            elif self.current_screen == "ending_lesson":
                self.draw_ending_lesson()

            pygame.display.flip()

        pygame.quit()
        sys.exit()