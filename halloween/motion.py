"""Diferença contra fundo adaptativo com filtro de área e confirmação temporal."""

from dataclasses import dataclass
import cv2
import numpy as np

from .config import Settings


@dataclass
class MotionResult:
    frame: np.ndarray
    mask: np.ndarray
    roi: tuple[int, int, int, int]
    boxes: list[tuple[int, int, int, int]]
    ratio: float
    active: bool
    confirmed: bool
    lighting_change: bool
    warming_up: bool


class MotionDetector:
    def __init__(self, settings: Settings):
        self.cfg = settings
        self.reset()

    def reset(self) -> None:
        self.background = None
        self.started_at = None
        self.reset_confirmation()

    def reset_confirmation(self) -> None:
        self.streak = 0
        self.motion_since = None

    def process(self, frame: np.ndarray, now: float) -> MotionResult:
        cfg = self.cfg
        height, width = frame.shape[:2]
        scale = min(1.0, cfg.processing_width / width)
        frame = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
        height, width = frame.shape[:2]
        x, y = int(cfg.roi_x * width), int(cfg.roi_y * height)
        right = min(width, max(x + 1, round((cfg.roi_x + cfg.roi_width) * width)))
        bottom = min(height, max(y + 1, round((cfg.roi_y + cfg.roi_height) * height)))
        roi = (x, y, right - x, bottom - y)
        gray = cv2.cvtColor(frame[y:bottom, x:right], cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (cfg.blur_kernel, cfg.blur_kernel), 0)
        if self.background is None or self.background.shape != gray.shape:
            self.background = gray.astype(np.float32)
            self.started_at = now
            self.reset_confirmation()
        delta = cv2.absdiff(gray, cv2.convertScaleAbs(self.background))
        mask = cv2.threshold(delta, cfg.difference_threshold, 255, cv2.THRESH_BINARY)[1]
        if cfg.dilate_iterations:
            mask = cv2.dilate(mask, None, iterations=cfg.dilate_iterations)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) >= cfg.min_contour_area]
        ratio = cv2.countNonZero(mask) / mask.size
        warming_up = now - self.started_at < cfg.warmup_seconds
        lighting_change = ratio > cfg.max_motion_ratio
        active = bool(boxes) and ratio >= cfg.min_motion_ratio and not lighting_change and not warming_up
        if active:
            if self.motion_since is None:
                self.motion_since = now
            self.streak += 1
        else:
            self.reset_confirmation()
        sustained = (cfg.start_motion_seconds == 0 or
                     (self.motion_since is not None and now - self.motion_since > cfg.start_motion_seconds))
        cv2.accumulateWeighted(gray, self.background, cfg.background_alpha)
        return MotionResult(frame, mask, roi, boxes, ratio, active,
                            self.streak >= cfg.consecutive_frames and sustained, lighting_change, warming_up)
