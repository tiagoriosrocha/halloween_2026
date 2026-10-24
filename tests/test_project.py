"""Testes determinísticos sem webcam e sem emitir som."""

from dataclasses import fields, replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import cv2
import numpy as np
from dotenv import dotenv_values

from halloween.audio import ScareSequence, validate_audio_files
from halloween.config import ROOT, Settings, load_settings
from halloween.motion import MotionDetector


class FakeMusic:
    def __init__(self):
        self.playing = False
        self.plays = []
        self.volume = 0.0
        self.background_playing = False
        self.background_volume = 0.0

    def start_background(self, path, volume):
        self.background_playing = volume > 0
        self.background_volume = volume

    def set_background_volume(self, volume):
        self.background_volume = volume

    def play(self, path, volume, loop=False):
        self.playing = True
        self.plays.append((path.name, volume, loop))
        self.volume = volume

    def busy(self):
        return self.playing

    def set_volume(self, volume):
        self.volume = volume

    def stop(self):
        self.playing = False
        self.background_playing = False


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = replace(Settings(), rearm_quiet_seconds=2, cooldown_seconds=3, stop_if_no_motion_seconds=0)
        self.music = FakeMusic()
        self.seq = ScareSequence(self.cfg, self.music)

    def advance_to_ambience(self):
        self.assertTrue(self.seq.start(0))
        self.music.playing = False
        self.seq.tick(8, True)
        self.assertEqual(self.seq.state, "delay")
        self.seq.tick(10.99, True)
        self.assertEqual(len(self.music.plays), 1)
        self.seq.tick(11, True)
        self.assertEqual(self.seq.state, "scare")
        self.music.playing = False
        self.seq.tick(13.5, True)
        self.assertEqual(self.seq.state, "ambience")

    def test_exact_delay_tail_fade_and_rearm(self):
        self.advance_to_ambience()
        self.assertTrue(self.music.plays[-1][2])
        self.seq.tick(42.5, True)
        self.assertAlmostEqual(self.music.volume, self.cfg.master_volume * self.cfg.ambience_volume / 2)
        self.seq.tick(43.5, True)
        self.assertEqual(self.seq.state, "rearm")
        self.assertFalse(self.music.playing)
        self.seq.tick(80, True)
        self.assertEqual(self.seq.state, "rearm")
        self.seq.tick(81, False)
        self.seq.tick(82.99, False)
        self.assertEqual(self.seq.state, "rearm")
        self.seq.tick(83, False)
        self.assertEqual(self.seq.state, "ready")
        self.assertTrue(self.seq.start(84))

    def test_movement_cannot_restart_any_stage(self):
        self.seq.start(0)
        self.assertFalse(self.seq.start(1))
        self.music.playing = False
        self.seq.tick(8, True)
        self.assertFalse(self.seq.start(9))
        self.seq.tick(11, True)
        self.assertFalse(self.seq.start(12))
        self.music.playing = False
        self.seq.tick(14, True)
        self.assertFalse(self.seq.start(15))
        self.assertEqual(len(self.music.plays), 3)

    def test_motion_resets_quiet_period_and_cooldown_is_required(self):
        self.seq.start(0)
        self.seq.stop(1)
        self.seq.tick(1.1, False)
        self.seq.tick(3.2, False)
        self.assertEqual(self.seq.state, "rearm")
        self.seq.tick(3.5, True)
        self.seq.tick(4, False)
        self.seq.tick(5.9, False)
        self.assertEqual(self.seq.state, "rearm")
        self.seq.tick(6, False)
        self.assertEqual(self.seq.state, "ready")

    def test_disabled_scare_and_zero_ambience(self):
        seq = ScareSequence(replace(self.cfg, scare_enabled=False, ambience_seconds=0), self.music)
        seq.start(0)
        self.music.playing = False
        seq.tick(1, False)
        seq.tick(4, False)
        self.assertEqual(seq.state, "rearm")
        self.assertEqual(len(self.music.plays), 1)

    def test_cancel_does_not_resume_old_stage(self):
        self.seq.start(0)
        self.seq.stop(0.5)
        self.seq.tick(10, True)
        self.assertEqual(self.seq.state, "rearm")
        self.assertEqual(len(self.music.plays), 1)

    def test_background_continues_during_pause_and_stops_with_cycle(self):
        self.seq.start(0)
        self.assertTrue(self.music.background_playing)
        self.music.playing = False
        self.seq.tick(1, False)
        self.assertEqual(self.seq.state, "delay")
        self.assertTrue(self.music.background_playing)
        self.assertAlmostEqual(self.music.background_volume,
                               self.cfg.master_volume * self.cfg.background_screams_volume)
        self.seq.stop(2)
        self.assertFalse(self.music.background_playing)

    def test_repeat_immediately_after_completion_with_continuous_motion(self):
        seq = ScareSequence(Settings(), self.music)
        seq.start(0)
        self.music.playing = False
        seq.tick(8, True)
        seq.tick(11, True)
        self.music.playing = False
        seq.tick(13.5, True)
        seq.tick(43.5, True)
        self.assertEqual(seq.state, "ready")
        self.assertFalse(self.music.background_playing)
        self.assertTrue(seq.start(43.5))
        self.assertEqual(seq.state, "intro")
        self.assertTrue(self.music.background_playing)

    def test_optional_cooldown_without_quiet_scene_accepts_continuous_motion(self):
        cfg = replace(Settings(), cooldown_seconds=1)
        seq = ScareSequence(cfg, self.music)
        seq.start(0)
        seq.stop(1, wait_for_quiet=False)
        seq.tick(1.9, True)
        self.assertEqual(seq.state, "rearm")
        seq.tick(2, True)
        self.assertEqual(seq.state, "ready")

    def test_no_motion_stops_all_audio_in_every_stage_and_can_restart(self):
        for stage in ("intro", "delay", "scare", "ambience"):
            with self.subTest(stage=stage):
                music = FakeMusic()
                seq = ScareSequence(Settings(), music)
                seq.start(0)
                seq.state, seq.deadline = stage, 100
                seq.tick(4.99, False)
                self.assertTrue(seq.running)
                seq.tick(5, False)
                self.assertEqual(seq.state, "ready")
                self.assertFalse(music.playing)
                self.assertFalse(music.background_playing)
                self.assertTrue(seq.start(5.1))

    def test_new_motion_resets_inactivity_timer_and_prelude_tick_does_not(self):
        seq = ScareSequence(Settings(), self.music)
        seq.start(0)
        seq.tick(4, False)
        seq.tick(4.5, True)
        seq.tick(8)
        seq.tick(9.49, False)
        self.assertTrue(seq.running)
        seq.tick(9.5, False)
        self.assertEqual(seq.state, "ready")

    def test_audio_only_preview_ignores_motion_timeout(self):
        seq = ScareSequence(Settings(), self.music)
        seq.start(0)
        seq.tick(20)
        self.assertTrue(seq.running)


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = replace(Settings(), processing_width=320, warmup_seconds=0,
                           blur_kernel=3, dilate_iterations=0, min_contour_area=100,
                           min_motion_ratio=0.003, background_alpha=0.01, start_motion_seconds=0)
        self.detector = MotionDetector(self.cfg)
        self.frame = np.full((240, 320, 3), 30, np.uint8)
        self.detector.process(self.frame, 0)

    def moving_frame(self):
        frame = self.frame.copy()
        cv2.rectangle(frame, (80, 60), (140, 160), (230, 230, 230), -1)
        return frame

    def test_static_noise_does_not_trigger(self):
        rng = np.random.default_rng(5)
        for i in range(1, 20):
            frame = np.clip(self.frame.astype(int) + rng.integers(-3, 4, self.frame.shape), 0, 255).astype(np.uint8)
            self.assertFalse(self.detector.process(frame, i * 0.05).confirmed)

    def test_requires_consecutive_frames(self):
        for i in (1, 2):
            self.assertFalse(self.detector.process(self.moving_frame(), i * 0.05).confirmed)
        result = self.detector.process(self.moving_frame(), 0.15)
        self.assertTrue(result.confirmed)
        self.assertTrue(result.boxes)
        self.assertGreater(result.ratio, 0.003)
        self.assertFalse(self.detector.process(self.frame, 0.2).confirmed)

    def test_requires_more_than_three_seconds_of_continuous_motion(self):
        detector = MotionDetector(replace(self.cfg, start_motion_seconds=3, background_alpha=0.001))
        detector.process(self.frame, 0)
        for now in (1, 2, 3.99, 4):
            self.assertFalse(detector.process(self.moving_frame(), now).confirmed)
        self.assertTrue(detector.process(self.moving_frame(), 4.01).confirmed)
        # Movimento contínuo mantém a confirmação para repetir sem intervalo entre ciclos.
        self.assertTrue(detector.process(self.moving_frame(), 5).confirmed)

    def test_motion_gap_or_camera_failure_restarts_three_second_count(self):
        detector = MotionDetector(replace(self.cfg, start_motion_seconds=3, background_alpha=0.001))
        detector.process(self.frame, 0)
        detector.process(self.moving_frame(), 1)
        detector.process(self.moving_frame(), 3.9)
        detector.process(self.frame, 4)
        for now in (5, 6, 7.99):
            self.assertFalse(detector.process(self.moving_frame(), now).confirmed)
        self.assertTrue(detector.process(self.moving_frame(), 8.01).confirmed)
        detector.reset_confirmation()
        self.assertFalse(detector.process(self.moving_frame(), 9).confirmed)

    def test_global_light_is_rejected(self):
        result = self.detector.process(np.full_like(self.frame, 220), 1)
        self.assertTrue(result.lighting_change)
        self.assertFalse(result.confirmed)

    def test_outside_roi_is_ignored(self):
        detector = MotionDetector(replace(self.cfg, roi_x=0.6, roi_width=0.4))
        detector.process(self.frame, 0)
        for i in range(1, 5):
            self.assertFalse(detector.process(self.moving_frame(), i).active)

    def test_warmup_and_reset_prevent_trigger(self):
        detector = MotionDetector(replace(self.cfg, warmup_seconds=3, consecutive_frames=1))
        detector.process(self.frame, 0)
        self.assertFalse(detector.process(self.moving_frame(), 2).confirmed)
        self.assertTrue(detector.process(self.moving_frame(), 3.1).confirmed)
        detector.reset()
        self.assertFalse(detector.process(self.moving_frame(), 5).confirmed)


class ConfigAndAudioTests(unittest.TestCase):
    def test_every_setting_has_documented_env_value(self):
        values = dotenv_values(ROOT / ".env.example")
        self.assertEqual({f.name.upper() for f in fields(Settings)}, set(values))

    def test_env_load_and_process_override(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".env"
            path.write_text("MASTER_VOLUME=0.2\nSHOW_PREVIEW=false\n")
            with patch.dict(os.environ, {"MASTER_VOLUME": "0.7"}):
                cfg = load_settings(path)
            self.assertEqual(cfg.master_volume, 0.7)
            self.assertFalse(cfg.show_preview)

    def test_invalid_values_are_rejected(self):
        bad_values = [dict(blur_kernel=10), dict(master_volume=1.1),
                      dict(min_motion_ratio=0.8, max_motion_ratio=0.7),
                      dict(roi_x=0.8, roi_width=0.5), dict(ambience_seconds=float("nan")),
                      dict(ambience_seconds=1, ambience_fade_seconds=2),
                      dict(audio_scare=Settings().audio_intro)]
        for values in bad_values:
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(Settings(), **values).validate()

    def test_missing_audio_is_actionable(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = replace(Settings(), audio_intro=str(Path(temp) / "missing.wav"))
            with self.assertRaisesRegex(ValueError, "gerar_audio.py"):
                validate_audio_files(cfg)

    def test_generated_example_preserves_pause_and_configured_tail_with_quiet_background(self):
        cfg = load_settings()
        durations = validate_audio_files(cfg)
        timeline = json.loads(cfg.path(cfg.audio_example).with_suffix(".json").read_text())
        with wave.open(str(cfg.path(cfg.audio_example)), "rb") as audio:
            sr = audio.getframerate()
            data = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").reshape(-1, 2)
        intro_end = round(durations["audio_intro"] * sr)
        scare_start = intro_end + round(cfg.scare_delay_seconds * sr)
        pause = data[intro_end:scare_start].astype(float)
        if cfg.background_screams_volume > 0 and pause.size:
            self.assertGreater(np.max(np.abs(pause)), 1)
            self.assertLessEqual(np.max(np.abs(pause)),
                                 32767 * cfg.master_volume * cfg.background_screams_volume * 0.81 + 2)
        else:
            self.assertTrue(np.all(pause == 0))
        self.assertEqual(scare_start - intro_end, round(cfg.scare_delay_seconds * sr))
        tail_start = scare_start + round(durations["audio_scare"] * sr)
        self.assertEqual(len(data) - tail_start, round(cfg.ambience_seconds * sr))
        self.assertGreater(np.max(np.abs(data[scare_start:tail_start])), 3000)
        self.assertAlmostEqual(timeline["total_seconds"], len(data) / sr)
        self.assertGreater(np.std(data[:intro_end]), 500)
        self.assertLess(np.max(np.abs(data)), 32767)
        self.assertEqual(timeline["background_speech_texts"],
                         [text.strip() for text in cfg.background_speech_texts.split("|") if text.strip()]
                         if cfg.audio_mode == "completo" else [])

    def test_sound_only_mode_never_requests_spoken_background(self):
        from gerar_audio import background_soundscape, load_sources
        cfg = replace(Settings(), background_loop_seconds=5)
        with patch("gerar_audio.synth_voice", side_effect=AssertionError("Fala indevida no modo só sons")):
            background, events = background_soundscape(cfg, load_sources(cfg))
        self.assertEqual(events, [])
        self.assertGreater(float(np.max(np.abs(background))), 0.01)
        self.assertEqual(cfg.background_audio, cfg.audio_background_sounds)
        self.assertEqual(replace(cfg, audio_mode="completo").background_audio, cfg.audio_background_screams)


if __name__ == "__main__":
    unittest.main()
