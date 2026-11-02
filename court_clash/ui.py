"""Smooth procedural players, basketball, scoreboard, and broadcast overlays."""

from __future__ import annotations

import math

import pygame

from .controls import InputRouter
from .entities import Ball, Player
from .settings import (
    ARENA_NAVY,
    BALL_ORANGE,
    BALL_RADIUS,
    BLACK,
    BLUE,
    COURT_FLOOR,
    GOLD,
    GREEN,
    HOOP_Y,
    RED,
    TEAMS,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
    ShotWindow,
    clamp,
    format_clock,
    lerp,
    smoothstep,
)
from .vector import Vec2


class FontBook:
    """Lazily caches polished fonts by size and visual weight."""

    def __init__(self) -> None:
        self.cache: dict[tuple[int, bool, bool], pygame.font.Font] = {}
        self.family = "arial"

    def get(self, size: int, bold: bool = False,
            italic: bool = False) -> pygame.font.Font:
        key = (size, bold, italic)
        if key not in self.cache:
            self.cache[key] = pygame.font.SysFont(self.family, size, bold, italic)
        return self.cache[key]

    def measure(self, text: str, size: int, bold: bool = False) -> tuple[int, int]:
        return self.get(size, bold).size(text)

    def clear(self) -> None:
        self.cache.clear()


class TextPainter:
    """Alignment helpers and subtle outlines for readable game text."""

    def __init__(self, fonts: FontBook | None = None) -> None:
        self.fonts = fonts or FontBook()

    def draw(self, surface: pygame.Surface, text: str, position: tuple[float, float],
             size: int, color: tuple[int, int, int], bold: bool = False,
             anchor: str = "center", shadow: bool = True,
             outline: tuple[int, int, int] | None = None) -> pygame.Rect:
        font = self.fonts.get(size, bold)
        image = font.render(text, True, color)
        if outline is not None:
            mask = font.render(text, True, outline)
            rect = self._anchor_rect(mask.get_rect(), position, anchor)
            for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                surface.blit(mask, rect.move(*offset))
        rect = self._anchor_rect(image.get_rect(), position, anchor)
        if shadow:
            dark = font.render(text, True, (0, 0, 0))
            dark.set_alpha(150)
            surface.blit(dark, rect.move(2, 3))
        surface.blit(image, rect)
        return rect

    @staticmethod
    def _anchor_rect(rect: pygame.Rect, position: tuple[float, float], anchor: str) -> pygame.Rect:
        x, y = round(position[0]), round(position[1])
        if anchor == "center":
            rect.center = (x, y)
        elif anchor == "left":
            rect.midleft = (x, y)
        elif anchor == "right":
            rect.midright = (x, y)
        elif anchor == "topleft":
            rect.topleft = (x, y)
        elif anchor == "topright":
            rect.topright = (x, y)
        return rect

    def pill(self, surface: pygame.Surface, text: str,
             center: tuple[float, float], color: tuple[int, int, int],
             size: int = 13, padding: tuple[int, int] = (15, 8)) -> pygame.Rect:
        font = self.fonts.get(size, True)
        text_surface = font.render(text, True, (248, 250, 255))
        rect = text_surface.get_rect(center=(round(center[0]), round(center[1])))
        panel = rect.inflate(padding[0]*2, padding[1]*2)
        pygame.draw.rect(surface, (11, 17, 30), panel, border_radius=panel.height//2)
        pygame.draw.rect(surface, color, panel, 2, border_radius=panel.height//2)
        surface.blit(text_surface, rect)
        return panel


class PlayerRenderer:
    """Draws player skeletons with layered limbs, cloth, and grounded shadows."""

    def __init__(self, painter: TextPainter | None = None) -> None:
        self.painter = painter or TextPainter()

    def draw(self, surface: pygame.Surface, player: Player, attack: int,
             time: float, alpha: float = 1.0, ball_position: Vec2 | None = None,
             active: bool = False) -> None:
        pose = player.get_pose(attack, time, ball_position)
        offset = player.previous_position.lerp_to(player.position, alpha)-player.position
        self._offset_pose(pose, offset)
        self._draw_shadow(surface, player, alpha)
        self._draw_legs(surface, player, pose)
        self._draw_jersey(surface, player, pose, active)
        self._draw_arms(surface, player, pose)
        self._draw_head(surface, player, pose)
        if active:
            self._draw_selection_ring(surface, player, alpha)

    def _offset_pose(self, pose, offset: Vec2) -> None:
        for name in pose.__slots__:
            point = getattr(pose, name)
            point.x += offset.x
            point.y += offset.y

    def _draw_shadow(self, surface: pygame.Surface, player: Player, alpha: float) -> None:
        position = player.previous_position.lerp_to(player.position, alpha)
        shrink = clamp(player.jump_height/260, 0, .55)
        width = int(70*(1-shrink))
        height = int(15*(1-shrink*.6))
        shadow = pygame.Surface((width+8, height+8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (7, 12, 22, 98), (4, 4, width, height))
        surface.blit(shadow, (position.x-width/2-4, COURT_FLOOR-height/2-4))

    def _draw_legs(self, surface: pygame.Surface, player: Player, pose) -> None:
        skin = player.team.skin
        shorts_shadow = player.team.jersey_shadow
        pygame.draw.line(surface, (23, 28, 39), pose.left_hip.rounded(), pose.left_knee.rounded(), 18)
        pygame.draw.line(surface, skin, pose.left_hip.rounded(), pose.left_knee.rounded(), 12)
        pygame.draw.line(surface, (23, 28, 39), pose.left_knee.rounded(), pose.left_foot.rounded(), 15)
        pygame.draw.line(surface, skin, pose.left_knee.rounded(), pose.left_foot.rounded(), 10)
        pygame.draw.line(surface, (23, 28, 39), pose.right_hip.rounded(), pose.right_knee.rounded(), 18)
        pygame.draw.line(surface, skin, pose.right_hip.rounded(), pose.right_knee.rounded(), 12)
        pygame.draw.line(surface, (23, 28, 39), pose.right_knee.rounded(), pose.right_foot.rounded(), 15)
        pygame.draw.line(surface, skin, pose.right_knee.rounded(), pose.right_foot.rounded(), 10)
        self._draw_shoe(surface, pose.left_foot, player.facing, shorts_shadow)
        self._draw_shoe(surface, pose.right_foot, player.facing, shorts_shadow)

    def _draw_shoe(self, surface: pygame.Surface, foot: Vec2,
                   facing: float, accent: tuple[int, int, int]) -> None:
        x = foot.x+facing*9
        rect = pygame.Rect(round(x-16), round(foot.y-8), 33, 15)
        pygame.draw.ellipse(surface, (9, 14, 24), rect.inflate(4, 4))
        pygame.draw.ellipse(surface, (242, 245, 251), rect)
        pygame.draw.line(surface, accent, (rect.left+8, rect.top+6),
                         (rect.right-7, rect.top+6), 3)
        pygame.draw.line(surface, (207, 218, 234), (rect.left+5, rect.bottom-2),
                         (rect.right-2, rect.bottom-2), 2)

    def _draw_jersey(self, surface: pygame.Surface, player: Player,
                     pose, active: bool) -> None:
        team = player.team
        chest = pose.chest
        points = [
            (chest.x-23, chest.y-6),
            (chest.x-17, chest.y-14),
            (chest.x+17, chest.y-14),
            (chest.x+23, chest.y-6),
            (pose.pelvis.x+22, pose.pelvis.y+9),
            (pose.pelvis.x-22, pose.pelvis.y+9),
        ]
        pygame.draw.polygon(surface, team.jersey_shadow, points)
        inner = [(x, y-3) for x, y in points]
        pygame.draw.polygon(surface, team.jersey, inner)
        pygame.draw.line(surface, team.accent, points[1], points[2], 3)
        pygame.draw.line(surface, team.accent, (pose.pelvis.x-18, pose.pelvis.y+5),
                         (pose.pelvis.x+18, pose.pelvis.y+5), 3)
        number = str(7+player.team_id*3)
        self.painter.draw(surface, number, (chest.x, chest.y+1), 20,
                          (255, 255, 255), bold=True, shadow=False)
        if active:
            pygame.draw.line(surface, (255, 255, 255),
                             (chest.x-12, chest.y+15), (chest.x+12, chest.y+15), 2)

    def _draw_arms(self, surface: pygame.Surface, player: Player, pose) -> None:
        skin = player.team.skin
        self._draw_arm(surface, pose.left_shoulder, pose.left_elbow, pose.left_hand, skin)
        self._draw_arm(surface, pose.right_shoulder, pose.right_elbow, pose.right_hand, skin)
        if player.is_catching:
            self._draw_fingers(surface, pose.left_hand, pose.right_hand, skin)

    def _draw_arm(self, surface: pygame.Surface, shoulder: Vec2,
                  elbow: Vec2, hand: Vec2, skin: tuple[int, int, int]) -> None:
        pygame.draw.line(surface, (24, 28, 37), shoulder.rounded(), elbow.rounded(), 17)
        pygame.draw.line(surface, skin, shoulder.rounded(), elbow.rounded(), 12)
        pygame.draw.line(surface, (24, 28, 37), elbow.rounded(), hand.rounded(), 14)
        pygame.draw.line(surface, skin, elbow.rounded(), hand.rounded(), 10)
        pygame.draw.circle(surface, skin, hand.rounded(), 7)
        pygame.draw.circle(surface, (235, 177, 143), hand.rounded(), 3, 1)

    def _draw_fingers(self, surface: pygame.Surface, left: Vec2,
                      right: Vec2, skin: tuple[int, int, int]) -> None:
        for hand in (left, right):
            for finger in range(3):
                offset = finger-1
                pygame.draw.line(surface, skin, hand.rounded(),
                                 (round(hand.x+offset*4), round(hand.y-7-abs(offset)*2)), 2)

    def _draw_head(self, surface: pygame.Surface, player: Player, pose) -> None:
        head = pose.head
        radius = 21
        pygame.draw.circle(surface, (25, 20, 23), head.rounded(), radius+2)
        pygame.draw.circle(surface, player.team.skin, head.rounded(), radius)
        hair_rect = pygame.Rect(round(head.x-radius), round(head.y-radius-2), radius*2, radius*1.05)
        pygame.draw.arc(surface, (30, 26, 31), hair_rect, math.pi, math.tau, 6)
        eye_direction = player.facing
        eye_x = head.x+eye_direction*6
        pygame.draw.circle(surface, (22, 20, 25), (round(eye_x), round(head.y-1)), 2)
        mouth = pygame.Rect(round(head.x-5), round(head.y+6), 11, 6)
        pygame.draw.arc(surface, (78, 45, 43), mouth, math.radians(195), math.radians(345), 2)
        pygame.draw.line(surface, player.team.accent,
                         (head.x-13, head.y-14), (head.x+13, head.y-14), 3)

    def _draw_selection_ring(self, surface: pygame.Surface,
                             player: Player, alpha: float) -> None:
        position = player.previous_position.lerp_to(player.position, alpha)
        pulse = 1+math.sin(player.animation_time*4)*.04
        rect = pygame.Rect(round(position.x-39*pulse), round(COURT_FLOOR-5),
                           round(78*pulse), 17)
        pygame.draw.ellipse(surface, player.team.accent, rect, 2)


class BasketballRenderer:
    """Layered orange ball with seam rotation, specular highlight, and trail."""

    def draw(self, surface: pygame.Surface, ball: Ball, alpha: float = 1.0) -> None:
        position = ball.interpolated_position(alpha)
        self._draw_trail(surface, ball)
        radius = BALL_RADIUS
        center = position.rounded()
        pygame.draw.circle(surface, (52, 33, 22), (center[0]+2, center[1]+3), radius+2)
        pygame.draw.circle(surface, BALL_ORANGE, center, radius)
        pygame.draw.circle(surface, (255, 172, 79), (center[0]-4, center[1]-5), radius-4)
        pygame.draw.circle(surface, (112, 55, 27), center, radius, 2)
        self._draw_seams(surface, position, radius, ball.rotation)
        pygame.draw.ellipse(surface, (255, 228, 171),
                            (center[0]-8, center[1]-10, 8, 5))

    def _draw_trail(self, surface: pygame.Surface, ball: Ball) -> None:
        for index, point in enumerate(ball.trail):
            fraction = (index+1)/max(1, len(ball.trail))
            radius = max(2, int(BALL_RADIUS*fraction*.55))
            color = (int(160+60*fraction), int(86+35*fraction), 43)
            pygame.draw.circle(surface, color, point.rounded(), radius)

    def _draw_seams(self, surface: pygame.Surface, center: Vec2,
                    radius: float, rotation: float) -> None:
        seam = (104, 49, 24)
        rect = pygame.Rect(round(center.x-radius+2), round(center.y-radius+2),
                           round((radius-2)*2), round((radius-2)*2))
        pygame.draw.arc(surface, seam, rect,
                        rotation, rotation+math.pi*.92, 2)
        pygame.draw.arc(surface, seam, rect,
                        rotation+math.pi, rotation+math.pi*1.92, 2)
        line_angle = rotation*.48
        direction = Vec2(math.cos(line_angle), math.sin(line_angle))*radius
        pygame.draw.line(surface, seam,
                         (center-direction).rounded(), (center+direction).rounded(), 2)


class HUDRenderer:
    """Broadcast scoreboard, action meters, instructions, and overlays."""

    def __init__(self) -> None:
        self.fonts = FontBook()
        self.text = TextPainter(self.fonts)
        self.panel_cache: dict[tuple[int, int], pygame.Surface] = {}
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def draw_scoreboard(self, surface: pygame.Surface, game) -> None:
        pygame.draw.rect(surface, (9, 15, 29), (365, 7, 550, 91), border_radius=14)
        pygame.draw.rect(surface, (62, 81, 116), (365, 7, 550, 91), 2, border_radius=14)
        label = f"{game.period_label()}     {game.clock_text()}"
        self.text.draw(surface, label, (640, 24), 15, GOLD, True)
        self.text.draw(surface, f"{game.scores[0]}", (476, 62), 32, BLUE, True)
        self.text.draw(surface, "BLUE CITY", (421, 66), 11, (201, 224, 255), True)
        self.text.draw(surface, f"{game.scores[1]}", (803, 62), 32, RED, True)
        self.text.draw(surface, "RED STORM", (856, 66), 11, (255, 206, 208), True)
        self._draw_period_ticks(surface, game)
        self._draw_shot_clock(surface, game)
        self._draw_possession(surface, game)
        self._draw_run(surface, game)

    def _draw_period_ticks(self, surface: pygame.Surface, game) -> None:
        start_x = 540
        for index in range(4):
            rect = pygame.Rect(start_x+index*31, 88, 25, 3)
            if game.overtime:
                color = GOLD
            elif index < game.quarter-1:
                color = (128, 151, 183)
            elif index == game.quarter-1:
                color = GOLD
            else:
                color = (42, 55, 78)
            pygame.draw.rect(surface, color, rect, border_radius=2)

    def _draw_shot_clock(self, surface: pygame.Surface, game) -> None:
        text = f"SHOT CLOCK  {game.shot_clock_text()}"
        color = RED if game.shot_clock < 4 else GOLD
        scale = 1.0+max(0.0, 4-game.shot_clock)*.02
        self.text.draw(surface, text, (640, 112), int(13*scale), color, True)

    def _draw_possession(self, surface: pygame.Surface, game) -> None:
        for team_id, x in ((0, 164), (1, 1116)):
            team = TEAMS[team_id]
            owns = game.ball.owner == team_id
            label = "BALL CONTROL" if owns else "DEFENSE"
            color = team.jersey if owns else (139, 153, 177)
            self.text.pill(surface, f"{team.short_name}  •  {label}", (x, 45), color, 11)

    def _draw_run(self, surface: pygame.Surface, game) -> None:
        if game.streak_count < 2:
            return
        team = TEAMS[game.streak_team]
        pulse = 1.0+math.sin(self.elapsed*8.0)*.06
        box = pygame.Rect(555, 126, 170, 31)
        pygame.draw.rect(surface, (10, 17, 30), box, border_radius=15)
        pygame.draw.rect(surface, team.jersey, box, 2, border_radius=15)
        self.text.draw(surface, f"HEATER x{game.streak_count}",
                       (640, 141), int(14*pulse), GOLD, True)

    def draw_player_hud(self, surface: pygame.Surface, team_id: int,
                        player: Player, window: ShotWindow,
                        charge: float | None, steal_cooldown: float,
                        timeouts: int, controls: tuple[str, ...]) -> None:
        x = 29 if team_id == 0 else VIRTUAL_WIDTH-29
        anchor = "left" if team_id == 0 else "right"
        box_x = 29 if team_id == 0 else VIRTUAL_WIDTH-267
        box = pygame.Rect(box_x, 488, 238, 99)
        self._panel(surface, box, alpha=224)
        team = TEAMS[team_id]
        self.text.draw(surface, team.name, (box_x+14 if team_id == 0 else box.right-14,
                                            502), 13, team.accent, True, anchor)
        shot_label = "THREE-POINTER" if window.is_three else "MID-RANGE"
        self.text.draw(surface, shot_label, (box_x+14 if team_id == 0 else box.right-14,
                                            519), 9, (207, 219, 239), True, anchor)
        self._draw_shot_meter(surface, box_x, box.y+38, box.width, window, charge,
                              team.jersey)
        self._draw_stamina(surface, box_x+12, box.y+67,
                           box.width-24, player.energy_fraction, team.jersey)
        steal_label = "STEAL READY" if steal_cooldown <= 0 else f"STEAL {steal_cooldown:.1f}s"
        cooldown_label = f"TO {timeouts}   |   {steal_label}"
        self.text.draw(surface, cooldown_label,
                       (box_x+13 if team_id == 0 else box.right-13, box.bottom-8),
                       8, GOLD if steal_cooldown <= 0 else (151, 162, 181), True, anchor)

    def _draw_shot_meter(self, surface: pygame.Surface, x: int, y: int,
                         width: int, window: ShotWindow, charge: float | None,
                         accent: tuple[int, int, int]) -> None:
        bar = pygame.Rect(x+12, y, width-24, 13)
        pygame.draw.rect(surface, (44, 53, 70), bar, border_radius=6)
        start = bar.left+int(bar.width*window.start)
        end = bar.left+int(bar.width*window.end)
        red_rect = pygame.Rect(bar.left, bar.top, max(0, start-bar.left), bar.height)
        green_rect = pygame.Rect(start, bar.top, max(1, end-start), bar.height)
        yellow_rect = pygame.Rect(end, bar.top, max(0, bar.right-end), bar.height)
        pygame.draw.rect(surface, (238, 86, 90), red_rect, border_radius=6)
        pygame.draw.rect(surface, GREEN, green_rect, border_radius=4)
        pygame.draw.rect(surface, (227, 172, 68), yellow_rect, border_radius=6)
        if charge is not None:
            marker_x = int(bar.left+bar.width*clamp(charge, 0.0, 1.0))
            pygame.draw.line(surface, (255, 255, 255), (marker_x, bar.top-4),
                             (marker_x, bar.bottom+4), 3)
            pygame.draw.circle(surface, accent, (marker_x, bar.centery), 4)

    def _draw_stamina(self, surface: pygame.Surface, x: int, y: int,
                      width: int, energy: float,
                      accent: tuple[int, int, int]) -> None:
        label = self.fonts.get(8, True).render("ENERGY", True, (201, 213, 232))
        surface.blit(label, (x, y-1))
        bar_x = x+44
        bar_width = width-44
        pygame.draw.rect(surface, (35, 44, 60), (bar_x, y, bar_width, 7), border_radius=3)
        fill_width = int(bar_width*clamp(energy, 0.0, 1.0))
        if fill_width:
            color = GREEN if energy > .3 else GOLD
            pygame.draw.rect(surface, color, (bar_x, y, fill_width, 7), border_radius=3)

    def draw_event(self, surface: pygame.Surface, message: str,
                   timer: float, color: tuple[int, int, int] = GOLD) -> None:
        if timer <= 0 or not message:
            return
        pulse = 1.0+math.sin(self.elapsed*9)*.025
        size = int(22*pulse)
        alpha = min(255, int(timer*330))
        text_surface = self.fonts.get(size, True).render(message, True, color)
        text_surface.set_alpha(alpha)
        rect = text_surface.get_rect(center=(VIRTUAL_WIDTH//2, 180))
        shadow = self.fonts.get(size, True).render(message, True, (0, 0, 0))
        shadow.set_alpha(alpha//2)
        surface.blit(shadow, rect.move(2, 3))
        surface.blit(text_surface, rect)

    def draw_instructions(self, surface: pygame.Surface, muted: bool) -> None:
        panel = pygame.Rect(170, VIRTUAL_HEIGHT-65, VIRTUAL_WIDTH-340, 34)
        pygame.draw.rect(surface, (8, 14, 26), panel, border_radius=12)
        pygame.draw.rect(surface, (50, 66, 92), panel, 1, border_radius=12)
        text = "BLUE  A/D MOVE  W JUMP  E SPRINT  HOLD F SHOOT  G DUNK  S STEAL  Q CROSS"
        text += "     •     RED  ARROWS MOVE  UP JUMP  RSHIFT SPRINT  J SHOOT  K DUNK  H STEAL  U CROSS"
        self.text.draw(surface, text, panel.center, 10, (220, 228, 241), True, shadow=False)
        state = "SOUND OFF" if muted else "M SOUND  •  P PAUSE  •  C CONTROLS  •  ESC QUIT"
        self.text.draw(surface, state, (VIRTUAL_WIDTH//2, panel.bottom+16), 9,
                       (156, 174, 201), True, shadow=False)

    def draw_pause(self, surface: pygame.Surface) -> None:
        self._draw_dim(surface, 135)
        self._draw_card(surface, pygame.Rect(375, 220, 530, 280), "PAUSED",
                        ("P  RESUME", "C  CONTROLS", "R  RESTART MATCH", "ESC  QUIT"))

    def draw_help(self, surface: pygame.Surface) -> None:
        self._draw_dim(surface, 168)
        rect = pygame.Rect(250, 104, 780, 514)
        self._panel(surface, rect, alpha=246, outline=(91, 117, 157))
        self.text.draw(surface, "CONTROLS & GAMEPLAY", (640, 138), 25, GOLD, True)
        left_rows = ("A / D   MOVE", "W   JUMP / BLOCK", "E   SPRINT",
                     "HOLD F   SHOOT", "G   DUNK NEAR THE RIM",
                     "S   STEAL NEAR YOUR OPPONENT", "Q   CROSSOVER", "T   TIMEOUT")
        right_rows = ("ARROWS   MOVE", "UP   JUMP / BLOCK", "RIGHT SHIFT   SPRINT",
                      "HOLD J   SHOOT", "K   DUNK NEAR THE RIM",
                      "H   STEAL NEAR YOUR OPPONENT", "U   CROSSOVER", "Y   TIMEOUT")
        self.text.draw(surface, "BLUE CITY", (450, 187), 16, BLUE, True)
        self.text.draw(surface, "RED STORM", (830, 187), 16, RED, True)
        for row, (left, right) in enumerate(zip(left_rows, right_rows)):
            y = 224+row*31
            self.text.draw(surface, left, (355, y), 13, (237, 241, 249), False, "left")
            self.text.draw(surface, right, (735, y), 13, (237, 241, 249), False, "left")
        explanations = (
            "Release a normal shot in the green timing zone.",
            "Three-pointers have a smaller green window. Sprinting, moving, fatigue, and close defense shrink it.",
            "Missed shots stay live. Move within arm reach to catch them; rebounds are not automatic pickups.",
            "A regulation match is four one-minute quarters. Tied games play short overtime periods.",
        )
        for index, line in enumerate(explanations):
            self.text.draw(surface, line, (640, 496+index*25), 11,
                           (193, 207, 228), False)
        self.text.draw(surface, "C  CLOSE CONTROLS", (640, 598), 12, GREEN, True)

    def draw_final_box(self, surface: pygame.Surface, game) -> None:
        self._draw_dim(surface, 185)
        rect = pygame.Rect(160, 105, 960, 530)
        self._panel(surface, rect, alpha=248, outline=(106, 129, 166))
        self.text.draw(surface, "FINAL SCORE", (640, 143), 21, GOLD, True)
        winner = game.winner_text()
        self.text.draw(surface, winner, (640, 181), 29, (245, 248, 255), True)
        self.text.draw(surface, f"{game.scores[0]}", (490, 233), 44, BLUE, True)
        self.text.draw(surface, "BLUE CITY", (425, 235), 14, (195, 222, 255), True)
        self.text.draw(surface, f"{game.scores[1]}", (790, 233), 44, RED, True)
        self.text.draw(surface, "RED STORM", (855, 235), 14, (255, 205, 209), True)
        columns = ("TEAM", "PTS", "FG", "3PT", "DUNK", "STL", "BLK", "REB", "TO")
        x_positions = (260, 375, 465, 565, 670, 760, 840, 930, 1020)
        for x, heading in zip(x_positions, columns):
            self.text.draw(surface, heading, (x, 300), 11, (139, 165, 204), True)
        for team_id, y in ((0, 341), (1, 382)):
            stat = game.players[team_id].stats
            values = (
                TEAMS[team_id].short_name,
                str(stat.points),
                f"{stat.fgm}/{stat.fga}",
                f"{stat.three_made}/{stat.three_attempted}",
                str(stat.dunks),
                str(stat.steals),
                str(stat.blocks),
                str(stat.rebounds),
                str(stat.turnovers),
            )
            color = BLUE if team_id == 0 else RED
            for x, value in zip(x_positions, values):
                self.text.draw(surface, value, (x, y), 12, color, True)
        self.text.draw(surface, f"PERFECT RELEASES    BLUE {game.players[0].stats.perfect_releases}  •  RED {game.players[1].stats.perfect_releases}",
                       (640, 432), 12, (205, 216, 233))
        self.text.draw(surface, "R  REMATCH", (640, 505), 17, GREEN, True)
        self.text.draw(surface, "ESC  QUIT", (640, 542), 11, (158, 177, 204), True)

    def _draw_card(self, surface: pygame.Surface, rect: pygame.Rect,
                   title: str, rows: tuple[str, ...]) -> None:
        self._panel(surface, rect, alpha=245, outline=(94, 122, 164))
        self.text.draw(surface, title, rect.midtop, 28, GOLD, True)
        for index, row in enumerate(rows):
            self.text.draw(surface, row, (rect.centerx, rect.y+94+index*34),
                           16, (232, 238, 248), True)

    def _draw_dim(self, surface: pygame.Surface, alpha: int) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((3, 7, 15, alpha))
        surface.blit(overlay, (0, 0))

    def _panel(self, surface: pygame.Surface, rect: pygame.Rect,
               alpha: int = 232,
               outline: tuple[int, int, int] = (55, 73, 103)) -> None:
        cache_key = rect.size
        if cache_key not in self.panel_cache:
            panel = pygame.Surface(cache_key, pygame.SRCALPHA)
            pygame.draw.rect(panel, (8, 15, 29, alpha), panel.get_rect(), border_radius=16)
            pygame.draw.rect(panel, (*outline, 220), panel.get_rect(), 2, border_radius=16)
            self.panel_cache[cache_key] = panel
        surface.blit(self.panel_cache[cache_key], rect.topleft)

