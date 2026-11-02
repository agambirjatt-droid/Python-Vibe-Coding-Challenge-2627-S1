"""Keyboard and optional gamepad routing for local two-player games."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .settings import TEAMS


@dataclass(slots=True)
class PlayerInput:
    """One frame of normalized controls for a single player."""

    move_x: float = 0.0
    jump: bool = False
    jump_pressed: bool = False
    shoot: bool = False
    shoot_pressed: bool = False
    shoot_released: bool = False
    dunk_pressed: bool = False
    steal_pressed: bool = False
    crossover_pressed: bool = False
    sprint: bool = False
    timeout_pressed: bool = False
    taunt_pressed: bool = False

    @property
    def moving(self) -> bool:
        return abs(self.move_x) > 0.01

    @property
    def moving_toward_right(self) -> bool:
        return self.move_x > 0.01

    @property
    def moving_toward_left(self) -> bool:
        return self.move_x < -0.01

    def clear_edges(self) -> None:
        self.jump_pressed = False
        self.shoot_pressed = False
        self.shoot_released = False
        self.dunk_pressed = False
        self.steal_pressed = False
        self.crossover_pressed = False
        self.timeout_pressed = False
        self.taunt_pressed = False


class InputRouter:
    """Tracks edge-triggered input separately from held input.

    Edge state prevents key repeat from retriggering jumps, crossovers, and
    timeouts. Held state powers smooth movement, sprinting, and shot charging.
    """

    def __init__(self) -> None:
        self.held: set[int] = set()
        self.pressed: set[int] = set()
        self.released: set[int] = set()
        self.players = [PlayerInput(), PlayerInput()]
        self.quit_requested = False
        self.pause_pressed = False
        self.help_pressed = False
        self.sound_pressed = False
        self.restart_pressed = False
        self.window_resized = False
        self.resized_to = (0, 0)
        self.gamepad = None
        self.gamepad_axes = [0.0, 0.0]
        self.gamepad_buttons: set[int] = set()
        self.try_attach_gamepad()

    def try_attach_gamepad(self) -> None:
        """Attach the first controller if one is present; keyboard still works."""
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.gamepad = pygame.joystick.Joystick(0)
                self.gamepad.init()
        except pygame.error:
            self.gamepad = None

    def begin_frame(self) -> None:
        """Reset window-level edges before collecting this frame's events.

        Player action edges stay queued until a fixed simulation step consumes
        them, so a very short render frame cannot swallow a key press.
        """
        self.pressed.clear()
        self.released.clear()
        self.pause_pressed = False
        self.help_pressed = False
        self.sound_pressed = False
        self.restart_pressed = False
        self.window_resized = False

    def consume_edges(self) -> None:
        """Consume one-shot actions after a single simulation update.

        Rendering can run at a different rate than the fixed physics loop. If
        an edge were left set for every catch-up step, one key press could
        trigger a timeout or restart a shot several times in the same frame.
        """
        self.pressed.clear()
        self.released.clear()
        for player in self.players:
            player.clear_edges()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Record one SDL event without performing game logic here."""
        if event.type == pygame.QUIT:
            self.quit_requested = True
            return
        if event.type == pygame.VIDEORESIZE:
            self.window_resized = True
            self.resized_to = (event.w, event.h)
            return
        if event.type == pygame.KEYDOWN:
            self._handle_key_down(event.key)
            return
        if event.type == pygame.KEYUP:
            self._handle_key_up(event.key)
            return
        if event.type == pygame.JOYAXISMOTION:
            self._handle_joystick_axis(event)
            return
        if event.type == pygame.JOYBUTTONDOWN:
            self.gamepad_buttons.add(event.button)
            return
        if event.type == pygame.JOYBUTTONUP:
            self.gamepad_buttons.discard(event.button)

    def _handle_key_down(self, key: int) -> None:
        if key not in self.held:
            self.pressed.add(key)
        self.held.add(key)
        if key == pygame.K_ESCAPE:
            self.quit_requested = True
        elif key == pygame.K_p:
            self.pause_pressed = True
        elif key == pygame.K_c:
            self.help_pressed = True
        elif key == pygame.K_m:
            self.sound_pressed = True
        elif key == pygame.K_r:
            self.restart_pressed = True
        for index, team in enumerate(TEAMS):
            if key == team.keys["jump"]:
                self.players[index].jump_pressed = True
            elif key == team.keys["shoot"]:
                self.players[index].shoot_pressed = True
            elif key == team.keys["dunk"]:
                self.players[index].dunk_pressed = True
            elif key == team.keys["steal"]:
                self.players[index].steal_pressed = True
            elif key == team.keys["cross"]:
                self.players[index].crossover_pressed = True
            elif key == team.keys["timeout"]:
                self.players[index].timeout_pressed = True
            elif key == pygame.K_1 + index:
                self.players[index].taunt_pressed = True

    def _handle_key_up(self, key: int) -> None:
        if key in self.held:
            self.held.remove(key)
        self.released.add(key)
        for index, team in enumerate(TEAMS):
            if key == team.keys["shoot"]:
                self.players[index].shoot_released = True

    def _handle_joystick_axis(self, event: pygame.event.Event) -> None:
        if event.axis in (0, 1):
            self.gamepad_axes[event.axis] = event.value

    def is_held(self, key: int) -> bool:
        return key in self.held

    def was_pressed(self, key: int) -> bool:
        return key in self.pressed

    def was_released(self, key: int) -> bool:
        return key in self.released

    def build_player_inputs(self) -> tuple[PlayerInput, PlayerInput]:
        """Build both players' controls from their configured key bindings."""
        result = []
        for index, team in enumerate(TEAMS):
            state = self.players[index]
            left_held = self.is_held(team.keys["left"])
            right_held = self.is_held(team.keys["right"])
            state.move_x = float(right_held)-float(left_held)
            state.jump = self.is_held(team.keys["jump"])
            state.shoot = self.is_held(team.keys["shoot"])
            state.sprint = self.is_held(team.keys["sprint"])
            result.append(state)
        self._apply_gamepad(result)
        return result[0], result[1]

    def _apply_gamepad(self, result: list[PlayerInput]) -> None:
        """Allow one optional controller to drive the red team's movement."""
        if self.gamepad is None:
            return
        axis = self.gamepad_axes[0]
        if abs(axis) > 0.18:
            result[1].move_x = axis
        try:
            if self.gamepad.get_button(0):
                result[1].jump = True
            if self.gamepad.get_button(1):
                result[1].shoot = True
            if self.gamepad.get_button(2):
                result[1].dunk_pressed = True
            if self.gamepad.get_button(3):
                result[1].steal_pressed = True
        except pygame.error:
            self.gamepad = None

    def clear_player_keys(self) -> None:
        """Release held movement and action keys, useful when pausing/focus loss."""
        self.held.clear()
        self.pressed.clear()
        self.released.clear()
        for player in self.players:
            player.clear_edges()
            player.move_x = 0.0
            player.jump = False
            player.shoot = False
            player.sprint = False

    def handle_focus_lost(self) -> None:
        """Prevent a stuck sprint or shot if the game window loses focus."""
        self.clear_player_keys()

    def handle_focus_gained(self) -> None:
        """Reset old edge data when the game window regains focus."""
        self.pressed.clear()
        self.released.clear()

    def player_key_legend(self, index: int) -> tuple[str, ...]:
        """Return a concise control legend for help panels and instructions."""
        if index == 0:
            return (
                "A / D MOVE",
                "W JUMP",
                "E SPRINT",
                "HOLD F SHOOT",
                "G DUNK",
                "S STEAL",
                "Q CROSSOVER",
                "T TIMEOUT",
            )
        return (
            "ARROWS MOVE",
            "UP JUMP",
            "RIGHT SHIFT SPRINT",
            "HOLD J SHOOT",
            "K DUNK",
            "H STEAL",
            "U CROSSOVER",
            "Y TIMEOUT",
        )

    def global_key_legend(self) -> tuple[str, ...]:
        return (
            "P PAUSE",
            "C CONTROLS",
            "M SOUND",
            "R REMATCH",
            "ESC QUIT",
        )

