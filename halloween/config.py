"""Configuração validada. Caminhos relativos usam a raiz do projeto."""

from dataclasses import dataclass, fields
from pathlib import Path
import math
import os

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    camera_index: int = 0
    camera_backend: str = "auto"
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30
    processing_width: int = 640
    processing_fps: int = 20
    camera_max_read_failures: int = 20
    show_preview: bool = True
    preview_fullscreen: bool = False
    show_detection_overlay: bool = False
    show_mask: bool = False
    mirror_preview: bool = False
    warmup_seconds: float = 3.0
    blur_kernel: int = 21
    difference_threshold: int = 25
    min_contour_area: float = 1600.0
    min_motion_ratio: float = 0.008
    max_motion_ratio: float = 0.70
    consecutive_frames: int = 3
    start_motion_seconds: float = 3.0
    background_alpha: float = 0.035
    dilate_iterations: int = 2
    roi_x: float = 0.0
    roi_y: float = 0.0
    roi_width: float = 1.0
    roi_height: float = 1.0
    rearm_quiet_seconds: float = 0.0
    cooldown_seconds: float = 0.0
    stop_if_no_motion_seconds: float = 5.0
    audio_mode: str = "sons_e_boas_vindas"
    audio_intro: str = "audio/01_boas_vindas.wav"
    audio_scare: str = "audio/02_susto.wav"
    audio_ambience: str = "audio/03_ambiente.wav"
    audio_background_screams: str = "audio/04_gritos_fundo.wav"
    audio_background_sounds: str = "audio/05_fundo_sons.wav"
    audio_example: str = "audio/halloween_exemplo.wav"
    source_witch_laugh: str = "audio/fontes/risada_bruxa.wav"
    source_witch_scream: str = "audio/fontes/grito_bruxa.wav"
    source_bat: str = "audio/fontes/morcego.wav"
    source_wings: str = "audio/fontes/asas.wav"
    source_wind: str = "audio/fontes/vento.wav"
    source_wood_slam: str = "audio/fontes/porta_batendo.wav"
    source_wood_creak: str = "audio/fontes/madeira_rangendo.wav"
    source_chainsaw: str = "audio/fontes/motosserra.wav"
    source_greeting_voice: str = "audio/falas_ia/boas_vindas.wav"
    audio_device: str = ""
    audio_buffer: int = 1024
    audio_sample_rate: int = 44100
    master_volume: float = 0.90
    intro_volume: float = 1.0
    scare_volume: float = 1.0
    ambience_volume: float = 0.40
    background_screams_volume: float = 0.25
    scare_enabled: bool = True
    scare_delay_seconds: float = 3.0
    ambience_seconds: float = 30.0
    ambience_fade_seconds: float = 2.0
    speech_text: str = "Bem-vindos ao Halloween do New Life!"
    speech_voice: str = "Grandma (Português (Brasil))"
    speech_rate: int = 112
    voice_pitch: float = 0.96
    voice_gain: float = 0.45
    opening_scream_gain: float = 1.0
    scream_compression_ratio: float = 3.5
    bats_gain: float = 0.18
    witch_gain: float = 0.45
    scare_gain: float = 1.0
    ambience_gain: float = 0.30
    scare_sound_seconds: float = 2.5
    ambience_loop_seconds: float = 30.0
    background_loop_seconds: float = 45.0
    background_min_interval_seconds: float = 1.5
    background_max_interval_seconds: float = 2.8
    background_speech_texts: str = "Socorro!|Me salve!|Estou preso aqui!|Eu vou matar você!|Não adianta correr!"
    background_help_voice: str = "Eddy (Português (Brasil))"
    background_witch_voice: str = "Grandma (Português (Brasil))"
    background_speech_rate: int = 145
    chainsaw_gain: float = 0.35
    random_seed: int = 31
    log_level: str = "INFO"

    def path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else ROOT / path

    @property
    def background_audio(self) -> str:
        return self.audio_background_sounds if self.audio_mode == "sons_e_boas_vindas" else self.audio_background_screams

    def validate(self) -> None:
        if self.audio_mode not in {"completo", "sons_e_boas_vindas"}:
            raise ValueError("AUDIO_MODE deve ser completo ou sons_e_boas_vindas.")
        ranges = {
            "camera_index": (0, 100), "camera_width": (160, 7680),
            "camera_height": (120, 4320), "camera_fps": (1, 120),
            "processing_width": (64, 3840), "processing_fps": (1, 120),
            "camera_max_read_failures": (1, 1000), "warmup_seconds": (0, 120),
            "blur_kernel": (1, 101), "difference_threshold": (1, 254),
            "min_contour_area": (1, 10000000), "min_motion_ratio": (0, 1),
            "max_motion_ratio": (0.001, 1), "consecutive_frames": (1, 200),
            "start_motion_seconds": (0, 600),
            "background_alpha": (0.0001, 1), "dilate_iterations": (0, 10),
            "roi_x": (0, 0.99), "roi_y": (0, 0.99),
            "roi_width": (0.01, 1), "roi_height": (0.01, 1),
            "rearm_quiet_seconds": (0, 600), "cooldown_seconds": (0, 3600),
            "stop_if_no_motion_seconds": (0, 3600),
            "audio_buffer": (128, 32768), "master_volume": (0, 1),
            "intro_volume": (0, 1), "scare_volume": (0, 1),
            "ambience_volume": (0, 1), "scare_delay_seconds": (0, 120),
            "background_screams_volume": (0, 1), "chainsaw_gain": (0, 1),
            "background_loop_seconds": (5, 180),
            "background_min_interval_seconds": (0.25, 30),
            "background_max_interval_seconds": (0.25, 30),
            "background_speech_rate": (60, 400),
            "ambience_seconds": (0, 3600), "ambience_fade_seconds": (0, 60),
            "speech_rate": (60, 400), "voice_pitch": (0.5, 1.5),
            "voice_gain": (0, 1), "opening_scream_gain": (0, 1), "bats_gain": (0, 1), "witch_gain": (0, 1),
            "scream_compression_ratio": (1, 8),
            "scare_gain": (0, 1), "ambience_gain": (0, 1),
            "scare_sound_seconds": (0.2, 20), "ambience_loop_seconds": (2, 120),
            "random_seed": (0, 2147483647),
        }
        for name, (low, high) in ranges.items():
            value = getattr(self, name)
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name.upper()} deve estar entre {low} e {high}.")
        if self.blur_kernel % 2 == 0:
            raise ValueError("BLUR_KERNEL deve ser ímpar (ex.: 21).")
        if self.background_min_interval_seconds > self.background_max_interval_seconds:
            raise ValueError("BACKGROUND_MIN_INTERVAL_SECONDS deve ser <= BACKGROUND_MAX_INTERVAL_SECONDS.")
        if not any(text.strip() for text in self.background_speech_texts.split("|")):
            raise ValueError("BACKGROUND_SPEECH_TEXTS deve conter pelo menos uma frase.")
        if self.roi_x + self.roi_width > 1.000001 or self.roi_y + self.roi_height > 1.000001:
            raise ValueError("A região ROI deve caber na imagem: X + WIDTH e Y + HEIGHT <= 1.")
        if self.min_motion_ratio >= self.max_motion_ratio:
            raise ValueError("MIN_MOTION_RATIO deve ser menor que MAX_MOTION_RATIO.")
        if self.ambience_fade_seconds > self.ambience_seconds:
            raise ValueError("AMBIENCE_FADE_SECONDS não pode ultrapassar AMBIENCE_SECONDS.")
        if self.camera_backend not in {"auto", "avfoundation", "dshow", "msmf", "v4l2"}:
            raise ValueError("CAMERA_BACKEND inválido: auto, avfoundation, dshow, msmf ou v4l2.")
        if self.audio_sample_rate not in {22050, 44100, 48000}:
            raise ValueError("AUDIO_SAMPLE_RATE deve ser 22050, 44100 ou 48000.")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("LOG_LEVEL inválido: DEBUG, INFO, WARNING ou ERROR.")
        paths = [self.path(getattr(self, name)).resolve() for name in
                 ("audio_intro", "audio_scare", "audio_ambience", "audio_background_screams", "audio_background_sounds", "audio_example")]
        if len(set(paths)) != len(paths):
            raise ValueError("Os caminhos AUDIO_* devem ser diferentes entre si.")


def load_settings(env_path: Path | None = None) -> Settings:
    source = env_path or ROOT / ".env"
    if env_path is not None and not source.is_file():
        raise ValueError(f"Arquivo de configuração não encontrado: {source}")
    values = {**dotenv_values(source), **os.environ}
    defaults = Settings()
    parsed = {}
    for field in fields(defaults):
        key = field.name.upper()
        if key not in values:
            continue
        raw = str(values[key] or "").strip()
        default = getattr(defaults, field.name)
        try:
            if isinstance(default, bool):
                if raw.lower() not in {"true", "false", "1", "0", "yes", "no", "sim", "nao", "não"}:
                    raise ValueError("use true ou false")
                parsed[field.name] = raw.lower() in {"true", "1", "yes", "sim"}
            elif isinstance(default, int):
                parsed[field.name] = int(raw)
            elif isinstance(default, float):
                parsed[field.name] = float(raw)
            else:
                parsed[field.name] = raw
        except ValueError as exc:
            raise ValueError(f"{key} inválido: {raw!r} ({exc})") from exc
    result = Settings(**parsed)
    result.validate()
    return result
