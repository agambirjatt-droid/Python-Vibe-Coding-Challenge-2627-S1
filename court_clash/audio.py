"""Procedural sound cues that require no external music or sound files."""

from __future__ import annotations

from array import array
import math
import random

import pygame


class AudioBus:
    """Small synthesizer for whistle, rim, dribble, net, and crowd cues."""

    SAMPLE_RATE = 22050

    def __init__(self) -> None:
        self.enabled = True
        self.available = False
        self.master_volume = .32
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.channels: dict[str, pygame.mixer.Channel | None] = {}
        self.random = random.Random(101)
        self._initialize_mixer()
        if self.available:
            self._build_sound_bank()

    def _initialize_mixer(self) -> None:
        try:
            pygame.mixer.pre_init(self.SAMPLE_RATE, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(12)
            self.available = True
        except pygame.error:
            self.available = False

    def _build_sound_bank(self) -> None:
        self.sounds["dribble"] = self._tone(115, .075, .42, -25, noise=.16)
        self.sounds["rim"] = self._tone(690, .12, .38, -390, noise=.35)
        self.sounds["swish"] = self._tone(740, .19, .26, 220, noise=.12)
        self.sounds["dunk"] = self._tone(68, .30, .62, -35, noise=.52)
        self.sounds["steal"] = self._tone(480, .10, .30, 180, noise=.18)
        self.sounds["block"] = self._tone(160, .16, .43, -40, noise=.8)
        self.sounds["buzzer"] = self._tone(210, .75, .34, 0, noise=.04)
        self.sounds["whistle"] = self._tone(1650, .27, .18, 120, noise=.02)
        self.sounds["crowd"] = self._tone(280, .22, .11, 80, noise=.82)
        self.sounds["crossover"] = self._tone(360, .065, .16, -180, noise=.08)
        self.sounds["perfect"] = self._tone(980, .16, .22, 520, noise=.02)
        self.sounds["horn"] = self._tone(128, .66, .28, -8, noise=.05)
        for name, sound in self.sounds.items():
            sound.set_volume(self.master_volume)
            self.channels[name] = None

    def _tone(self, start_frequency: float, duration: float, volume: float,
              pitch_delta: float, noise: float = 0.0) -> pygame.mixer.Sound:
        sample_count = max(1, int(self.SAMPLE_RATE*duration))
        samples = array("h")
        phase = 0.0
        for index in range(sample_count):
            progress = index/sample_count
            envelope = (1.0-progress)**2.2
            frequency = start_frequency + pitch_delta*progress
            phase += math.tau*frequency/self.SAMPLE_RATE
            fundamental = math.sin(phase)
            overtone = math.sin(phase*2.01)*.16
            static = self.random.uniform(-1, 1)*noise
            value = (fundamental+overtone+static)*envelope*volume
            samples.append(max(-32767, min(32767, int(value*32767))))
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled or not self.available:
            return
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            channel = sound.play()
            if channel is not None:
                channel.set_volume(self.master_volume*max(0.0, min(1.0, volume)))
                self.channels[name] = channel
        except pygame.error:
            self.available = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled and self.available:
            pygame.mixer.stop()

    def toggle(self) -> bool:
        self.set_enabled(not self.enabled)
        return self.enabled

    def set_master_volume(self, volume: float) -> None:
        self.master_volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.master_volume)

    def stop_all(self) -> None:
        if self.available:
            pygame.mixer.stop()

    def shutdown(self) -> None:
        self.stop_all()
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        self.available = False

