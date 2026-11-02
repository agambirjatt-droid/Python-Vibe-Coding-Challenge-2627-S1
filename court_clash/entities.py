"""Basketball player and ball models with fixed-step-friendly physics."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random

from .controls import PlayerInput
from .settings import (
    BALL_GRAVITY,
    BALL_RADIUS,
    COURT_FLOOR,
    COURT_LEFT,
    COURT_RIGHT,
    DUNK_DISTANCE,
    PLAYER_ACCELERATION,
    PLAYER_DRAG,
    PLAYER_GRAVITY,
    PLAYER_JUMP_SPEED,
    PLAYER_MAX_SPEED,
    PLAYER_RADIUS,
    PLAYER_REACH,
    BallMode,
    TeamConfig,
    clamp,
    lerp,
    smoothstep,
)
from .vector import Vec2, damp


@dataclass(slots=True)
class PlayerStats:
    """Per-match statistics collected by the controller."""

    points: int = 0
    fgm: int = 0
    fga: int = 0
    three_made: int = 0
    three_attempted: int = 0
    dunks: int = 0
    steals: int = 0
    blocks: int = 0
    rebounds: int = 0
    turnovers: int = 0
    perfect_releases: int = 0
    timeouts: int = 0


@dataclass(slots=True)
class PlayerPose:
    """World-space skeleton joints for drawing a basketball player."""

    head: Vec2 = field(default_factory=Vec2)
    neck: Vec2 = field(default_factory=Vec2)
    chest: Vec2 = field(default_factory=Vec2)
    pelvis: Vec2 = field(default_factory=Vec2)
    left_shoulder: Vec2 = field(default_factory=Vec2)
    right_shoulder: Vec2 = field(default_factory=Vec2)
    left_elbow: Vec2 = field(default_factory=Vec2)
    right_elbow: Vec2 = field(default_factory=Vec2)
    left_hand: Vec2 = field(default_factory=Vec2)
    right_hand: Vec2 = field(default_factory=Vec2)
    left_hip: Vec2 = field(default_factory=Vec2)
    right_hip: Vec2 = field(default_factory=Vec2)
    left_knee: Vec2 = field(default_factory=Vec2)
    right_knee: Vec2 = field(default_factory=Vec2)
    left_foot: Vec2 = field(default_factory=Vec2)
    right_foot: Vec2 = field(default_factory=Vec2)

    def hands(self) -> tuple[Vec2, Vec2]:
        return self.left_hand, self.right_hand

    def feet(self) -> tuple[Vec2, Vec2]:
        return self.left_foot, self.right_foot


class Player:
    """A smooth arcade player with stamina, momentum, and procedural limbs."""

    def __init__(self, team_id: int, team: TeamConfig, spawn_x: float) -> None:
        self.team_id = team_id
        self.team = team
        self.position = Vec2(spawn_x, COURT_FLOOR)
        self.previous_position = self.position.copy()
        self.velocity = Vec2()
        self.jump_height = 0.0
        self.jump_velocity = 0.0
        self.facing = float(team.initial_attack)
        self.stamina = 100.0
        self.animation_time = random.random()*math.tau
        self.run_blend = 0.0
        self.jump_blend = 0.0
        self.cross_blend = 0.0
        self.catch_blend = 0.0
        self.shoot_blend = 0.0
        self.dunk_blend = 0.0
        self.steal_cooldown = 0.0
        self.crossover_cooldown = 0.0
        self.flash_timer = 0.0
        self.last_move = 0.0
        self.is_sprinting = False
        self.is_catching = False
        self.is_shooting = False
        self.is_defending = False
        self.is_dunking = False
        self.ball_owner = False
        self.stun_timer = 0.0
        self.hand_target = Vec2()
        self.stats = PlayerStats()

    @property
    def grounded(self) -> bool:
        return self.jump_height <= 0.1 and self.jump_velocity <= 0.0

    @property
    def speed_fraction(self) -> float:
        return min(1.0, abs(self.velocity.x)/PLAYER_MAX_SPEED)

    @property
    def energy_fraction(self) -> float:
        return clamp(self.stamina/100.0, 0.0, 1.0)

    @property
    def center(self) -> Vec2:
        return Vec2(self.position.x, self.position.y-self.jump_height-72)

    @property
    def floor_point(self) -> Vec2:
        return Vec2(self.position.x, self.position.y)

    def reset(self, spawn_x: float) -> None:
        self.position = Vec2(spawn_x, COURT_FLOOR)
        self.previous_position = self.position.copy()
        self.velocity = Vec2()
        self.jump_height = 0.0
        self.jump_velocity = 0.0
        self.stamina = 100.0
        self.animation_time = 0.0
        self.run_blend = 0.0
        self.jump_blend = 0.0
        self.cross_blend = 0.0
        self.catch_blend = 0.0
        self.shoot_blend = 0.0
        self.dunk_blend = 0.0
        self.steal_cooldown = 0.0
        self.crossover_cooldown = 0.0
        self.flash_timer = 0.0
        self.is_sprinting = False
        self.is_catching = False
        self.is_shooting = False
        self.is_defending = False
        self.is_dunking = False
        self.ball_owner = False
        self.stun_timer = 0.0
        self.hand_target = Vec2()
        self.stats = PlayerStats()

    def update(self, controls: PlayerInput, dt: float, attack: int,
               has_ball: bool, defender_near: bool) -> None:
        """Advance movement, jump, stamina, and animation state."""
        self.previous_position = self.position.copy()
        self.steal_cooldown = max(0.0, self.steal_cooldown-dt)
        self.crossover_cooldown = max(0.0, self.crossover_cooldown-dt)
        self.flash_timer = max(0.0, self.flash_timer-dt)
        self.cross_blend = max(0.0, self.cross_blend-dt*3.4)
        self.catch_blend = max(0.0, self.catch_blend-dt*3.8)
        self.shoot_blend = max(0.0, self.shoot_blend-dt*2.4)
        self.dunk_blend = max(0.0, self.dunk_blend-dt*2.0)
        self.stun_timer = max(0.0, self.stun_timer-dt)
        self.is_defending = not has_ball
        self.ball_owner = has_ball
        self.is_catching = False
        self.is_sprinting = controls.sprint and controls.moving and self.stamina > 2.0
        self._update_horizontal(controls, dt)
        self._update_jump(controls, dt)
        self._update_stamina(controls, dt)
        self._update_animation(controls, dt)
        if controls.jump_pressed and self.grounded:
            self.jump()
        self.facing = float(attack)

    def _update_horizontal(self, controls: PlayerInput, dt: float) -> None:
        if self.stun_timer > 0:
            self.velocity.x = damp(self.velocity.x, 0.0, 7.0, dt)
            return
        input_axis = clamp(controls.move_x, -1.0, 1.0)
        sprint_multiplier = 1.42 if self.is_sprinting else 1.0
        desired_speed = input_axis*PLAYER_MAX_SPEED*sprint_multiplier
        if abs(input_axis) > 0.01:
            self.velocity.x = damp(self.velocity.x, desired_speed, 11.0, dt)
        else:
            self.velocity.x = damp(self.velocity.x, 0.0, PLAYER_DRAG, dt)
        if abs(self.velocity.x) < 2.0:
            self.velocity.x = 0.0
        self.position.x += self.velocity.x*dt
        self.position.x = clamp(self.position.x, COURT_LEFT+30, COURT_RIGHT-30)
        if input_axis:
            self.last_move = input_axis

    def _update_jump(self, controls: PlayerInput, dt: float) -> None:
        if self.jump_height > 0.0 or self.jump_velocity > 0.0:
            self.jump_height += self.jump_velocity*dt
            self.jump_velocity -= PLAYER_GRAVITY*dt
            if self.jump_height <= 0.0:
                self.jump_height = 0.0
                self.jump_velocity = 0.0
        if controls.jump_pressed and self.grounded:
            self.jump()
        target = 1.0 if self.jump_height > 0.0 else 0.0
        self.jump_blend = damp(self.jump_blend, target, 14.0, dt)

    def _update_stamina(self, controls: PlayerInput, dt: float) -> None:
        if self.is_sprinting:
            self.stamina = max(0.0, self.stamina-26.0*dt)
        else:
            recovery = 24.0 if self.grounded else 9.0
            if self.ball_owner:
                recovery *= .92
            self.stamina = min(100.0, self.stamina+recovery*dt)

    def _update_animation(self, controls: PlayerInput, dt: float) -> None:
        target_run = min(1.0, abs(self.velocity.x)/PLAYER_MAX_SPEED)
        self.run_blend = damp(self.run_blend, target_run, 10.0, dt)
        self.animation_time += dt*(3.0+10.0*self.run_blend)
        if self.is_shooting:
            self.shoot_blend = min(1.0, self.shoot_blend+dt*4.5)
        if self.is_dunking:
            self.dunk_blend = min(1.0, self.dunk_blend+dt*4.0)

    def jump(self, strength: float = 1.0) -> None:
        if not self.grounded:
            return
        tired_scale = .83 + .17*self.energy_fraction
        self.jump_velocity = PLAYER_JUMP_SPEED*strength*tired_scale
        self.flash_timer = .12

    def begin_crossover(self) -> bool:
        if self.crossover_cooldown > 0.0 or not self.grounded:
            return False
        self.cross_blend = 1.0
        self.crossover_cooldown = .55
        return True

    def begin_catch(self, target: Vec2) -> None:
        self.is_catching = True
        self.hand_target = target.copy()
        self.catch_blend = 1.0

    def confirm_catch(self) -> None:
        self.is_catching = False
        self.catch_blend = 1.0

    def begin_shot(self) -> None:
        self.is_shooting = True
        self.shoot_blend = .15

    def release_shot(self) -> None:
        self.is_shooting = False
        self.shoot_blend = 1.0

    def begin_dunk(self) -> None:
        self.is_dunking = True
        self.dunk_blend = .12
        self.jump(max(1.18, self.energy_fraction))

    def finish_dunk(self) -> None:
        self.is_dunking = False

    def get_pose(self, attack: int, time: float, ball_position: Vec2 | None = None) -> PlayerPose:
        """Build a full skeleton pose with stride, lean, and reaching hands."""
        pose = PlayerPose()
        run = self.run_blend
        wave = math.sin(self.animation_time)*run*18.0
        bounce = abs(math.sin(self.animation_time*2.0))*run*4.0
        base_y = self.position.y-self.jump_height-bounce
        lean = clamp(self.velocity.x/PLAYER_MAX_SPEED, -1.0, 1.0)*8.0
        center_x = self.position.x+lean
        pose.head = Vec2(center_x, base_y-132)
        pose.neck = Vec2(center_x, base_y-96)
        pose.chest = Vec2(center_x, base_y-78)
        pose.pelvis = Vec2(self.position.x, base_y-31)
        pose.left_shoulder = Vec2(center_x-19, base_y-84)
        pose.right_shoulder = Vec2(center_x+19, base_y-84)
        pose.left_hip = Vec2(self.position.x-12, base_y-42)
        pose.right_hip = Vec2(self.position.x+12, base_y-42)
        self._pose_legs(pose, base_y, wave, time)
        if ball_position is not None and (self.is_catching or self.catch_blend > 0):
            self._pose_reach(pose, ball_position, attack)
        elif self.is_dunking or self.dunk_blend > 0:
            self._pose_dunk(pose, base_y, attack)
        elif self.is_shooting or self.shoot_blend > 0:
            self._pose_shot(pose, base_y, attack)
        elif self.cross_blend > 0:
            self._pose_cross(pose, base_y, attack)
        elif not self.ball_owner:
            self._pose_defense(pose, base_y)
        else:
            self._pose_run_arms(pose, base_y, wave)
        return pose

    def _pose_legs(self, pose: PlayerPose, base_y: float, wave: float, time: float) -> None:
        jump_factor = min(1.0, self.jump_height/90.0)
        if jump_factor > .2:
            kick = math.sin(time*7.0)*13.0
            pose.left_knee = Vec2(self.position.x-12-kick, base_y-34)
            pose.right_knee = Vec2(self.position.x+12+kick, base_y-34)
            pose.left_foot = Vec2(self.position.x-28-kick, base_y-7)
            pose.right_foot = Vec2(self.position.x+28+kick, base_y-7)
        else:
            pose.left_knee = Vec2(self.position.x-13+wave*.42, base_y-30)
            pose.right_knee = Vec2(self.position.x+13-wave*.42, base_y-30)
            pose.left_foot = Vec2(self.position.x-26+wave, base_y)
            pose.right_foot = Vec2(self.position.x+26-wave, base_y)

    def _pose_run_arms(self, pose: PlayerPose, base_y: float, wave: float) -> None:
        pose.left_elbow = Vec2(pose.left_shoulder.x-8-wave*.4, base_y-57)
        pose.right_elbow = Vec2(pose.right_shoulder.x+8+wave*.4, base_y-58)
        pose.left_hand = Vec2(pose.left_elbow.x-10-wave*.55, base_y-47)
        pose.right_hand = Vec2(pose.right_elbow.x+10+wave*.55, base_y-47)

    def _pose_defense(self, pose: PlayerPose, base_y: float) -> None:
        raise_height = 24.0 + max(0.0, self.jump_height*.18)
        pose.left_elbow = Vec2(pose.left_shoulder.x-18, base_y-111-raise_height*.3)
        pose.right_elbow = Vec2(pose.right_shoulder.x+18, base_y-111-raise_height*.3)
        pose.left_hand = Vec2(pose.left_shoulder.x-24, base_y-143-raise_height)
        pose.right_hand = Vec2(pose.right_shoulder.x+24, base_y-143-raise_height)

    def _pose_shot(self, pose: PlayerPose, base_y: float, attack: int) -> None:
        pose.right_elbow = Vec2(self.position.x+attack*23, base_y-111)
        pose.right_hand = Vec2(self.position.x+attack*35, base_y-145)
        pose.left_elbow = Vec2(self.position.x-attack*24, base_y-57)
        pose.left_hand = Vec2(self.position.x-attack*11, base_y-68)

    def _pose_dunk(self, pose: PlayerPose, base_y: float, attack: int) -> None:
        pose.right_elbow = Vec2(self.position.x+attack*34, base_y-117)
        pose.right_hand = Vec2(self.position.x+attack*48, base_y-166)
        pose.left_elbow = Vec2(self.position.x-attack*30, base_y-112)
        pose.left_hand = Vec2(self.position.x-attack*47, base_y-132)

    def _pose_cross(self, pose: PlayerPose, base_y: float, attack: int) -> None:
        phase = self.cross_blend
        sweep = math.sin((1.0-phase)*math.pi)*34.0
        pose.left_elbow = Vec2(self.position.x-attack*8, base_y-65)
        pose.right_elbow = Vec2(self.position.x+attack*8, base_y-64)
        pose.left_hand = Vec2(self.position.x+attack*sweep, base_y-48)
        pose.right_hand = Vec2(self.position.x-attack*sweep, base_y-48)

    def _pose_reach(self, pose: PlayerPose, target: Vec2, attack: int) -> None:
        shoulder = pose.right_shoulder if (target.x-self.position.x)*attack >= 0 else pose.left_shoulder
        other = pose.left_shoulder if shoulder is pose.right_shoulder else pose.right_shoulder
        vector = target-shoulder
        reach = vector.clamp_length(PLAYER_REACH)
        hand = shoulder+reach
        elbow = shoulder+reach*.52+Vec2(0, 8)
        if shoulder is pose.right_shoulder:
            pose.right_elbow, pose.right_hand = elbow, hand
        else:
            pose.left_elbow, pose.left_hand = elbow, hand
        opposite = (target-other).clamp_length(72)
        support_hand = other+opposite
        support_elbow = other+(support_hand-other)*.55+Vec2(0, 7)
        if shoulder is pose.right_shoulder:
            pose.left_elbow, pose.left_hand = support_elbow, support_hand
        else:
            pose.right_elbow, pose.right_hand = support_elbow, support_hand

    def hands(self, attack: int, time: float, target: Vec2 | None = None) -> tuple[Vec2, Vec2]:
        pose = self.get_pose(attack, time, target)
        return pose.hands()

    def catch_reach_distance(self, attack: int, target: Vec2, time: float) -> float:
        hand_a, hand_b = self.hands(attack, time, target)
        return min(hand_a.distance_to(target), hand_b.distance_to(target))

    def can_reach_ball(self, attack: int, target: Vec2, time: float,
                       radius: float) -> bool:
        return self.catch_reach_distance(attack, target, time) <= radius

    def interpolated_position(self, alpha: float) -> Vec2:
        return self.previous_position.lerp_to(self.position, alpha)

    def recover_after_bump(self, impulse: Vec2) -> None:
        self.velocity += impulse
        self.flash_timer = .18

    def apply_stun(self, seconds: float) -> None:
        self.stun_timer = max(self.stun_timer, seconds)

    def nudge_toward(self, point: Vec2, amount: float) -> None:
        direction = (point-self.center).normalized()
        self.velocity += direction*amount


class Ball:
    """Basketball flight, bounce, rim contact, and catchable loose-ball state."""

    def __init__(self) -> None:
        self.position = Vec2()
        self.previous_position = Vec2()
        self.start_position = Vec2()
        self.velocity = Vec2()
        self.mode = BallMode.HELD
        self.owner: int | None = 0
        self.last_touch: int | None = 0
        self.shooter: int | None = None
        self.target_x = 0.0
        self.value = 2
        self.flight_time = 0.0
        self.age = 0.0
        self.quality = 0.0
        self.is_three = False
        self.made = False
        self.rim_touched = False
        self.bounces = 0
        self.rotation = 0.0
        self.spin = 0.0
        self.trail: list[Vec2] = []
        self.catch_lock = 0.0
        self.dunk_target = Vec2()

    @property
    def airborne(self) -> bool:
        return self.mode in (BallMode.SHOT, BallMode.DUNK, BallMode.MADE)

    @property
    def loose(self) -> bool:
        return self.mode == BallMode.LOOSE

    def reset(self, owner: int = 0) -> None:
        self.position = Vec2()
        self.previous_position = Vec2()
        self.start_position = Vec2()
        self.velocity = Vec2()
        self.mode = BallMode.HELD
        self.owner = owner
        self.last_touch = owner
        self.shooter = None
        self.age = 0.0
        self.quality = 0.0
        self.made = False
        self.rim_touched = False
        self.bounces = 0
        self.rotation = 0.0
        self.spin = 0.0
        self.trail.clear()
        self.catch_lock = .1

    def attach_to_player(self, player: Player, attack: int,
                         dribble_phase: float, shooting: bool = False) -> None:
        self.owner = player.team_id
        self.last_touch = player.team_id
        self.mode = BallMode.HELD
        self.catch_lock = 0.0
        if shooting:
            pose = player.get_pose(attack, dribble_phase)
            self.position = pose.right_hand + Vec2(attack*7, -4)
        elif player.catch_blend > 0.1:
            self.position = Vec2(player.position.x+attack*35,
                                 player.position.y-player.jump_height-86)
        else:
            bounce = abs(math.sin(dribble_phase*2.0))*26.0
            cross = math.sin((1.0-player.cross_blend)*math.pi)*30.0
            self.position = Vec2(player.position.x+attack*(27+cross),
                                 player.position.y-player.jump_height-22-bounce)
        self.previous_position = self.position.copy()

    def release_shot(self, player: Player, attack: int, hoop_x: float,
                     release_quality: float, points: int, accuracy: float) -> None:
        self.mode = BallMode.SHOT
        self.owner = None
        self.shooter = player.team_id
        self.last_touch = player.team_id
        self.target_x = hoop_x
        self.value = points
        self.is_three = points == 3
        self.quality = accuracy
        self.age = 0.0
        self.made = False
        self.rim_touched = False
        self.bounces = 0
        self.trail.clear()
        self.position = Vec2(player.position.x+attack*22,
                             player.position.y-player.jump_height-116)
        self.previous_position = self.position.copy()
        self.start_position = self.position.copy()
        distance = abs(hoop_x-self.position.x)
        self.flight_time = clamp(distance/640.0, .63, 1.58)
        target_y = 337.0 + clamp((.88-accuracy)*24.0, -2.0, 14.0)
        offset = (1.0-accuracy)*112.0
        if accuracy < .5:
            offset *= -1.0
        self.target_x = hoop_x + offset
        self.velocity = Vec2((self.target_x-self.position.x)/self.flight_time,
                             -(self.position.y-target_y + .5*BALL_GRAVITY*self.flight_time**2)/self.flight_time)
        self.spin = attack*12.0 + release_quality*7.0

    def begin_dunk(self, player: Player, attack: int, hoop_x: float) -> None:
        self.mode = BallMode.DUNK
        self.owner = None
        self.shooter = player.team_id
        self.last_touch = player.team_id
        self.target_x = hoop_x
        self.dunk_target = Vec2(hoop_x, 365.0)
        self.position = Vec2(player.position.x+attack*32,
                             player.position.y-player.jump_height-94)
        self.previous_position = self.position.copy()
        self.start_position = self.position.copy()
        self.velocity = Vec2()
        self.age = 0.0
        self.made = False
        self.trail.clear()

    def become_loose(self, position: Vec2, velocity: Vec2,
                     last_touch: int | None, minimum_lock: float = .12) -> None:
        self.mode = BallMode.LOOSE
        self.owner = None
        self.last_touch = last_touch
        self.position = position.copy()
        self.previous_position = position.copy()
        self.start_position = position.copy()
        self.velocity = velocity.copy()
        self.age = 0.0
        self.catch_lock = minimum_lock
        self.made = False

    def mark_made(self, attacking_team: int) -> None:
        self.mode = BallMode.MADE
        self.owner = None
        self.made = True
        self.last_touch = attacking_team
        self.velocity.x = 0.0
        self.velocity.y = 165.0
        self.age = 0.0

    def update(self, dt: float, hoop_y: float, floor_y: float) -> None:
        self.previous_position = self.position.copy()
        self.age += dt
        self.catch_lock = max(0.0, self.catch_lock-dt)
        if self.mode in (BallMode.SHOT, BallMode.LOOSE, BallMode.MADE):
            self._integrate_arc(dt)
            self._resolve_floor(floor_y)
            self._record_trail()
        elif self.mode == BallMode.DUNK:
            self._update_dunk_path(hoop_y)

    def _integrate_arc(self, dt: float) -> None:
        self.position += self.velocity*dt
        self.velocity.y += BALL_GRAVITY*dt
        self.rotation += self.spin*dt
        self.spin *= math.exp(-.5*dt)

    def _resolve_floor(self, floor_y: float) -> None:
        if self.mode != BallMode.LOOSE:
            return
        floor_contact = floor_y-BALL_RADIUS
        if self.position.y < floor_contact:
            return
        self.position.y = floor_contact
        if abs(self.velocity.y) > 82.0:
            self.velocity.y = -abs(self.velocity.y)*.56
            self.velocity.x *= .78
            self.bounces += 1
        else:
            self.velocity.y = 0.0
            self.velocity.x *= .86
        if abs(self.velocity.x) < 9.0:
            self.velocity.x = 0.0

    def _update_dunk_path(self, hoop_y: float) -> None:
        progress = clamp(self.age/.39, 0.0, 1.0)
        eased = smoothstep(progress)
        self.position.x = self.start_position.x + (self.target_x-self.start_position.x)*eased
        if progress < 1.0:
            arc = math.sin(progress*math.pi)*46.0
            self.position.y = lerp(self.start_position.y, hoop_y, eased)-arc
        else:
            self.position.y = hoop_y + max(0.0, self.age-.39)*300.0

    def _record_trail(self) -> None:
        if self.mode in (BallMode.SHOT, BallMode.MADE) and self.age > .05:
            self.trail.append(self.position.copy())
            if len(self.trail) > 11:
                del self.trail[0]
        elif self.mode == BallMode.LOOSE:
            if self.trail:
                self.trail.clear()

    def interpolated_position(self, alpha: float) -> Vec2:
        return self.previous_position.lerp_to(self.position, alpha)

    def hit_rim(self, normal: Vec2, restitution: float = .72) -> None:
        self.velocity = self.velocity.reflect(normal)*restitution
        self.rim_touched = True
        self.mode = BallMode.LOOSE
        self.owner = None
        self.age = 0.0
        self.bounces += 1

    def hit_backboard(self, normal: Vec2) -> None:
        self.velocity = self.velocity.reflect(normal)*.68
        self.mode = BallMode.LOOSE
        self.owner = None
        self.age = 0.0

    def is_out_of_play(self, left: float, right: float, top: float, floor: float) -> bool:
        return (self.position.x < left or self.position.x > right
                or self.position.y < top-140 or self.position.y > floor+100)

    def speed(self) -> float:
        return self.velocity.length

    def distance_to(self, point: Vec2) -> float:
        return self.position.distance_to(point)


def dt_soft(progress: float) -> float:
    """Ease a dunk's vertical path without a sharp start or stop."""
    return smoothstep(clamp(progress, 0.0, 1.0))

