"""Small, dependency-free vector and easing helpers for the simulation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .settings import clamp, lerp


@dataclass(slots=True)
class Vec2:
    """Two-dimensional floating-point vector with familiar arithmetic."""

    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_pair(cls, pair: tuple[float, float]) -> "Vec2":
        return cls(float(pair[0]), float(pair[1]))

    @classmethod
    def polar(cls, angle: float, length: float = 1.0) -> "Vec2":
        return cls(math.cos(angle)*length, math.sin(angle)*length)

    def copy(self) -> "Vec2":
        return Vec2(self.x, self.y)

    def tuple(self) -> tuple[float, float]:
        return self.x, self.y

    def rounded(self) -> tuple[int, int]:
        return round(self.x), round(self.y)

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x+other.x, self.y+other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x-other.x, self.y-other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x*scalar, self.y*scalar)

    def __rmul__(self, scalar: float) -> "Vec2":
        return self*scalar

    def __truediv__(self, scalar: float) -> "Vec2":
        if abs(scalar) < 1e-12:
            return Vec2()
        return Vec2(self.x/scalar, self.y/scalar)

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def __iadd__(self, other: "Vec2") -> "Vec2":
        self.x += other.x
        self.y += other.y
        return self

    def __isub__(self, other: "Vec2") -> "Vec2":
        self.x -= other.x
        self.y -= other.y
        return self

    def __imul__(self, scalar: float) -> "Vec2":
        self.x *= scalar
        self.y *= scalar
        return self

    @property
    def length_squared(self) -> float:
        return self.x*self.x + self.y*self.y

    @property
    def length(self) -> float:
        return math.hypot(self.x, self.y)

    @property
    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def normalized(self) -> "Vec2":
        magnitude = self.length
        return self/magnitude if magnitude > 1e-9 else Vec2()

    def normalize_ip(self) -> None:
        magnitude = self.length
        if magnitude > 1e-9:
            self.x /= magnitude
            self.y /= magnitude

    def dot(self, other: "Vec2") -> float:
        return self.x*other.x + self.y*other.y

    def cross(self, other: "Vec2") -> float:
        return self.x*other.y - self.y*other.x

    def distance_to(self, other: "Vec2") -> float:
        return math.hypot(self.x-other.x, self.y-other.y)

    def distance_squared_to(self, other: "Vec2") -> float:
        dx = self.x-other.x
        dy = self.y-other.y
        return dx*dx + dy*dy

    def rotate(self, radians: float) -> "Vec2":
        cosine = math.cos(radians)
        sine = math.sin(radians)
        return Vec2(self.x*cosine-self.y*sine, self.x*sine+self.y*cosine)

    def rotated_toward(self, target: "Vec2", radians: float) -> "Vec2":
        direction = (target-self).normalized()
        return self + direction.rotate(radians)

    def reflect(self, normal: "Vec2") -> "Vec2":
        unit_normal = normal.normalized()
        return self - unit_normal*(2*self.dot(unit_normal))

    def clamp_length(self, maximum: float) -> "Vec2":
        magnitude = self.length
        if magnitude > maximum and magnitude > 0:
            return self*(maximum/magnitude)
        return self.copy()

    def clamp_components(self, low: float, high: float) -> "Vec2":
        return Vec2(clamp(self.x, low, high), clamp(self.y, low, high))

    def move_toward(self, target: "Vec2", maximum_delta: float) -> "Vec2":
        offset = target-self
        distance = offset.length
        if distance <= maximum_delta or distance == 0:
            return target.copy()
        return self + offset*(maximum_delta/distance)

    def lerp_to(self, target: "Vec2", amount: float) -> "Vec2":
        return Vec2(lerp(self.x, target.x, amount), lerp(self.y, target.y, amount))

    def is_finite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y)

    def almost_equal(self, other: "Vec2", epsilon: float = 1e-5) -> bool:
        return self.distance_squared_to(other) <= epsilon*epsilon

    def angle_to(self, other: "Vec2") -> float:
        return math.atan2(self.cross(other), self.dot(other))

    def project_onto(self, other: "Vec2") -> "Vec2":
        denominator = other.length_squared
        if denominator <= 1e-9:
            return Vec2()
        return other*(self.dot(other)/denominator)

    def perpendicular(self) -> "Vec2":
        return Vec2(-self.y, self.x)

    def with_x(self, value: float) -> "Vec2":
        return Vec2(value, self.y)

    def with_y(self, value: float) -> "Vec2":
        return Vec2(self.x, value)

    def __iter__(self):
        yield self.x
        yield self.y

    def __repr__(self) -> str:
        return f"Vec2({self.x:.3f}, {self.y:.3f})"


def distance(a: Vec2, b: Vec2) -> float:
    return a.distance_to(b)


def distance_squared(a: Vec2, b: Vec2) -> float:
    return a.distance_squared_to(b)


def direction_from_angle(angle: float) -> Vec2:
    return Vec2(math.cos(angle), math.sin(angle))


def angle_between(a: Vec2, b: Vec2) -> float:
    if a.length_squared < 1e-9 or b.length_squared < 1e-9:
        return 0.0
    return a.angle_to(b)


def nearest_point_on_segment(point: Vec2, start: Vec2, end: Vec2) -> Vec2:
    segment = end-start
    length_squared = segment.length_squared
    if length_squared <= 1e-9:
        return start.copy()
    amount = clamp((point-start).dot(segment)/length_squared, 0.0, 1.0)
    return start + segment*amount


def distance_to_segment(point: Vec2, start: Vec2, end: Vec2) -> float:
    return point.distance_to(nearest_point_on_segment(point, start, end))


def average(points: Iterable[Vec2]) -> Vec2:
    total = Vec2()
    count = 0
    for point in points:
        total += point
        count += 1
    return total/count if count else Vec2()


def damp(current: float, target: float, smoothing: float, dt: float) -> float:
    """Frame-rate-independent exponential damping."""
    factor = 1.0-math.exp(-max(0.0, smoothing)*max(0.0, dt))
    return lerp(current, target, factor)


def spring_step(position: Vec2, velocity: Vec2, target: Vec2,
                stiffness: float, damping: float, dt: float) -> tuple[Vec2, Vec2]:
    """Integrate a damped spring for camera follow and secondary motion."""
    acceleration = (target-position)*stiffness - velocity*damping
    next_velocity = velocity + acceleration*dt
    next_position = position + next_velocity*dt
    return next_position, next_velocity

