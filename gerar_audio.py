#!/usr/bin/env python3
"""Monta uma cena de bruxas usando gargalhadas, gritos e foley gravados."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

from halloween.config import ROOT, Settings, load_settings


def write_wav(path: Path, samples: np.ndarray, sr: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (np.clip(samples, -0.98, 0.98) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2 if data.ndim == 2 else 1)
        output.setsampwidth(2)
        output.setframerate(sr)
        output.writeframes(data.tobytes())


def read_wav(path: Path, sr: int) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise ValueError("A gravação de voz deve ser WAV PCM de 16 bits.")
        data = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(float) / 32768
        data = data.reshape(-1, source.getnchannels()).mean(axis=1)
        source_rate = source.getframerate()
    if source_rate != sr:
        data = respeed(data, source_rate / sr)
    return data


def respeed(data, factor):
    return np.interp(np.arange(0, len(data), factor), np.arange(len(data)), data)


def normalize(data, peak=0.9):
    maximum = np.max(np.abs(data)) if data.size else 0
    return data * (peak / maximum) if maximum > 0 else data


def fade(data, sr, attack=0.015, release=0.06):
    data = data.copy()
    a, r = min(len(data), int(sr * attack)), min(len(data), int(sr * release))
    if a:
        data[:a] *= np.linspace(0, 1, a)
    if r:
        data[-r:] *= np.linspace(1, 0, r)
    return data


def add(track, sound, start, sr, gain=1.0, pan=0.0):
    offset = round(start * sr)
    count = min(len(sound), len(track) - offset)
    if count <= 0:
        return
    # Pan estéreo com potência constante.
    angle = (pan + 1) * np.pi / 4
    track[offset:offset + count, 0] += sound[:count] * gain * np.cos(angle)
    track[offset:offset + count, 1] += sound[:count] * gain * np.sin(angle)


def trim_silence(data):
    """Preserva pausas internas da interpretação e retira só as pontas vazias."""
    if not data.size:
        raise ValueError("Uma das fontes de áudio está vazia.")
    active = np.flatnonzero(np.abs(data) > max(float(np.max(np.abs(data))) * 0.003, 1e-5))
    if not active.size:
        raise ValueError("Uma das fontes de áudio contém apenas silêncio.")
    return data[active[0]:active[-1] + 1].copy()


def soften(data, sr, frequency=3500):
    width = max(1, min(len(data), round(sr / frequency)))
    return np.convolve(data, np.ones(width) / width, mode="same")


def stronger_scream(data, sr, ratio):
    """Sustenta a intensidade da voz sem recortar seus picos."""
    data = normalize(data, 0.97)
    window = max(1, min(len(data), round(sr * 0.015)))
    kernel = np.ones(window) / window
    envelope = np.sqrt(np.convolve(data * data, kernel, mode="same") + 1e-12)
    gain = (np.maximum(envelope, 0.12) / 0.12) ** (1 / ratio - 1)
    gain = np.convolve(gain, kernel, mode="same")
    return normalize(data * gain, 0.97)


def room(data, sr, rng, wet=0.15, seconds=0.42):
    """Reflexões difusas de uma sala, sem repetição de sílabas ou modulação."""
    size = max(1, round(seconds * sr))
    impulse = soften(rng.normal(0, 1, size), sr, 5000)
    impulse *= np.exp(-np.linspace(0, 7, size))
    impulse[:min(size, round(sr * 0.018))] = 0
    impulse /= max(float(np.linalg.norm(impulse)), 1e-9)
    count = len(data) + size - 1
    fft_size = 1 << (count - 1).bit_length()
    reverberation = np.fft.irfft(np.fft.rfft(data, fft_size) * np.fft.rfft(impulse, fft_size), fft_size)[:count]
    output = reverberation * wet
    output[:len(data)] += data
    return fade(output, sr, attack=0.006, release=0.05)


def load_sources(cfg):
    keys = {"laugh": "source_witch_laugh", "scream": "source_witch_scream",
            "bat": "source_bat", "wings": "source_wings", "wind": "source_wind",
            "slam": "source_wood_slam", "creak": "source_wood_creak", "chainsaw": "source_chainsaw"}
    sources = {}
    for key, field in keys.items():
        path = cfg.path(getattr(cfg, field))
        if not path.is_file():
            raise ValueError(f"Fonte gravada não encontrada: {path}. Veja audio/FONTES.md.")
        sources[key] = trim_silence(read_wav(path, cfg.audio_sample_rate))
    return sources


def synth_voice(cfg: Settings, voice_file: Path | None, reuse_voice: bool, cache_stem="voz_original"):
    sr = cfg.audio_sample_rate
    cache = ROOT / "audio" / f"{cache_stem}.wav"
    meta_path = ROOT / "audio" / f"{cache_stem}.json"
    metadata = {"text": cfg.speech_text, "voice": cfg.speech_voice, "rate": cfg.speech_rate}
    if voice_file:
        return read_wav(voice_file, sr)
    if cache.exists() and meta_path.exists() and not reuse_voice:
        if json.loads(meta_path.read_text()) == metadata:
            return read_wav(cache, sr)
    if reuse_voice:
        if not cache.is_file():
            raise ValueError("Não há voz salva para reutilizar. Forneça --voz-arquivo fala.wav.")
        return read_wav(cache, sr)
    cache.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        raw = Path(temp) / "voz.wav"
        if sys.platform == "darwin" and shutil.which("say"):
            aiff = Path(temp) / "voz.aiff"
            subprocess.run(["say", "-v", cfg.speech_voice, "-r", str(cfg.speech_rate),
                            "-o", str(aiff), cfg.speech_text], check=True, capture_output=True)
            if not shutil.which("ffmpeg"):
                raise ValueError("Para regenerar a voz no macOS, instale FFmpeg ou use --reutilizar-voz.")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", str(sr),
                            "-ac", "1", "-c:a", "pcm_s16le", str(raw)], check=True, capture_output=True)
        elif shutil.which("espeak-ng") or shutil.which("espeak"):
            engine = shutil.which("espeak-ng") or shutil.which("espeak")
            subprocess.run([engine, "-v", cfg.speech_voice, "-s", str(cfg.speech_rate),
                            "-w", str(raw), cfg.speech_text], check=True, capture_output=True)
        else:
            raise ValueError("Use --reutilizar-voz (já incluída), --voz-arquivo fala.wav, ou instale um sintetizador.")
        voice = read_wav(raw, sr)
    write_wav(cache, voice, sr)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return voice


def bat(sr, rng, sources):
    # Asas de foley e guinchos extraídos de gravação de morcegos.
    wings = respeed(sources["wings"], float(rng.uniform(1.15, 1.45)))
    chirp = respeed(sources["bat"], float(rng.uniform(0.95, 1.06)))
    sound = np.zeros(max(len(wings), len(chirp) + round(sr * 0.12)))
    sound[:len(wings)] += normalize(wings, 0.65)
    offset = round(sr * 0.12)
    sound[offset:offset + len(chirp)] += normalize(chirp, 0.38)
    return fade(sound, sr, attack=0.01, release=0.08)


def cackle(sr, rng, sources):
    # Performance de uma atriz: mantém a respiração e o ritmo irregular reais.
    laugh = respeed(sources["laugh"], float(rng.uniform(0.97, 1.02)))
    return room(fade(normalize(laugh, 0.88), sr), sr, rng, wet=0.12)


def scare(sr, seconds, rng, sources, compression_ratio):
    # Um grito humano irrompe junto de uma porta de madeira batendo.
    track = np.zeros((round(sr * seconds), 2))
    scream = room(stronger_scream(sources["scream"], sr, compression_ratio),
                  sr, rng, wet=0.16, seconds=0.65)
    slam = room(normalize(respeed(sources["slam"], 0.88), 0.85), sr, rng, wet=0.16, seconds=0.55)
    add(track, scream, 0.025, sr, 0.95, -0.08)
    add(track, slam, 0, sr, 0.28, 0.15)
    for channel in range(2):
        track[:, channel] = fade(track[:, channel], sr, attack=0.003, release=min(0.28, seconds / 3))
    return normalize(track, 0.97)


def ambience(sr, seconds, rng, cfg, sources, voice):
    track = np.zeros((round(sr * seconds), 2))
    # Rajadas sobrepostas com variação irregular: sem notas graves sustentadas.
    cursor = 0.0
    while cursor < seconds:
        gust = respeed(sources["wind"], float(rng.uniform(0.75, 1.1)))
        gust = fade(normalize(soften(gust, sr, 1800), 0.24), sr, attack=0.7, release=1.0)
        add(track, gust, cursor, sr, float(rng.uniform(0.65, 0.95)), float(rng.uniform(-0.5, 0.5)))
        cursor += max(0.4, len(gust) / sr * 0.55)
    for start in np.arange(0.8, seconds - 0.5, 4.1):
        add(track, bat(sr, rng, sources), float(start + rng.uniform(0, 0.5)), sr,
            cfg.bats_gain * 0.65, float(rng.uniform(-0.9, 0.9)))
    for start in np.arange(1.6, seconds - 1, 7.3):
        raw = respeed(sources["laugh"], float(rng.uniform(0.94, 1.04)))
        begin = int(rng.uniform(0, max(0, len(raw) - 3.8 * sr)))
        fragment = fade(raw[begin:begin + round(sr * 3.8)], sr, attack=0.12, release=0.35)
        fragment = room(normalize(soften(fragment, sr, 2200), 0.65), sr, rng, wet=0.28)
        add(track, fragment, float(start), sr, cfg.witch_gain * 0.55, float(rng.uniform(-0.75, 0.75)))
    for start in np.arange(5.5, seconds - 0.6, 8.7):
        creak = room(normalize(respeed(sources["creak"], float(rng.uniform(0.8, 1.0))), 0.45),
                     sr, rng, wet=0.2)
        add(track, creak, float(start), sr, 0.40, float(rng.uniform(-0.8, 0.8)))
    for start in (np.arange(10.5, seconds - 2, 13.0) if cfg.audio_mode == "completo" else ()):
        # Sussurro distante com a mesma frase, sem coro afinado ou voz duplicada.
        whisper = voice - soften(voice, sr, 900)
        whisper = room(normalize(whisper, 0.30), sr, rng, wet=0.25)
        add(track, whisper, float(start), sr, cfg.voice_gain * 0.25, -0.65)
    fade_len = min(round(sr * 0.15), len(track) // 2)
    track[:fade_len] *= np.linspace(0, 1, fade_len)[:, None]
    track[-fade_len:] *= np.linspace(1, 0, fade_len)[:, None]
    maximum = float(np.max(np.abs(track)))
    return track * min(1.0, 0.90 / max(maximum, 1e-9)) * cfg.ambience_gain


def background_soundscape(cfg, sources):
    """Vozes distantes e motosserra, para o canal independente de fundo."""
    sr = cfg.audio_sample_rate
    rng = np.random.default_rng(cfg.random_seed + 2)
    track = np.zeros((round(sr * cfg.background_loop_seconds), 2))
    texts = ([text.strip() for text in cfg.background_speech_texts.split("|") if text.strip()]
             if cfg.audio_mode == "completo" else [])
    phrases = []
    for index, text in enumerate(texts):
        threatening = index >= 3
        voice_cfg = replace(cfg, speech_text=text,
                            speech_voice=cfg.background_witch_voice if threatening else cfg.background_help_voice,
                            speech_rate=round(cfg.background_speech_rate * (0.80 if threatening else 1.0)))
        raw = synth_voice(voice_cfg, None, False, cache_stem=f"fontes/fala_fundo_{index + 1:02d}")
        spoken = trim_silence(raw)
        spoken = room(fade(normalize(soften(spoken, sr, 3200), 0.75), sr),
                      sr, rng, wet=0.28, seconds=0.65)
        phrases.append(spoken)
    # Cada fala aparece logo na primeira passagem, depois a ordem é embaralhada.
    order = list(rng.permutation(len(phrases)))
    events = []
    cursor = 0.2
    while cursor < cfg.background_loop_seconds:
        if phrases:
            if not order:
                order = list(rng.permutation(len(phrases)))
            index = order.pop()
            sound = respeed(phrases[index], float(rng.uniform(0.97, 1.03)))
            add(track, sound, cursor, sr, float(rng.uniform(0.60, 0.85)), float(rng.uniform(-0.8, 0.8)))
            events.append({"seconds": round(cursor, 3), "text": texts[index]})
        # Gritos sem palavras entre as falas, com distância e posição variáveis.
        cry = respeed(sources["scream"], float(rng.uniform(0.88, 1.12)))
        cry = room(normalize(soften(cry, sr, 3000), 0.55), sr, rng, wet=0.35, seconds=0.8)
        add(track, cry, cursor + float(rng.uniform(0.6, 1.2)), sr,
            float(rng.uniform(0.35, 0.55)), float(rng.uniform(-0.85, 0.85)))
        cursor += float(rng.uniform(cfg.background_min_interval_seconds, cfg.background_max_interval_seconds))
    # A gravação conserva as acelerações reais do motor.
    cursor = 3.0
    while cursor < cfg.background_loop_seconds:
        length = min(len(sources["chainsaw"]), round(sr * float(rng.uniform(3.0, 5.0))))
        begin = int(rng.integers(0, max(1, len(sources["chainsaw"]) - length + 1)))
        saw = fade(normalize(sources["chainsaw"][begin:begin + length], 0.60), sr, attack=0.35, release=0.65)
        add(track, saw, cursor, sr, cfg.chainsaw_gain, float(rng.uniform(-0.65, 0.65)))
        cursor += float(rng.uniform(6.0, 9.0))
    maximum = float(np.max(np.abs(track)))
    track *= min(1.0, 0.80 / max(maximum, 1e-9))
    edge = min(len(track) // 2, round(sr * 0.08))
    track[:edge] *= np.linspace(0, 1, edge)[:, None]
    track[-edge:] *= np.linspace(1, 0, edge)[:, None]
    return track, events


def generate(cfg, voice_file=None, reuse_voice=False):
    sr = cfg.audio_sample_rate
    rng = np.random.default_rng(cfg.random_seed)
    sources = load_sources(cfg)
    if cfg.audio_mode == "sons_e_boas_vindas" and voice_file is None:
        voice_file = cfg.path(cfg.source_greeting_voice)
        if not voice_file.is_file():
            raise ValueError("Falta o áudio de boas-vindas. Forneça --voz-arquivo com a saudação gravada.")
        greeting_metadata = voice_file.with_suffix(".json")
        if greeting_metadata.is_file():
            expected_text = json.loads(greeting_metadata.read_text()).get("cue")
            if expected_text and expected_text != cfg.speech_text:
                raise ValueError("SPEECH_TEXT difere da gravação de boas-vindas. Gere ou forneça uma nova gravação.")
    raw_voice = synth_voice(cfg, voice_file, reuse_voice)
    voice = fade(normalize(respeed(trim_silence(raw_voice), cfg.voice_pitch), 0.84), sr)
    voice = room(voice, sr, rng, wet=0.10, seconds=0.28)
    laugh = cackle(sr, rng, sources)
    voice_start = 2.0
    laugh_start = voice_start + len(voice) / sr + 0.18
    intro_seconds = laugh_start + len(laugh) / sr
    intro = np.zeros((round(sr * intro_seconds), 2))
    wind = fade(normalize(soften(sources["wind"], sr, 1600), 0.16), sr, attack=0.4, release=1.2)
    add(intro, wind, 0, sr, cfg.ambience_gain, 0)
    for start, pan in [(0.05, -0.8), (0.72, 0.65), (1.30, -0.3)]:
        add(intro, bat(sr, rng, sources), start, sr, cfg.bats_gain, pan)
    add(intro, voice, voice_start, sr, cfg.voice_gain)
    add(intro, laugh, laugh_start, sr, cfg.witch_gain, -0.15)
    maximum = float(np.max(np.abs(intro)))
    intro *= min(1.0, 0.95 / max(maximum, 1e-9))
    shock = scare(sr, cfg.scare_sound_seconds, rng, sources, cfg.scream_compression_ratio) * cfg.scare_gain
    loop = ambience(sr, cfg.ambience_loop_seconds, rng, cfg, sources, voice)
    background, background_events = background_soundscape(cfg, sources)
    opening_seconds = 0.0
    if cfg.opening_scream_gain > 0:
        # Grito já no primeiro instante, com pico forte e sem saturação.
        # Um gerador separado preserva o restante da montagem existente.
        opening_rng = np.random.default_rng(cfg.random_seed + 1)
        scream_source = sources["scream"]
        # Retira a preparação mais baixa da gravação para já abrir no grito.
        strong = np.flatnonzero(np.abs(scream_source) >= np.max(np.abs(scream_source)) * 0.80)
        onset = max(0, int(strong[0]) - round(sr * 0.008))
        opening = room(scream_source[onset:], sr, opening_rng, wet=0.12, seconds=0.40)
        opening = stronger_scream(opening, sr, cfg.scream_compression_ratio) * cfg.opening_scream_gain
        opening = fade(opening, sr, attack=0.003, release=0.12)
        opening_seconds = len(opening) / sr
        intro = np.concatenate([np.column_stack((opening, opening)), intro])
        voice_start += opening_seconds
        laugh_start += opening_seconds
    intro_path, shock_path, loop_path, example_path = [cfg.path(getattr(cfg, field)) for field in
                                                     ("audio_intro", "audio_scare", "audio_ambience", "audio_example")]
    for path, sound in [(intro_path, intro), (shock_path, shock), (loop_path, loop)]:
        write_wav(path, sound, sr)
    background_path = cfg.path(cfg.background_audio)
    write_wav(background_path, background, sr)
    delay = np.zeros((round(sr * cfg.scare_delay_seconds), 2))
    tail_frames = round(sr * cfg.ambience_seconds)
    tail = np.tile(loop, (int(np.ceil(tail_frames / len(loop))), 1))[:tail_frames].copy()
    fade_frames = min(round(sr * cfg.ambience_fade_seconds), len(tail))
    if fade_frames:
        tail[-fade_frames:] *= np.linspace(1, 0, fade_frames)[:, None]
    shock_part = shock * cfg.scare_volume if cfg.scare_enabled else np.zeros((0, 2))
    example = np.concatenate([intro * cfg.intro_volume, delay, shock_part, tail * cfg.ambience_volume]) * cfg.master_volume
    background_mix = np.tile(background, (int(np.ceil(len(example) / len(background))), 1))[:len(example)].copy()
    if fade_frames:
        background_mix[-fade_frames:] *= np.linspace(1, 0, fade_frames)[:, None]
    example += background_mix * cfg.master_volume * cfg.background_screams_volume
    write_wav(example_path, example, sr)
    timeline = {
        "descricao": "Boas-vindas do New Life com gritos sem palavras, gargalhadas, morcegos, vento, madeira e motosserra.",
        "audio_mode": cfg.audio_mode,
        "estilo": "bruxas e casa assombrada; vozes e foley, sem osciladores musicais ou efeitos metálicos",
        "fontes_e_licencas": "audio/FONTES.md",
        "speech_text": cfg.speech_text,
        "speech_source": str(voice_file) if voice_file else "síntese local",
        "sample_rate": sr,
        "intro_seconds": len(intro) / sr,
        "opening_scream_start_seconds": 0.0 if opening_seconds else None,
        "opening_scream_seconds": opening_seconds,
        "scream_compression_ratio": cfg.scream_compression_ratio,
        "speech_start_seconds": voice_start,
        "laugh_start_seconds": laugh_start,
        "silence_seconds": 0 if cfg.background_screams_volume > 0 else cfg.scare_delay_seconds,
        "pre_scare_pause_seconds": cfg.scare_delay_seconds,
        "background_screams_volume": cfg.background_screams_volume,
        "background_speech_texts": ([text.strip() for text in cfg.background_speech_texts.split("|") if text.strip()]
                                    if cfg.audio_mode == "completo" else []),
        "background_events": background_events,
        "scare_start_seconds": (len(intro) + len(delay)) / sr if cfg.scare_enabled else None,
        "ambience_start_seconds": (len(intro) + len(delay) + len(shock_part)) / sr,
        "ambience_seconds": cfg.ambience_seconds,
        "total_seconds": len(example) / sr,
    }
    manifest = example_path.with_suffix(".json")
    manifest.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n")
    for path in (intro_path, shock_path, loop_path, background_path, example_path):
        print(f"Salvo: {path}")
    print(f"Exemplo completo: {len(example) / sr:.2f} segundos.")
    return timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, help="Arquivo .env alternativo.")
    parser.add_argument("--voz-arquivo", type=Path, help="Use sua própria fala em WAV PCM 16 bits.")
    parser.add_argument("--reutilizar-voz", action="store_true", help="Reutiliza voz_original.wav, sem sintetizador.")
    args = parser.parse_args()
    try:
        generate(load_settings(args.env), args.voz_arquivo, args.reutilizar_voz)
        return 0
    except Exception as exc:
        print(f"Não foi possível gerar o áudio: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            print(exc.stderr.decode(errors="replace"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
