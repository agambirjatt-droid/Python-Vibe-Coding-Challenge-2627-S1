"""Main match simulation and fixed-step Pygame application loop."""

from __future__ import annotations

import math
import random
import sys

import pygame

from .arena import ArenaRenderer
from .audio import AudioBus
from .controls import InputRouter, PlayerInput
from .effects import CameraRig, ParticleSystem
from .entities import Ball, Player
from .settings import (
    BALL_RADIUS,
    BACKBOARD_OFFSET,
    BLACK,
    COURT_FLOOR,
    COURT_LEFT,
    COURT_RIGHT,
    DUNK_DISTANCE,
    FIXED_STEP,
    BallMode,
    GamePhase,
    HOOP_LEFT_X,
    HOOP_RIGHT_X,
    HOOP_Y,
    MAX_FRAME_TIME,
    OVERTIME_SECONDS,
    PLAYER_RADIUS,
    QUARTER_SECONDS,
    SHOT_CLOCK_SECONDS,
    TEAMS,
    THREE_POINT_DISTANCE,
    TARGET_FPS,
    VIRTUAL_HEIGHT,
    VIRTUAL_WIDTH,
    ShotWindow,
    clamp,
    format_clock,
)
from .ui import BasketballRenderer, HUDRenderer, PlayerRenderer
from .vector import Vec2


class CourtClashGame:
    """Two-player arcade basketball match with smooth fixed-step simulation."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("COURT CLASH  |  Local Arcade Basketball")
        self.window = pygame.display.set_mode((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.RESIZABLE)
        self.world = pygame.Surface((VIRTUAL_WIDTH, VIRTUAL_HEIGHT)).convert()
        self.scaled_surface: pygame.Surface | None = None
        self.scaled_size = (0, 0)
        self.clock = pygame.time.Clock()
        self.accumulator = 0.0
        self.running = True
        self.router = InputRouter()
        self.audio = AudioBus()
        self.arena = ArenaRenderer()
        self.effects = ParticleSystem()
        self.camera = CameraRig()
        self.player_renderer = PlayerRenderer()
        self.ball_renderer = BasketballRenderer()
        self.hud = HUDRenderer()
        self.fullscreen = False
        self.muted = False
        self.show_help = False
        self.return_phase = GamePhase.LIVE
        self.random = random.Random(81)
        self.reset_match()

    def reset_match(self) -> None:
        """Reset score, players, possession, timing, effects, and box score."""
        self.players = [
            Player(0, TEAMS[0], TEAMS[0].start_x),
            Player(1, TEAMS[1], TEAMS[1].start_x),
        ]
        self.attacks = [TEAMS[0].initial_attack, TEAMS[1].initial_attack]
        self.ball = Ball()
        self.ball.reset(0)
        self.ball.attach_to_player(self.players[0], self.attacks[0],
                                   self.players[0].animation_time)
        self.scores = [0, 0]
        self.quarter = 1
        self.overtime = 0
        self.game_clock = QUARTER_SECONDS
        self.shot_clock = SHOT_CLOCK_SECONDS
        self.break_timer = 0.0
        self.phase = GamePhase.LIVE
        self.return_phase = GamePhase.LIVE
        self.broadcast = "TIP OFF!  BLUE CITY HAS POSSESSION"
        self.broadcast_timer = 2.3
        self.streak_team: int | None = None
        self.streak_count = 0
        self.charge = [0.0, 0.0]
        self.charge_active = [False, False]
        self.steal_cooldown = [0.0, 0.0]
        self.timeouts = [2, 2]
        self.held_timer = 0.0
        self.last_shot_team: int | None = None
        self.last_event_score = 0
        self.effects.clear()
        self.camera.reset()
        self.arena.net_energy = [0.0, 0.0]
        self.arena.flash_boards = [0.0, 0.0]

    def run(self) -> None:
        """Run fixed physics steps and render as smoothly as the display allows."""
        try:
            while self.running:
                frame_seconds = min(self.clock.tick(TARGET_FPS)/1000.0, MAX_FRAME_TIME)
                self._handle_events()
                self.accumulator += frame_seconds
                steps = 0
                while self.accumulator >= FIXED_STEP and steps < 18:
                    self._fixed_update(FIXED_STEP)
                    self.router.consume_edges()
                    self.accumulator -= FIXED_STEP
                    steps += 1
                if steps == 18:
                    self.accumulator = min(self.accumulator, FIXED_STEP)
                alpha = clamp(self.accumulator/FIXED_STEP, 0.0, 1.0)
                self._render(alpha)
                self._present()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self.audio.shutdown()
        pygame.quit()

    def _handle_events(self) -> None:
        self.router.begin_frame()
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self._toggle_fullscreen()
                continue
            if event.type == pygame.WINDOWFOCUSLOST:
                self.router.handle_focus_lost()
            elif event.type == pygame.WINDOWFOCUSGAINED:
                self.router.handle_focus_gained()
            elif event.type == pygame.WINDOWRESIZED:
                self._handle_resize(event)
            self.router.handle_event(event)
        if self.router.quit_requested:
            self.running = False
        if self.router.pause_pressed and self.phase != GamePhase.FINAL:
            self._toggle_pause()
        if self.router.help_pressed:
            self.show_help = not self.show_help
            self.router.clear_player_keys()
        if self.router.sound_pressed:
            self.muted = not self.muted
            self.audio.set_enabled(not self.muted)
            self.set_broadcast("SOUND ON" if not self.muted else "SOUND OFF", .8)
        if self.router.restart_pressed and self.phase == GamePhase.FINAL:
            self.reset_match()

    def _handle_resize(self, event: pygame.event.Event) -> None:
        width = max(640, event.w)
        height = max(360, event.h)
        if (width, height) != self.window.get_size():
            self.window = pygame.display.set_mode((width, height), pygame.RESIZABLE)

    def _toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode((VIRTUAL_WIDTH, VIRTUAL_HEIGHT), pygame.RESIZABLE)

    def _toggle_pause(self) -> None:
        if self.phase == GamePhase.PAUSED:
            self.phase = self.return_phase
            self.set_broadcast("BACK TO THE ACTION", .8)
        else:
            self.return_phase = self.phase
            self.phase = GamePhase.PAUSED
            self.charge_active = [False, False]
            self.charge = [0.0, 0.0]
            self.router.clear_player_keys()
            self.set_broadcast("GAME PAUSED", .8)

    def _fixed_update(self, dt: float) -> None:
        self.broadcast_timer = max(0.0, self.broadcast_timer-dt)
        self.hud.update(dt)
        self.effects.update(dt)
        self.arena.update(dt)
        self.camera.update(self._camera_target(), dt)
        if self.phase == GamePhase.PAUSED or self.show_help:
            return
        if self.phase == GamePhase.QUARTER_BREAK:
            self._update_break(dt)
            return
        if self.phase == GamePhase.FINAL:
            return
        if self.phase not in (GamePhase.LIVE, GamePhase.TIP_OFF):
            return
        controls = self.router.build_player_inputs()
        self._update_match_clock(dt)
        if self.phase not in (GamePhase.LIVE, GamePhase.TIP_OFF):
            return
        self._update_players(controls, dt)
        self._process_actions(controls)
        self._update_ball(dt)
        self._resolve_player_collision()
        self._update_shot_clock(dt)
        self._update_out_of_bounds()
        self._update_drift_effects(dt)

    def _update_break(self, dt: float) -> None:
        self.break_timer -= dt
        if self.break_timer > 0.0:
            return
        self.phase = GamePhase.LIVE
        self.set_broadcast("QUARTER START!", 1.0)

    def _update_match_clock(self, dt: float) -> None:
        self.game_clock = max(0.0, self.game_clock-dt)
        if self.game_clock > 0.0:
            return
        if self.quarter < 4:
            self._end_quarter()
            return
        if self.scores[0] == self.scores[1]:
            self.overtime += 1
            self.game_clock = OVERTIME_SECONDS
            self.phase = GamePhase.QUARTER_BREAK
            self.break_timer = 1.5
            self.set_broadcast(f"OVERTIME {self.overtime}  •  20 SECOND PERIOD", 1.5)
            return
        self.phase = GamePhase.FINAL
        self.audio.play("buzzer")
        self.set_broadcast("FINAL BUZZER!", 2.0)

    def _end_quarter(self) -> None:
        if self.quarter == 2:
            self.attacks = [-attack for attack in self.attacks]
            self.set_broadcast("HALFTIME  •  SWITCH SIDES", 1.6)
        else:
            self.set_broadcast(f"END OF QUARTER {self.quarter}", 1.6)
        self.quarter += 1
        self.game_clock = QUARTER_SECONDS
        self.phase = GamePhase.QUARTER_BREAK
        self.break_timer = 1.6
        self.charge_active = [False, False]

    def _update_players(self, controls: tuple[PlayerInput, PlayerInput], dt: float) -> None:
        for index, player in enumerate(self.players):
            defender = self.players[1-index]
            has_ball = self.ball.owner == index and self.ball.mode == BallMode.HELD
            near_defender = player.position.distance_to(defender.position) < 116
            effective_controls = controls[index]
            if self.ball.mode == BallMode.DUNK and self.ball.shooter == index:
                effective_controls = PlayerInput()
            player.update(effective_controls, dt, self.attacks[index],
                          has_ball, near_defender)
            if self.charge_active[index] and self.ball.owner == index:
                self.charge[index] = min(1.0, self.charge[index]+dt*1.18)
            self.steal_cooldown[index] = max(0.0, self.steal_cooldown[index]-dt)
        if self.ball.mode == BallMode.HELD and self.ball.owner is not None:
            owner = self.ball.owner
            self.ball.attach_to_player(self.players[owner], self.attacks[owner],
                                       self.players[owner].animation_time,
                                       self.charge_active[owner])

    def _process_actions(self, controls: tuple[PlayerInput, PlayerInput]) -> None:
        for index, action in enumerate(controls):
            if action.crossover_pressed:
                player = self.players[index]
                if player.begin_crossover() and self.ball.owner == index:
                    self.audio.play("crossover", .65)
                    self.effects.foot_dust(player.floor_point, player.team.accent)
            if action.shoot_pressed and self.ball.owner == index and self.ball.mode == BallMode.HELD:
                self.charge_active[index] = True
                self.charge[index] = 0.0
                self.players[index].begin_shot()
            if action.shoot_released and self.charge_active[index]:
                self._release_shot(index)
            if action.dunk_pressed:
                self._attempt_dunk(index)
            if action.steal_pressed:
                self._attempt_steal(index)
            if action.timeout_pressed:
                self._call_timeout(index)

    def shot_window(self, team: int) -> ShotWindow:
        player = self.players[team]
        defender = self.players[1-team]
        is_three = self.distance_to_basket(team) > THREE_POINT_DISTANCE
        width = .054 if is_three else .215
        center = .695 if is_three else .68
        contested = player.position.distance_to(defender.position) < 112
        moving = abs(player.velocity.x) > 105
        tired = player.stamina < 28
        sprinting = player.is_sprinting
        if contested:
            width *= .54 if is_three else .62
        if moving:
            width *= .76
        if sprinting:
            width *= .75
        if tired:
            width *= .80
        width = max(.016 if is_three else .055, width)
        return ShotWindow(center-width/2, center+width/2,
                          is_three, contested, moving, tired,
                          "THREE-POINTER" if is_three else "MID-RANGE")

    def _release_shot(self, team: int) -> None:
        self.charge_active[team] = False
        player = self.players[team]
        player.release_shot()
        window = self.shot_window(team)
        release = self.charge[team]
        distance_from_center = abs(release-window.center)
        half_width = max(.001, window.width*.5)
        timing_grade = clamp(1.0-distance_from_center/half_width, 0.0, 1.0)
        quality = timing_grade
        if window.contested:
            quality *= .76
        if window.moving:
            quality *= .86
        if window.tired:
            quality *= .83
        is_make_window = window.contains(release)
        if not is_make_window:
            quality *= .34
        points = 3 if window.is_three else 2
        player.stats.fga += 1
        if window.is_three:
            player.stats.three_attempted += 1
        if is_make_window and timing_grade > .88:
            player.stats.perfect_releases += 1
        accuracy = quality if is_make_window else min(.48, quality)
        hoop = self.hoop_for(team)
        self.ball.release_shot(player, self.attacks[team], hoop,
                               release, points, accuracy)
        self.last_shot_team = team
        if is_make_window and timing_grade >= .84:
            self.audio.play("perfect", .8)
            self.set_broadcast("PERFECT RELEASE!", .55)
        elif window.is_three:
            self.set_broadcast("DEEP THREE IN THE AIR...", .8)
        else:
            self.set_broadcast("SHOT UP!", .65)

    def _attempt_dunk(self, team: int) -> None:
        if self.ball.owner != team or self.ball.mode != BallMode.HELD:
            return
        player = self.players[team]
        hoop = self.hoop_for(team)
        distance = abs(hoop-player.position.x)
        if distance > DUNK_DISTANCE:
            self.set_broadcast("DRIVE CLOSER TO THE RIM TO DUNK", .8)
            return
        player.stats.fga += 1
        player.begin_dunk()
        self.ball.begin_dunk(player, self.attacks[team], hoop)
        self.audio.play("dunk", .9)
        self.camera.add_shake(3.8, .18)

    def _attempt_steal(self, defender_id: int) -> None:
        if self.ball.owner is None or self.ball.owner == defender_id:
            return
        if self.ball.mode != BallMode.HELD:
            return
        defender = self.players[defender_id]
        carrier = self.players[self.ball.owner]
        if self.steal_cooldown[defender_id] > 0:
            return
        self.steal_cooldown[defender_id] = .62
        distance = defender.position.distance_to(carrier.position)
        if distance > 82:
            self.set_broadcast("GET CLOSER TO REACH THE BALL", .5)
            return
        chance = .70 + defender.energy_fraction*.20
        chance -= .15 if carrier.cross_blend > .2 else 0.0
        if self.random.random() > chance:
            defender.apply_stun(.12)
            self.set_broadcast("REACH-IN! CROSSED UP", .6)
            return
        carrier.stats.turnovers += 1
        defender.stats.steals += 1
        defender.confirm_catch()
        self.ball.owner = defender_id
        self.ball.mode = BallMode.HELD
        self.ball.last_touch = defender_id
        self.shot_clock = SHOT_CLOCK_SECONDS
        self.audio.play("steal", .9)
        self.effects.steal(defender.center, defender.team.jersey)
        self.set_broadcast(f"{defender.team.short_name} STEAL!", .9)

    def _call_timeout(self, team: int) -> None:
        if self.ball.owner != team or self.ball.mode != BallMode.HELD:
            self.set_broadcast("TIMEOUT REQUIRES POSSESSION", .8)
            return
        if self.timeouts[team] <= 0:
            self.set_broadcast("NO TIMEOUTS LEFT", .8)
            return
        self.timeouts[team] -= 1
        player = self.players[team]
        player.stats.timeouts += 1
        player.stamina = min(100.0, player.stamina+45.0)
        self.shot_clock = max(12.0, self.shot_clock)
        self.return_phase = GamePhase.LIVE
        self.phase = GamePhase.QUARTER_BREAK
        self.break_timer = 2.2
        self.set_broadcast(f"{player.team.short_name} TIMEOUT", 2.0)
        self.audio.play("whistle", .65)

    def _update_ball(self, dt: float) -> None:
        if self.ball.mode == BallMode.HELD:
            return
        if self.ball.mode == BallMode.SHOT:
            self._try_block_shot()
        old_mode = self.ball.mode
        self.ball.update(dt, HOOP_Y, COURT_FLOOR)
        if old_mode == BallMode.SHOT:
            self._check_shot_rim()
            if self.ball.mode == BallMode.SHOT:
                self._check_backboard()
            if self.ball.mode == BallMode.SHOT:
                self._check_shot_timeout()
        elif self.ball.mode == BallMode.DUNK:
            self._check_dunk()
            if self.ball.mode == BallMode.DUNK and self.ball.made and self.ball.age > .86:
                self._finish_scoring_possession()
        elif self.ball.mode == BallMode.LOOSE:
            self._check_catches()
            self._check_dead_ball()
        elif self.ball.mode == BallMode.MADE:
            if self.ball.position.y > HOOP_Y+94:
                self._finish_scoring_possession()

    def _try_block_shot(self) -> None:
        if self.ball.age > .15 or self.ball.shooter is None:
            return
        shooter = self.ball.shooter
        defender = self.players[1-shooter]
        origin = self.players[shooter].position
        close = defender.position.distance_to(origin) < 88
        in_air = defender.jump_height > 40
        if close and in_air:
            point = self.ball.position.copy()
            attack = self.attacks[shooter]
            self.ball.become_loose(point, Vec2(-attack*235, -240), shooter, .08)
            defender.stats.blocks += 1
            self.audio.play("block", .9)
            self.effects.block(point)
            self.camera.add_shake(2.1, .1)
            self.set_broadcast("BLOCKED! FIGHT FOR THE REBOUND", 1.0)

    def _check_shot_rim(self) -> None:
        ball = self.ball
        if ball.shooter is None:
            return
        hoop_x = self.hoop_for(ball.shooter)
        previous = ball.previous_position
        current = ball.position
        crossed_x = ((previous.x-hoop_x)*(current.x-hoop_x) <= 0)
        near_x = abs(current.x-hoop_x) <= 42
        descending = ball.velocity.y > 0
        near_rim_y = HOOP_Y-31 <= current.y <= HOOP_Y+20
        if not near_x or not descending or not near_rim_y:
            return
        quality_good = ball.quality >= .62
        if quality_good and (crossed_x or abs(current.x-hoop_x) < 26):
            self._record_basket(ball.shooter, ball.value, ball.is_three, False)
            ball.mark_made(ball.shooter)
            side = 1 if hoop_x > VIRTUAL_WIDTH/2 else 0
            self.arena.kick_net(side, 1.0)
            self.arena.excite_crowd(hoop_x, .9)
            self.effects.swish(Vec2(hoop_x, HOOP_Y+20), TEAMS[ball.shooter].jersey)
            self.audio.play("swish", .85)
            self.camera.add_shake(1.6, .13)
            return
        rim_point = Vec2(hoop_x, HOOP_Y)
        if current.distance_to(rim_point) < 49:
            normal = Vec2(-1 if current.x > hoop_x else 1, -.18).normalized()
            ball.hit_rim(normal)
            self.effects.rim_hit(current)
            self.audio.play("rim", .55)
            self.set_broadcast("OFF THE RIM! REBOUND", .9)
            if self.ball.shooter is not None:
                pass

    def _check_backboard(self) -> None:
        ball = self.ball
        if ball.shooter is None:
            return
        hoop_x = self.hoop_for(ball.shooter)
        board_x = hoop_x+(-BACKBOARD_OFFSET if hoop_x < VIRTUAL_WIDTH/2
                          else BACKBOARD_OFFSET)
        if abs(ball.position.x-board_x) < BALL_RADIUS+5 and 306 < ball.position.y < 401:
            normal = Vec2(-1 if ball.position.x > board_x else 1, 0)
            ball.hit_backboard(normal)
            self.effects.rim_hit(ball.position)
            self.audio.play("rim", .48)

    def _check_shot_timeout(self) -> None:
        if self.ball.mode != BallMode.SHOT:
            return
        if self.ball.age > self.ball.flight_time+1.05 or self.ball.position.y > COURT_FLOOR+40:
            point = self.ball.position.copy()
            direction = self.ball.velocity.normalized()
            velocity = Vec2(direction.x*125, -85)
            self.ball.become_loose(point, velocity, self.ball.last_touch)
            self.set_broadcast("LOOSE BALL! GO GET IT", .8)

    def _check_dunk(self) -> None:
        ball = self.ball
        if ball.shooter is None or ball.age < .38:
            return
        shooter = ball.shooter
        defender = self.players[1-shooter]
        player = self.players[shooter]
        blocked = (defender.jump_height > 54
                   and defender.position.distance_to(player.position) < 98)
        if blocked:
            ball.become_loose(ball.position, Vec2(-self.attacks[shooter]*210, -180),
                              shooter, .08)
            player.finish_dunk()
            defender.stats.blocks += 1
            self.effects.block(ball.position)
            self.audio.play("block", .95)
            self.set_broadcast("DUNK BLOCKED!", 1.0)
            return
        if not ball.made:
            ball.made = True
            self._record_basket(shooter, 2, False, True)
            self.arena.kick_net(1 if self.hoop_for(shooter) > VIRTUAL_WIDTH/2 else 0, 1.1)
            self.arena.excite_crowd(self.hoop_for(shooter), 1.0)
            self.effects.dunk(Vec2(self.hoop_for(shooter), HOOP_Y+12), TEAMS[shooter].jersey)
            self.audio.play("dunk", 1.0)
            self.camera.add_shake(5.0, .25)
            player.finish_dunk()

    def _check_catches(self) -> None:
        if self.ball.mode != BallMode.LOOSE or self.ball.catch_lock > 0:
            return
        candidates = sorted(range(2),
                            key=lambda team: self.players[team].position.distance_to(self.ball.position))
        for team in candidates:
            player = self.players[team]
            player.begin_catch(self.ball.position)
            attack = self.attacks[team]
            reach = player.catch_reach_distance(attack, self.ball.position,
                                                player.animation_time)
            if reach <= BALL_RADIUS+8:
                self._secure_rebound(team)
                return

    def _secure_rebound(self, team: int) -> None:
        player = self.players[team]
        last_touch = self.ball.last_touch
        player.confirm_catch()
        player.stats.rebounds += 1
        if last_touch is not None and last_touch != team:
            self.players[last_touch].stats.turnovers += 1
        self.ball.reset(team)
        self.ball.attach_to_player(player, self.attacks[team], player.animation_time)
        self.shot_clock = SHOT_CLOCK_SECONDS
        self.effects.burst(player.center, player.team.accent, 10, (25, 130), (.2, .46), "spark")
        self.audio.play("dribble", .55)
        self.set_broadcast(f"{player.team.short_name} SECURES THE REBOUND", .85)

    def _check_dead_ball(self) -> None:
        if self.ball.mode != BallMode.LOOSE:
            return
        if self.ball.is_out_of_play(COURT_LEFT-40, COURT_RIGHT+40, -80, COURT_FLOOR):
            self._award_out_of_bounds()
        elif self.ball.age > 5.5:
            nearest = min(range(2),
                          key=lambda team: self.players[team].position.distance_to(self.ball.position))
            self._secure_rebound(nearest)

    def _award_out_of_bounds(self) -> None:
        last_touch = self.ball.last_touch
        winner = 1-last_touch if last_touch is not None else 0
        self.ball.reset(winner)
        self.ball.attach_to_player(self.players[winner], self.attacks[winner], 0.0)
        self.shot_clock = SHOT_CLOCK_SECONDS
        self.set_broadcast(f"OUT OF BOUNDS  •  {TEAMS[winner].short_name} BALL", .9)

    def _record_basket(self, team: int, points: int,
                       is_three: bool, is_dunk: bool) -> None:
        self.scores[team] += points
        player = self.players[team]
        player.stats.points += points
        player.stats.fgm += 1
        if is_three:
            player.stats.three_made += 1
        if is_dunk:
            player.stats.dunks += 1
        if self.streak_team == team:
            self.streak_count += 1
        else:
            self.streak_team = team
            self.streak_count = 1
        if self.streak_count >= 2:
            self.set_broadcast(f"{TEAMS[team].short_name} HEATER x{self.streak_count}!", 1.2)
        else:
            label = "SLAM DUNK!" if is_dunk else f"{points} POINTS!"
            self.set_broadcast(f"{TEAMS[team].short_name}  •  {label}", 1.1)
        self.shot_clock = SHOT_CLOCK_SECONDS

    def _finish_scoring_possession(self) -> None:
        scorer = self.ball.last_touch
        if scorer is None:
            return
        next_owner = 1-scorer
        self.ball.reset(next_owner)
        self.ball.attach_to_player(self.players[next_owner], self.attacks[next_owner], 0.0)
        self.shot_clock = SHOT_CLOCK_SECONDS

    def _resolve_player_collision(self) -> None:
        first, second = self.players
        offset = second.position-first.position
        distance = offset.length
        minimum = PLAYER_RADIUS*2.0
        if distance <= 1e-4 or distance >= minimum:
            return
        direction = offset/distance
        separation = (minimum-distance)*.5
        first.position.x -= direction.x*separation
        second.position.x += direction.x*separation
        impact = max(0.0, minimum-distance)*4.0
        first.velocity.x -= direction.x*impact
        second.velocity.x += direction.x*impact

    def _update_shot_clock(self, dt: float) -> None:
        if self.phase != GamePhase.LIVE or self.ball.mode not in (BallMode.HELD,
                                                                  BallMode.LOOSE):
            return
        self.shot_clock = max(0.0, self.shot_clock-dt)
        if self.shot_clock > 0:
            return
        old_owner = self.ball.owner
        if old_owner is None:
            old_owner = self.ball.last_touch
        if old_owner is None:
            old_owner = 0
        new_owner = 1-old_owner
        self.players[old_owner].stats.turnovers += 1
        self.ball.reset(new_owner)
        self.ball.attach_to_player(self.players[new_owner], self.attacks[new_owner], 0.0)
        self.shot_clock = SHOT_CLOCK_SECONDS
        self.set_broadcast("SHOT CLOCK VIOLATION!", 1.0)
        self.audio.play("whistle", .7)

    def _update_out_of_bounds(self) -> None:
        if self.ball.owner is not None or self.ball.mode != BallMode.HELD:
            return
        self.ball.position.x = clamp(self.ball.position.x,
                                     COURT_LEFT, COURT_RIGHT)

    def _update_drift_effects(self, dt: float) -> None:
        for player in self.players:
            if player.is_sprinting and player.run_blend > .65 and self.random.random() < dt*16:
                self.effects.foot_dust(player.floor_point, player.team.jersey_shadow)

    def _camera_target(self) -> Vec2:
        if self.ball.mode == BallMode.HELD and self.ball.owner is not None:
            target = self.players[self.ball.owner].center
        else:
            target = self.ball.position.copy()
        center = Vec2(VIRTUAL_WIDTH/2, VIRTUAL_HEIGHT/2)
        offset = target-center
        return center+offset*.10

    def set_broadcast(self, message: str, duration: float = 1.0) -> None:
        self.broadcast = message
        self.broadcast_timer = duration

    def hoop_for(self, team: int) -> float:
        return HOOP_RIGHT_X if self.attacks[team] > 0 else HOOP_LEFT_X

    def distance_to_basket(self, team: int) -> float:
        return abs(self.hoop_for(team)-self.players[team].position.x)

    def period_label(self) -> str:
        return f"OVERTIME {self.overtime}" if self.overtime else f"QUARTER {self.quarter}"

    def clock_text(self) -> str:
        return format_clock(self.game_clock)

    def shot_clock_text(self) -> str:
        return f"{max(0.0, self.shot_clock):04.1f}"

    def winner_text(self) -> str:
        if self.scores[0] == self.scores[1]:
            return "TIE GAME"
        return f"{TEAMS[0 if self.scores[0] > self.scores[1] else 1].name} WINS!"

    def _render(self, alpha: float) -> None:
        self.world.fill((7, 11, 21))
        self.arena.draw(self.world)
        loose_target = self.ball.position if self.ball.mode == BallMode.LOOSE else None
        order = sorted(range(2), key=lambda team: self.players[team].position.x)
        for team in order:
            self.player_renderer.draw(self.world, self.players[team], self.attacks[team],
                                      self.players[team].animation_time, alpha,
                                      loose_target, self.ball.owner == team)
        if self.ball.mode != BallMode.HELD:
            self.ball_renderer.draw(self.world, self.ball, alpha)
        else:
            owner = self.ball.owner
            if owner is not None:
                self.ball_renderer.draw(self.world, self.ball, alpha)
        self.effects.draw(self.world)
        self.hud.draw_scoreboard(self.world, self)
        for team in range(2):
            window = self.shot_window(team)
            self.hud.draw_player_hud(self.world, team, self.players[team], window,
                                     self.charge[team] if self.charge_active[team] else None,
                                     self.steal_cooldown[team],
                                     self.timeouts[team], self.router.player_key_legend(team))
        self.hud.draw_instructions(self.world, self.muted)
        self.hud.draw_event(self.world, self.broadcast, self.broadcast_timer)
        if self.phase == GamePhase.PAUSED:
            self.hud.draw_pause(self.world)
        if self.show_help:
            self.hud.draw_help(self.world)
        if self.phase == GamePhase.FINAL:
            self.hud.draw_final_box(self.world, self)

    def _present(self) -> None:
        width, height = self.window.get_size()
        scale = min(width/VIRTUAL_WIDTH, height/VIRTUAL_HEIGHT)
        scaled_size = (max(1, int(VIRTUAL_WIDTH*scale)),
                       max(1, int(VIRTUAL_HEIGHT*scale)))
        if scaled_size == (VIRTUAL_WIDTH, VIRTUAL_HEIGHT):
            scaled = self.world
        else:
            if self.scaled_size != scaled_size or self.scaled_surface is None:
                self.scaled_surface = pygame.Surface(scaled_size).convert()
                self.scaled_size = scaled_size
            scaled = pygame.transform.smoothscale(
                self.world, scaled_size, self.scaled_surface
            )
        self.window.fill(BLACK)
        x = (width-scaled_size[0])//2
        y = (height-scaled_size[1])//2
        offset = self.camera.screen_offset()
        self.window.blit(scaled, (x+int(offset.x), y+int(offset.y)))
        pygame.display.flip()

