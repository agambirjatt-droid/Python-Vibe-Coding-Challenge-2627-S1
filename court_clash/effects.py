"""Particles, camera motion, and crowd reactions for the broadcast presentation."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

import pygame

from .settings import VIRTUAL_HEIGHT, VIRTUAL_WIDTH, clamp
from .vector import Vec2, damp, spring_step


@dataclass(slots=True)
class Particle:
    """One short-lived screen-space particle."""

    position: Vec2
    velocity: Vec2
    color: tuple[int, int, int]
    radius: float
    life: float
    max_life: float
    gravity: float = 0.0
    drag: float = 0.0
    kind: str = "spark"
    rotation: float = 0.0
    spin: float = 0.0

    @property
    def age_fraction(self) -> float:
        if self.max_life <= 0:
            return 1.0
        return clamp(1.0-self.life/self.max_life, 0.0, 1.0)

    @property
    def alpha_fraction(self) -> float:
        return clamp(self.life/max(.001, self.max_life*.28), 0.0, 1.0)

    def update(self, dt: float) -> None:
        self.position += self.velocity*dt
        self.velocity.y += self.gravity*dt
        self.velocity *= math.exp(-self.drag*dt)
        self.rotation += self.spin*dt
        self.life -= dt

    def alive(self) -> bool:
        return self.life > 0.0


class ParticleSystem:
    """Managed visual bursts for makes, dunks, steals, blocks, and dust."""

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)
        self.particles: list[Particle] = []
        self.max_particles = 1400
        self.flash_alpha = 0.0
        self.flash_color = (255, 255, 255)
        self.flash_time = 0.0

    def clear(self) -> None:
        self.particles.clear()
        self.flash_alpha = 0.0
        self.flash_time = 0.0

    def update(self, dt: float) -> None:
        for particle in self.particles:
            particle.update(dt)
        self.particles = [particle for particle in self.particles if particle.alive()]
        self.flash_time = max(0.0, self.flash_time-dt)
        self.flash_alpha = damp(self.flash_alpha, 0.0, 15.0, dt)

    def burst(self, position: Vec2, color: tuple[int, int, int],
              count: int = 30, speed: tuple[float, float] = (70, 320),
              life: tuple[float, float] = (.3, .85), kind: str = "spark") -> None:
        for _ in range(count):
            angle = self.random.uniform(0.0, math.tau)
            magnitude = self.random.uniform(*speed)
            velocity = Vec2(math.cos(angle), math.sin(angle))*magnitude
            particle_color = self._variation(color, 28)
            radius = self.random.uniform(2.0, 6.5)
            lifetime = self.random.uniform(*life)
            particle = Particle(
                position.copy(),
                velocity,
                particle_color,
                radius,
                lifetime,
                lifetime,
                gravity=self.random.uniform(100, 360),
                drag=self.random.uniform(.2, 1.8),
                kind=kind,
                rotation=self.random.uniform(0, math.tau),
                spin=self.random.uniform(-9, 9),
            )
            self.particles.append(particle)
        self._trim()

    def swish(self, position: Vec2, team_color: tuple[int, int, int]) -> None:
        self.burst(position, team_color, 42, (55, 260), (.45, 1.05), "confetti")
        self.flash((255, 238, 176), .20)

    def dunk(self, position: Vec2, team_color: tuple[int, int, int]) -> None:
        self.burst(position, team_color, 68, (95, 460), (.35, .95), "star")
        self.ring(position, team_color, 45, .42)
        self.flash((255, 203, 87), .28)

    def steal(self, position: Vec2, team_color: tuple[int, int, int]) -> None:
        self.burst(position, team_color, 24, (45, 190), (.25, .6), "spark")

    def block(self, position: Vec2) -> None:
        self.burst(position, (240, 246, 255), 32, (100, 340), (.2, .6), "streak")
        self.flash((176, 210, 255), .13)

    def rim_hit(self, position: Vec2) -> None:
        self.burst(position, (255, 130, 82), 14, (50, 160), (.18, .42), "spark")

    def foot_dust(self, position: Vec2, color: tuple[int, int, int]) -> None:
        self.burst(position, color, 5, (12, 58), (.16, .34), "dust")

    def ring(self, position: Vec2, color: tuple[int, int, int],
             radius: float, life: float) -> None:
        particle = Particle(position.copy(), Vec2(), color, radius,
                            life, life, kind="ring")
        self.particles.append(particle)

    def flash(self, color: tuple[int, int, int], strength: float) -> None:
        self.flash_color = color
        self.flash_alpha = max(self.flash_alpha, strength)
        self.flash_time = max(self.flash_time, strength)

    def _variation(self, color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
        return tuple(int(clamp(channel+self.random.randint(-amount, amount), 0, 255))
                     for channel in color)

    def _trim(self) -> None:
        overflow = len(self.particles)-self.max_particles
        if overflow > 0:
            del self.particles[:overflow]

    def draw(self, surface: pygame.Surface) -> None:
        for particle in self.particles:
            if particle.kind == "ring":
                self._draw_ring(surface, particle)
            else:
                self._draw_particle(surface, particle)
        if self.flash_alpha > .01:
            alpha = int(clamp(self.flash_alpha*90, 0, 70))
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((*self.flash_color, alpha))
            surface.blit(overlay, (0, 0))

    def _draw_particle(self, surface: pygame.Surface, particle: Particle) -> None:
        center = particle.position.rounded()
        alpha = particle.alpha_fraction
        radius = max(1, int(particle.radius*(.5+alpha*.5)))
        if particle.kind == "streak":
            tail = particle.position-particle.velocity.normalized()*radius*3
            pygame.draw.line(surface, particle.color, tail.rounded(), center, max(1, radius//2))
        elif particle.kind == "confetti":
            width = max(2, int(radius*1.1))
            height = max(3, int(radius*1.8))
            rect = pygame.Rect(0, 0, width, height)
            rect.center = center
            pygame.draw.rect(surface, particle.color, rect, border_radius=1)
        elif particle.kind == "star":
            self._draw_star(surface, center, radius, particle.color, particle.rotation)
        else:
            pygame.draw.circle(surface, particle.color, center, radius)

    def _draw_ring(self, surface: pygame.Surface, particle: Particle) -> None:
        progress = particle.age_fraction
        radius = max(1, int(particle.radius*(.3+progress*2.2)))
        width = max(1, int(6*(1-progress)))
        alpha = int(255*(1-progress))
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.ellipse(layer, (*particle.color, alpha),
                            (particle.position.x-radius, particle.position.y-radius*.24,
                             radius*2, radius*.48), width)
        surface.blit(layer, (0, 0))

    def _draw_star(self, surface: pygame.Surface, center: tuple[int, int],
                   radius: int, color: tuple[int, int, int], rotation: float) -> None:
        points = []
        for index in range(10):
            angle = rotation-math.pi/2 + index*math.pi/5
            length = radius if index%2 == 0 else radius*.42
            points.append((center[0]+math.cos(angle)*length,
                           center[1]+math.sin(angle)*length))
        pygame.draw.polygon(surface, color, points)


class CameraRig:
    """Soft follow camera and controlled impact shake."""

    def __init__(self) -> None:
        self.position = Vec2(VIRTUAL_WIDTH/2, VIRTUAL_HEIGHT/2)
        self.previous = self.position.copy()
        self.velocity = Vec2()
        self.offset = Vec2()
        self.shake_time = 0.0
        self.shake_strength = 0.0
        self.random = random.Random(42)

    def reset(self) -> None:
        self.position = Vec2(VIRTUAL_WIDTH/2, VIRTUAL_HEIGHT/2)
        self.previous = self.position.copy()
        self.velocity = Vec2()
        self.offset = Vec2()
        self.shake_time = 0.0
        self.shake_strength = 0.0

    def add_shake(self, strength: float, duration: float) -> None:
        self.shake_strength = max(self.shake_strength, strength)
        self.shake_time = max(self.shake_time, duration)

    def update(self, target: Vec2, dt: float) -> None:
        self.previous = self.position.copy()
        self.position, self.velocity = spring_step(self.position, self.velocity,
                                                   target, 10.0, 6.5, dt)
        self.position.x = clamp(self.position.x, VIRTUAL_WIDTH*.42, VIRTUAL_WIDTH*.58)
        self.position.y = clamp(self.position.y, VIRTUAL_HEIGHT*.43, VIRTUAL_HEIGHT*.57)
        self.shake_time = max(0.0, self.shake_time-dt)
        decay = self.shake_time/max(.001, self.shake_time+.16)
        magnitude = self.shake_strength*decay
        self.offset.x = self.random.uniform(-magnitude, magnitude)
        self.offset.y = self.random.uniform(-magnitude, magnitude)*.55
        if self.shake_time == 0.0:
            self.shake_strength = damp(self.shake_strength, 0.0, 12.0, dt)

    def screen_offset(self, alpha: float = 1.0) -> Vec2:
        return self.offset.copy()


class CrowdReaction:
    """Smooth crowd wave state used by the cached arena background."""

    def __init__(self, count: int = 120) -> None:
        self.phases = [random.random()*math.tau for _ in range(count)]
        self.energy = 0.0
        self.wave_position = .5

    def excite(self, amount: float, location: float) -> None:
        self.energy = max(self.energy, clamp(amount, 0.0, 1.0))
        self.wave_position = clamp(location, 0.0, 1.0)

    def update(self, dt: float) -> None:
        self.energy = max(0.0, self.energy-dt*.38)
        self.phases = [(phase+dt*(1.8+self.energy*5.0))%math.tau
                       for phase in self.phases]

    def body_bounce(self, index: int) -> float:
        phase = self.phases[index%len(self.phases)]
        return abs(math.sin(phase))*2.0*self.energy

    def local_energy(self, normalized_x: float) -> float:
        distance = abs(normalized_x-self.wave_position)
        return self.energy*math.exp(-distance*5.0)

