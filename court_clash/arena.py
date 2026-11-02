"""Cached basketball arena artwork and dynamic hoops/crowd layers."""

from __future__ import annotations

import math
import random

import pygame

from .effects import CrowdReaction
from .settings import (
    ARENA_NAVY,
    BACKBOARD_OFFSET,
    BLACK,
    COURT_FLOOR,
    COURT_LEFT,
    COURT_RIGHT,
    COURT_TOP,
    COURT_WHITE,
    COURT_CENTER_X,
    GOLD,
    HOOP_LEFT_X,
    HOOP_RIGHT_X,
    HOOP_Y,
    RED,
    RIM_WIDTH,
    STAND_BLUE,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
    WOOD_DARK,
    WOOD_LIGHT,
)


class ArenaRenderer:
    """Builds the expensive court once and animates only light layers."""

    CROWD_COLORS = (
        (250, 208, 120),
        (239, 242, 251),
        (255, 102, 98),
        (72, 206, 183),
        (104, 145, 235),
        (227, 111, 180),
        (177, 195, 219),
    )

    def __init__(self, width: int = VIRTUAL_WIDTH,
                 height: int = VIRTUAL_HEIGHT, seed: int = 7) -> None:
        self.width = width
        self.height = height
        self.random = random.Random(seed)
        self.static = pygame.Surface((width, height)).convert()
        self.light_layer = pygame.Surface((width, height), pygame.SRCALPHA)
        self.crowd_layer = pygame.Surface((width, height), pygame.SRCALPHA)
        self.reaction = CrowdReaction(180)
        self.time = 0.0
        self.net_energy = [0.0, 0.0]
        self.net_phase = [0.0, 1.8]
        self.flash_boards = [0.0, 0.0]
        self._build_static_scene()

    def _build_static_scene(self) -> None:
        self.static.fill(ARENA_NAVY)
        self._draw_roof()
        self._draw_stands()
        self._draw_crowd_static()
        self._draw_led_ribbon()
        self._draw_floor()
        self._draw_court_markings()
        self._draw_scoreboard_mounts()
        self._draw_stanchions()

    def _draw_roof(self) -> None:
        pygame.draw.rect(self.static, (8, 13, 27), (0, 0, self.width, 95))
        pygame.draw.polygon(self.static, (17, 27, 49),
                            [(0, 0), (self.width, 0), (self.width, 76), (0, 104)])
        for index in range(17):
            x = index*self.width/16
            pygame.draw.line(self.static, (26, 41, 66), (x, 0), (x, 83), 2)
        self._draw_roof_trusses()
        self._draw_light_fixtures()

    def _draw_roof_trusses(self) -> None:
        base_y = 82
        for index in range(8):
            x = index*self.width/7
            top_x = x+self.width/14
            pygame.draw.line(self.static, (37, 54, 82), (x, base_y),
                             (top_x, 22), 3)
            pygame.draw.line(self.static, (37, 54, 82),
                             (top_x, 22), (min(self.width, x+self.width/3), base_y), 3)

    def _draw_light_fixtures(self) -> None:
        positions = (160, 385, 640, 895, 1120)
        for x in positions:
            pygame.draw.ellipse(self.static, (65, 79, 104), (x-37, 58, 74, 20))
            pygame.draw.ellipse(self.static, (255, 244, 203), (x-28, 62, 56, 10))

    def _draw_stands(self) -> None:
        pygame.draw.polygon(self.static, (20, 29, 51),
                            [(0, 89), (self.width, 76), (self.width, 279), (0, 287)])
        for row in range(7):
            top = 108+row*24
            inset = row*6
            color = (28+row*2, 39+row*2, 64+row*3)
            pygame.draw.polygon(self.static, color,
                                [(inset, top), (self.width-inset, top-8),
                                 (self.width-inset, top+14), (inset, top+21)])
            pygame.draw.line(self.static, (48, 62, 88), (inset, top+20),
                             (self.width-inset, top+13), 2)

    def _draw_crowd_static(self) -> None:
        for row in range(7):
            y = 112+row*24
            inset = row*9
            for col in range(52):
                x = inset+col*25+self.random.randint(-4, 4)
                if x > self.width-inset:
                    continue
                base = y+self.random.randint(-4, 7)
                skin = self.random.choice(((201, 151, 117), (158, 104, 74), (235, 190, 154)))
                shirt = self.random.choice(self.CROWD_COLORS)
                head_radius = self.random.randint(3, 5)
                pygame.draw.circle(self.static, skin, (x, base), head_radius)
                pygame.draw.ellipse(self.static, shirt,
                                    (x-7, base+3, 14, 14))
                self.reaction.phases[(row*52+col)%len(self.reaction.phases)] = self.random.random()*math.tau

    def _draw_led_ribbon(self) -> None:
        y = 278
        pygame.draw.rect(self.static, (5, 11, 23), (0, y, self.width, 29))
        for section in range(8):
            x1 = section*self.width/8
            x2 = x1+self.width/8-3
            color = (28, 77, 105) if section%2 else (43, 57, 91)
            pygame.draw.rect(self.static, color, (x1, y+3, x2-x1, 21), border_radius=4)

    def _draw_floor(self) -> None:
        floor_top = 306
        floor_height = int(COURT_FLOOR-floor_top)
        for row in range(floor_height):
            shade = row/floor_height
            red = int(WOOD_LIGHT[0]*(1-shade)+WOOD_DARK[0]*shade)
            green = int(WOOD_LIGHT[1]*(1-shade)+WOOD_DARK[1]*shade)
            blue = int(WOOD_LIGHT[2]*(1-shade)+WOOD_DARK[2]*shade)
            pygame.draw.line(self.static, (red, green, blue),
                             (0, floor_top+row), (self.width, floor_top+row))
        for plank in range(22):
            y = floor_top+plank*14
            color = (181, 108, 62) if plank%2 else (216, 151, 91)
            pygame.draw.line(self.static, color, (0, y), (self.width, y), 1)
        for plank in range(16):
            x = plank*self.width/15
            start = floor_top+(plank%3)*19
            pygame.draw.line(self.static, (194, 125, 73), (x, start), (x, COURT_FLOOR), 1)
        pygame.draw.rect(self.static, (255, 231, 195),
                         (COURT_LEFT, COURT_TOP, COURT_RIGHT-COURT_LEFT,
                          COURT_FLOOR-COURT_TOP), 3)
        pygame.draw.line(self.static, (244, 225, 195), (0, COURT_FLOOR),
                         (self.width, COURT_FLOOR), 5)

    def _draw_court_markings(self) -> None:
        line = COURT_WHITE
        pygame.draw.line(self.static, line, (COURT_CENTER_X, COURT_TOP),
                         (COURT_CENTER_X, COURT_FLOOR), 3)
        center_rect = pygame.Rect(COURT_CENTER_X-77, 402, 154, 154)
        pygame.draw.ellipse(self.static, line, center_rect, 3)
        pygame.draw.circle(self.static, (245, 177, 78),
                           (int(COURT_CENTER_X), 480), 13, 2)
        self._draw_key_area(0)
        self._draw_key_area(1)
        self._draw_three_point_arc(0)
        self._draw_three_point_arc(1)
        self._draw_restricted_area(0)
        self._draw_restricted_area(1)
        self._draw_court_logo()

    def _draw_key_area(self, side: int) -> None:
        if side == 0:
            rect = pygame.Rect(0, 370, 255, 230)
            baseline = 0
        else:
            rect = pygame.Rect(self.width-255, 370, 255, 230)
            baseline = self.width
        pygame.draw.rect(self.static, (179, 106, 65), rect)
        pygame.draw.rect(self.static, COURT_WHITE, rect, 3)
        free_throw = pygame.Rect(rect.centerx-67, 410, 134, 136)
        pygame.draw.ellipse(self.static, COURT_WHITE, free_throw, 3)
        pygame.draw.line(self.static, (245, 220, 185),
                         (rect.centerx-67, 476), (rect.centerx+67, 476), 2)
        for mark in range(4):
            offset = mark*24
            pygame.draw.line(self.static, COURT_WHITE,
                             (rect.left+7+offset, 447), (rect.left+25+offset, 447), 2)
            pygame.draw.line(self.static, COURT_WHITE,
                             (rect.right-25-offset, 447), (rect.right-7-offset, 447), 2)

    def _draw_three_point_arc(self, side: int) -> None:
        if side == 0:
            area = pygame.Rect(25, 350, 445, 285)
            angle_start, angle_stop = -92, 92
        else:
            area = pygame.Rect(self.width-470, 350, 445, 285)
            angle_start, angle_stop = 88, 272
        pygame.draw.arc(self.static, (255, 232, 204), area,
                        math.radians(angle_start), math.radians(angle_stop), 3)
        baseline_x = 0 if side == 0 else self.width
        if side == 0:
            pygame.draw.line(self.static, COURT_WHITE, (baseline_x+25, 350), (baseline_x+25, 590), 3)
        else:
            pygame.draw.line(self.static, COURT_WHITE, (baseline_x-25, 350), (baseline_x-25, 590), 3)

    def _draw_restricted_area(self, side: int) -> None:
        hoop_x = HOOP_LEFT_X if side == 0 else HOOP_RIGHT_X
        center = (int(hoop_x), int(COURT_FLOOR-12))
        rect = pygame.Rect(center[0]-73, center[1]-63, 146, 126)
        start = 270 if side == 0 else 90
        pygame.draw.arc(self.static, (255, 224, 191), rect,
                        math.radians(start), math.radians(start+180), 2)

    def _draw_court_logo(self) -> None:
        font = pygame.font.SysFont("arial", 22, bold=True)
        text = font.render("COURT  CLASH", True, (255, 233, 202))
        text.set_alpha(105)
        rect = text.get_rect(center=(int(COURT_CENTER_X), 576))
        self.static.blit(text, rect)
        pygame.draw.circle(self.static, (245, 175, 71),
                           (int(COURT_CENTER_X), 537), 4)

    def _draw_scoreboard_mounts(self) -> None:
        pygame.draw.rect(self.static, (12, 19, 34), (0, 0, self.width, 104))
        pygame.draw.line(self.static, (46, 63, 91), (0, 100), (self.width, 100), 2)
        pygame.draw.rect(self.static, (8, 13, 24), (365, 7, 550, 88), border_radius=14)
        pygame.draw.rect(self.static, (58, 76, 108), (365, 7, 550, 88), 2, border_radius=14)

    def _draw_stanchions(self) -> None:
        for side, hoop_x in enumerate((HOOP_LEFT_X, HOOP_RIGHT_X)):
            outward = -1 if side == 0 else 1
            board_x = hoop_x+outward*BACKBOARD_OFFSET
            pygame.draw.line(self.static, (66, 78, 99), (board_x, 387),
                             (board_x, 505), 11)
            pygame.draw.line(self.static, (48, 59, 80), (board_x, 496),
                             (board_x+outward*44, 528), 12)

    def update(self, dt: float) -> None:
        self.time += dt
        self.reaction.update(dt)
        for side in range(2):
            self.net_energy[side] = max(0.0, self.net_energy[side]-dt*2.3)
            self.net_phase[side] += dt*(8+18*self.net_energy[side])
            self.flash_boards[side] = max(0.0, self.flash_boards[side]-dt*2.5)

    def excite_crowd(self, position_x: float, strength: float = .7) -> None:
        normalized = position_x/max(1, self.width)
        self.reaction.excite(strength, normalized)

    def kick_net(self, side: int, strength: float = 1.0) -> None:
        self.net_energy[side] = max(self.net_energy[side], strength)
        self.flash_boards[side] = max(self.flash_boards[side], .8)
        self.reaction.excite(.95, .5 if side == 0 else .5)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.static, (0, 0))
        self._draw_dynamic_crowd(surface)
        self._draw_hoop(surface, 0)
        self._draw_hoop(surface, 1)
        self._draw_light_beams(surface)

    def _draw_dynamic_crowd(self, surface: pygame.Surface) -> None:
        if self.reaction.energy < .04:
            return
        for index in range(180):
            row = index//26
            col = index%26
            x = 8+col*50
            y = 130+row*23
            energy = self.reaction.local_energy(x/self.width)
            bounce = self.reaction.body_bounce(index)
            center = (x, int(y-bounce))
            color = self.CROWD_COLORS[index%len(self.CROWD_COLORS)]
            if energy > .16:
                hand_y = center[1]-7-int(energy*9)
                pygame.draw.line(surface, color, (x-4, center[1]+6), (x-7, hand_y), 2)
                pygame.draw.line(surface, color, (x+4, center[1]+6), (x+7, hand_y), 2)

    def _draw_hoop(self, surface: pygame.Surface, side: int) -> None:
        x = HOOP_LEFT_X if side == 0 else HOOP_RIGHT_X
        board_side = -1 if side == 0 else 1
        board_x = x+board_side*BACKBOARD_OFFSET
        backboard = pygame.Rect(int(board_x-7), 308, 14, 93)
        pygame.draw.rect(surface, (246, 248, 255), backboard, border_radius=3)
        pygame.draw.rect(surface, (164, 190, 221), backboard, 2, border_radius=3)
        target_box = pygame.Rect(int(board_x-23), 349, 46, 28)
        pygame.draw.rect(surface, (244, 103, 83), target_box, 3)
        rim_rect = pygame.Rect(int(x-RIM_WIDTH/2), int(HOOP_Y), int(RIM_WIDTH), 8)
        pygame.draw.ellipse(surface, (255, 92, 75), rim_rect, 0)
        pygame.draw.ellipse(surface, (255, 195, 160), rim_rect, 1)
        self._draw_net(surface, x, side)
        self._draw_board_glow(surface, board_x, side)

    def _draw_net(self, surface: pygame.Surface, x: float, side: int) -> None:
        energy = self.net_energy[side]
        phase = self.net_phase[side]
        anchor_y = HOOP_Y+7
        bottom_y = HOOP_Y+48+energy*7
        anchors = 8
        for index in range(anchors):
            ratio = index/(anchors-1)
            start_x = x-RIM_WIDTH/2+ratio*RIM_WIDTH
            sway = math.sin(phase+ratio*math.pi*2)*energy*13
            end_x = x-RIM_WIDTH*.31+ratio*RIM_WIDTH*.62+sway
            color = (236, 241, 249)
            pygame.draw.line(surface, color, (start_x, anchor_y), (end_x, bottom_y), 2)
        for cross in (0.38, 0.66):
            y = anchor_y+(bottom_y-anchor_y)*cross
            width = RIM_WIDTH*(1-cross*.58)
            sway = math.sin(phase+cross*4)*energy*8
            pygame.draw.line(surface, (235, 240, 247),
                             (x-width/2+sway, y), (x+width/2+sway, y), 1)

    def _draw_board_glow(self, surface: pygame.Surface, board_x: float, side: int) -> None:
        intensity = self.flash_boards[side]
        if intensity <= .02:
            return
        alpha = int(75*intensity)
        glow = pygame.Surface((130, 150), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 194, 92, alpha), (0, 0, 130, 150))
        surface.blit(glow, (int(board_x-65), 300), special_flags=pygame.BLEND_RGBA_ADD)

    def _draw_light_beams(self, surface: pygame.Surface) -> None:
        self.light_layer.fill((0, 0, 0, 0))
        pulse = (math.sin(self.time*.8)+1)*.5
        for index, x in enumerate((180, 470, 810, 1100)):
            alpha = 8+int(pulse*8)+index%3
            color = (255, 247, 222, alpha)
            pygame.draw.polygon(self.light_layer, color,
                                [(x-7, 74), (x+7, 74), (x+116, 304), (x-116, 304)])
        surface.blit(self.light_layer, (0, 0))

