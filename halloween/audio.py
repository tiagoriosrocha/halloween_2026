"""Sequência sem bloquear a câmera; novos disparos não sobrepõem o áudio."""

import logging
import os
import wave

from .config import Settings

LOG = logging.getLogger(__name__)


def validate_audio_files(cfg: Settings) -> dict[str, float]:
    durations = {}
    background_field = "audio_background_sounds" if cfg.audio_mode == "sons_e_boas_vindas" else "audio_background_screams"
    for field in ("audio_intro", "audio_scare", "audio_ambience", background_field):
        if field == "audio_scare" and not cfg.scare_enabled:
            continue
        if field == background_field and cfg.background_screams_volume == 0:
            continue
        path = cfg.path(getattr(cfg, field))
        if not path.is_file():
            raise ValueError(f"Áudio não encontrado: {path}. Execute: python gerar_audio.py")
        try:
            with wave.open(str(path), "rb") as audio:
                if audio.getnframes() == 0 or audio.getsampwidth() != 2 or audio.getnchannels() not in (1, 2):
                    raise ValueError(f"Use WAV PCM de 16 bits, mono ou estéreo: {path}")
                expected = audio.getnframes() * audio.getsampwidth() * audio.getnchannels()
                if len(audio.readframes(audio.getnframes())) != expected:
                    raise ValueError(f"Arquivo WAV incompleto: {path}")
                durations[field] = audio.getnframes() / audio.getframerate()
        except (wave.Error, EOFError) as exc:
            raise ValueError(f"Arquivo WAV inválido: {path}: {exc}") from exc
    return durations


class PygameMusic:
    def __init__(self, cfg: Settings):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        self.pygame = pygame
        kwargs = {"frequency": cfg.audio_sample_rate, "size": -16,
                  "channels": 2, "buffer": cfg.audio_buffer}
        if cfg.audio_device:
            kwargs["devicename"] = cfg.audio_device
        try:
            pygame.mixer.init(**kwargs)
        except pygame.error as exc:
            raise RuntimeError(f"Não foi possível abrir a saída de som. Confira AUDIO_DEVICE: {exc}") from exc
        self.background_channel = pygame.mixer.Channel(0)
        self.background_sound = None
        self.background_path = None

    def start_background(self, path, volume):
        if volume <= 0:
            return
        if self.background_path != path:
            self.background_sound = self.pygame.mixer.Sound(str(path))
            self.background_path = path
        self.set_background_volume(volume)
        self.background_channel.play(self.background_sound, loops=-1)

    def set_background_volume(self, volume):
        self.background_channel.set_volume(volume)

    def play(self, path, volume, loop=False):
        self.pygame.mixer.music.load(str(path))
        self.set_volume(volume)
        self.pygame.mixer.music.play(loops=-1 if loop else 0)

    def busy(self):
        return self.pygame.mixer.music.get_busy()

    def set_volume(self, volume):
        self.pygame.mixer.music.set_volume(volume)

    def stop(self):
        self.pygame.mixer.music.stop()
        self.background_channel.stop()

    def close(self):
        self.stop()
        self.pygame.mixer.quit()


class ScareSequence:
    LABELS = {"ready": "ARMADO", "intro": "BOAS-VINDAS", "delay": "SUSPENSE",
              "scare": "SUSTO", "ambience": "AMBIENTE", "rearm": "AGUARDANDO CENA QUIETA"}

    def __init__(self, cfg: Settings, music):
        self.cfg, self.music = cfg, music
        self.state = "ready"
        self.deadline = 0.0
        self.quiet_since = None
        self.required_quiet_seconds = cfg.rearm_quiet_seconds
        self.last_motion_at = None

    @property
    def running(self):
        return self.state in {"intro", "delay", "scare", "ambience"}

    def start(self, now: float) -> bool:
        if self.state != "ready":
            return False
        self.music.play(self.cfg.path(self.cfg.audio_intro), self.cfg.master_volume * self.cfg.intro_volume)
        self.music.start_background(self.cfg.path(self.cfg.background_audio),
                                    self.cfg.master_volume * self.cfg.background_screams_volume)
        self.state = "intro"
        self.last_motion_at = now
        LOG.info("Movimento detectado: iniciando boas-vindas.")
        return True

    def _ambience(self, now):
        if self.cfg.ambience_seconds > 0:
            self.music.play(self.cfg.path(self.cfg.audio_ambience),
                            self.cfg.master_volume * self.cfg.ambience_volume, loop=True)
            self.state = "ambience"
            self.deadline = now + self.cfg.ambience_seconds
            LOG.info("Ambiente assustador por %.1f segundos.", self.cfg.ambience_seconds)
        else:
            self.stop(now, wait_for_quiet=False)

    def stop(self, now: float, wait_for_quiet: bool = True):
        self.music.stop()
        # Parada manual aguarda repouso para S não ser desfeito pelo movimento seguinte.
        self.required_quiet_seconds = (max(2.0, self.cfg.rearm_quiet_seconds)
                                       if wait_for_quiet else self.cfg.rearm_quiet_seconds)
        self.state = "rearm" if self.required_quiet_seconds > 0 or self.cfg.cooldown_seconds > 0 else "ready"
        self.deadline = now + self.cfg.cooldown_seconds
        self.quiet_since = None
        self.last_motion_at = None
        LOG.info("Áudio encerrado. %s", "Pronto para repetir com movimento." if self.state == "ready"
                 else "Aguardando intervalo configurado ou repouso.")

    def tick(self, now: float, motion_active: bool | None = None):
        cfg = self.cfg
        # None avança o áudio sem inventar movimento (pré-leitura, falhas e teste de som).
        if self.running and motion_active is not None:
            if motion_active:
                self.last_motion_at = now
            elif (cfg.stop_if_no_motion_seconds > 0 and self.last_motion_at is not None
                  and now - self.last_motion_at >= cfg.stop_if_no_motion_seconds):
                LOG.info("Sem movimento por %.1f segundos: interrompendo áudio.", cfg.stop_if_no_motion_seconds)
                self.stop(now, wait_for_quiet=False)
                return
        if self.state == "intro" and not self.music.busy():
            self.state, self.deadline = "delay", now + cfg.scare_delay_seconds
            LOG.info("Pausa de %.1f segundos antes do susto.", cfg.scare_delay_seconds)
        elif self.state == "delay" and now >= self.deadline:
            if cfg.scare_enabled:
                self.music.play(cfg.path(cfg.audio_scare), cfg.master_volume * cfg.scare_volume)
                self.state = "scare"
                LOG.info("Susto!")
            else:
                self._ambience(now)
        elif self.state == "scare" and not self.music.busy():
            self._ambience(now)
        elif self.state == "ambience":
            remaining = self.deadline - now
            if remaining <= 0:
                self.stop(now, wait_for_quiet=False)
            elif not self.music.busy():
                self.stop(now)
                raise RuntimeError("A reprodução do ambiente foi interrompida pela saída de som.")
            elif cfg.ambience_fade_seconds > 0 and remaining < cfg.ambience_fade_seconds:
                self.music.set_volume(cfg.master_volume * cfg.ambience_volume * remaining / cfg.ambience_fade_seconds)
                self.music.set_background_volume(cfg.master_volume * cfg.background_screams_volume
                                                 * remaining / cfg.ambience_fade_seconds)
        elif self.state == "rearm":
            if motion_active is None or motion_active:
                self.quiet_since = None
            elif self.quiet_since is None:
                self.quiet_since = now
            quiet_enough = (self.required_quiet_seconds == 0 or
                            (self.quiet_since is not None and now - self.quiet_since >= self.required_quiet_seconds))
            if now >= self.deadline and quiet_enough:
                self.state = "ready"
                LOG.info("Armado: aguardando novo movimento.")
