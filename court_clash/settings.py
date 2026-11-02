"""Shared settings and small data records for Court Clash.

All coordinates use the game's 1280 by 720 virtual canvas. Rendering scales the
finished frame to the real window size, so the simulation keeps one stable set
of court measurements on every display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Final


VIRTUAL_WIDTH: Final[int] = 1280
VIRTUAL_HEIGHT: Final[int] = 720
TARGET_FPS: Final[int] = 120
FIXED_STEP: Final[float] = 1.0 / 120.0
MAX_FRAME_TIME: Final[float] = 0.16

COURT_LEFT: Final[float] = 58.0
COURT_RIGHT: Final[float] = 1222.0
COURT_TOP: Final[float] = 276.0
COURT_FLOOR: Final[float] = 602.0
COURT_CENTER_X: Final[float] = VIRTUAL_WIDTH / 2
HOOP_LEFT_X: Final[float] = 98.0
HOOP_RIGHT_X: Final[float] = 1182.0
HOOP_Y: Final[float] = 353.0
RIM_WIDTH: Final[float] = 58.0
BACKBOARD_OFFSET: Final[float] = 42.0
PLAYER_FLOOR_Y: Final[float] = COURT_FLOOR

QUARTER_SECONDS: Final[float] = 60.0
OVERTIME_SECONDS: Final[float] = 20.0
SHOT_CLOCK_SECONDS: Final[float] = 12.0
TIMEOUT_COUNT: Final[int] = 2

BALL_RADIUS: Final[float] = 15.0
BALL_GRAVITY: Final[float] = 760.0
PLAYER_RADIUS: Final[float] = 24.0
PLAYER_MAX_SPEED: Final[float] = 390.0
PLAYER_ACCELERATION: Final[float] = 2050.0
PLAYER_DRAG: Final[float] = 8.5
PLAYER_JUMP_SPEED: Final[float] = 620.0
PLAYER_GRAVITY: Final[float] = 1680.0
PLAYER_REACH: Final[float] = 106.0
THREE_POINT_DISTANCE: Final[float] = 382.0
DUNK_DISTANCE: Final[float] = 156.0

BLACK: Final[tuple[int, int, int]] = (7, 10, 18)
INK: Final[tuple[int, int, int]] = (11, 17, 30)
ARENA_NAVY: Final[tuple[int, int, int]] = (12, 20, 39)
STAND_BLUE: Final[tuple[int, int, int]] = (25, 37, 62)
WOOD_LIGHT: Final[tuple[int, int, int]] = (207, 139, 83)
WOOD_DARK: Final[tuple[int, int, int]] = (145, 84, 48)
COURT_WHITE: Final[tuple[int, int, int]] = (255, 241, 218)
GOLD: Final[tuple[int, int, int]] = (255, 207, 91)
GREEN: Final[tuple[int, int, int]] = (73, 221, 142)
RED: Final[tuple[int, int, int]] = (255, 92, 106)
BLUE: Final[tuple[int, int, int]] = (53, 148, 255)
SKIN_BLUE: Final[tuple[int, int, int]] = (176, 105, 72)
SKIN_RED: Final[tuple[int, int, int]] = (129, 73, 55)
BALL_ORANGE: Final[tuple[int, int, int]] = (239, 128, 39)


class GamePhase(Enum):
    """Top-level modes used by the match controller and the HUD."""

    TIP_OFF = auto()
    LIVE = auto()
    QUARTER_BREAK = auto()
    PAUSED = auto()
    FINAL = auto()


class BallMode(Enum):
    """Ball states control whether it follows a player or simulates freely."""

    HELD = auto()
    SHOT = auto()
    DUNK = auto()
    LOOSE = auto()
    MADE = auto()


@dataclass(frozen=True, slots=True)
class TeamConfig:
    """Identity, palette, and local keyboard bindings for one side."""

    name: str
    short_name: str
    jersey: tuple[int, int, int]
    jersey_shadow: tuple[int, int, int]
    skin: tuple[int, int, int]
    accent: tuple[int, int, int]
    start_x: float
    initial_attack: int
    keys: dict[str, int]


BLUE_TEAM: Final[TeamConfig] = TeamConfig(
    name="BLUE CITY",
    short_name="BLUE",
    jersey=BLUE,
    jersey_shadow=(23, 91, 187),
    skin=SKIN_BLUE,
    accent=(173, 220, 255),
    start_x=355.0,
    initial_attack=1,
    keys={
        "left": 97,
        "right": 100,
        "jump": 119,
        "shoot": 102,
        "dunk": 103,
        "steal": 115,
        "cross": 113,
        "sprint": 101,
        "timeout": 116,
    },
)

RED_TEAM: Final[TeamConfig] = TeamConfig(
    name="RED STORM",
    short_name="RED",
    jersey=RED,
    jersey_shadow=(177, 46, 63),
    skin=SKIN_RED,
    accent=(255, 195, 190),
    start_x=925.0,
    initial_attack=-1,
    keys={
        "left": 1073741904,
        "right": 1073741903,
        "jump": 1073741906,
        "shoot": 106,
        "dunk": 107,
        "steal": 104,
        "cross": 117,
        "sprint": 1073742053,
        "timeout": 121,
    },
)

TEAMS: Final[tuple[TeamConfig, TeamConfig]] = (BLUE_TEAM, RED_TEAM)


@dataclass(slots=True)
class ShotWindow:
    """Current shot meter window and the conditions that affect its width."""

    start: float = 0.0
    end: float = 1.0
    is_three: bool = False
    contested: bool = False
    moving: bool = False
    tired: bool = False
    label: str = "2 POINT"

    @property
    def center(self) -> float:
        return (self.start + self.end) * 0.5

    @property
    def width(self) -> float:
        return max(0.0, self.end - self.start)

    def contains(self, release: float) -> bool:
        return self.start <= release <= self.end


@dataclass(slots=True)
class GameStats:
    """Traditional box-score counters plus arcade-specific clean releases."""

    points: int = 0
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    threes_made: int = 0
    threes_attempted: int = 0
    dunks: int = 0
    steals: int = 0
    blocks: int = 0
    rebounds: int = 0
    turnovers: int = 0
    assists: int = 0
    perfect_releases: int = 0
    timeouts: int = 0

    def record_attempt(self, is_three: bool) -> None:
        self.field_goals_attempted += 1
        if is_three:
            self.threes_attempted += 1

    def record_make(self, points: int, is_three: bool, is_dunk: bool) -> None:
        self.points += points
        self.field_goals_made += 1
        if is_three:
            self.threes_made += 1
        if is_dunk:
            self.dunks += 1

    def percent(self, made: int, attempted: int) -> str:
        if attempted == 0:
            return "—"
        return f"{round(made / attempted * 100)}%"

    @property
    def field_goal_percent(self) -> str:
        return self.percent(self.field_goals_made, self.field_goals_attempted)

    @property
    def three_point_percent(self) -> str:
        return self.percent(self.threes_made, self.threes_attempted)


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a scalar into an inclusive range."""
    return max(low, min(high, value))


def lerp(start: float, end: float, amount: float) -> float:
    """Interpolate between two scalars using an amount from zero to one."""
    return start + (end-start) * clamp(amount, 0.0, 1.0)


def smoothstep(amount: float) -> float:
    """Smooth animation curves at their endpoints."""
    value = clamp(amount, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def format_clock(seconds: float) -> str:
    """Format a countdown to whole seconds without rounding upward."""
    whole = max(0, int(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def scale_rgba(color: tuple[int, int, int], alpha: int) -> tuple[int, int, int, int]:
    """Attach a clamped alpha channel to a normal RGB color."""
    return color[0], color[1], color[2], int(clamp(alpha, 0, 255))

