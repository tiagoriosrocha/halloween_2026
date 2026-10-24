#!/usr/bin/env python3
"""Execute python main.py --help para ver os modos de uso."""

import argparse
import logging
from pathlib import Path
import sys
import time

from halloween.config import load_settings

LOG = logging.getLogger("halloween")


def arguments():
    parser = argparse.ArgumentParser(description="Webcam de Halloween com detecção de movimento.")
    parser.add_argument("--env", type=Path, help="Arquivo .env alternativo.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--calibrar", action="store_true", help="Mostra movimento e máscara, sem tocar áudio.")
    modes.add_argument("--testar-audio", action="store_true", help="Reproduz um ciclo, sem acessar a câmera.")
    modes.add_argument("--verificar", action="store_true", help="Valida configuração e arquivos, sem câmera ou som.")
    parser.add_argument("--sem-janela", action="store_true", help="Executa sem prévia; encerre com Ctrl+C.")
    return parser.parse_args()


def test_audio(cfg):
    from halloween.audio import PygameMusic, ScareSequence, validate_audio_files
    validate_audio_files(cfg)
    music = PygameMusic(cfg)
    try:
        sequence = ScareSequence(cfg, music)
        sequence.start(time.monotonic())
        while sequence.running:
            sequence.tick(time.monotonic())
            time.sleep(0.02)
    finally:
        music.close()


def run_camera(cfg, args):
    import cv2
    from halloween.audio import PygameMusic, ScareSequence, validate_audio_files
    from halloween.motion import MotionDetector
    from halloween.preview import CameraPreview
    if not args.calibrar:
        validate_audio_files(cfg)
    backends = {"auto": cv2.CAP_ANY, "avfoundation": cv2.CAP_AVFOUNDATION,
                "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "v4l2": cv2.CAP_V4L2}
    capture, music = None, None
    preview = not args.sem_janela and (args.calibrar or cfg.show_preview)
    try:
        capture = cv2.VideoCapture(cfg.camera_index, backends[cfg.camera_backend])
        if not capture.isOpened():
            raise RuntimeError("Não foi possível abrir a webcam. Confira CAMERA_INDEX, feche outros apps "
                               "que usam a câmera e permita o acesso nas configurações do sistema.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)
        capture.set(cv2.CAP_PROP_FPS, cfg.camera_fps)
        LOG.info("Webcam aberta: %.0fx%.0f. Calibração: %s.",
                 capture.get(cv2.CAP_PROP_FRAME_WIDTH), capture.get(cv2.CAP_PROP_FRAME_HEIGHT), args.calibrar)
        sequence = None
        if not args.calibrar:
            music = PygameMusic(cfg)
            sequence = ScareSequence(cfg, music)
        detector = MotionDetector(cfg)
        camera_preview = CameraPreview(cfg, args.calibrar) if preview else None
        failures = 0
        while True:
            started = time.monotonic()
            # O áudio também avança durante falhas temporárias de leitura da câmera.
            if sequence and sequence.running:
                sequence.tick(started)
            ok, frame = capture.read()
            if not ok or frame is None:
                failures += 1
                detector.reset_confirmation()
                if sequence and sequence.state == "rearm":
                    sequence.tick(time.monotonic())
                if failures >= cfg.camera_max_read_failures:
                    raise RuntimeError("A webcam parou de fornecer imagens. Verifique a conexão.")
                time.sleep(1 / cfg.processing_fps)
                continue
            failures = 0
            now = time.monotonic()
            result = detector.process(frame, now)
            if sequence:
                observed_motion = None if result.lighting_change or result.warming_up else result.active
                sequence.tick(now, observed_motion)
                if result.confirmed and sequence.state == "ready":
                    sequence.start(now)
            if preview:
                state = "CALIBRACAO" if sequence is None else sequence.LABELS[sequence.state]
                if result.warming_up:
                    state = "CALIBRANDO FUNDO - AGUARDE"
                elif result.lighting_change:
                    state += " | LUZ GLOBAL IGNORADA"
                key = camera_preview.show(frame, result, state)
                if key == ord("q") or camera_preview.is_closed():
                    break
                if key == ord("f"):
                    camera_preview.set_fullscreen(not camera_preview.fullscreen)
                if key == 27:
                    if camera_preview.fullscreen:
                        camera_preview.set_fullscreen(False)
                    else:
                        break
                if key == ord("r"):
                    detector.reset()
                if key == ord("s") and sequence:
                    sequence.stop(time.monotonic())
            elapsed = time.monotonic() - started
            time.sleep(max(0, 1 / cfg.processing_fps - elapsed))
    finally:
        if capture is not None:
            capture.release()
        if music is not None:
            music.close()
        if preview:
            cv2.destroyAllWindows()


def main():
    args = arguments()
    try:
        cfg = load_settings(args.env)
        logging.basicConfig(level=cfg.log_level, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
        if args.verificar:
            from halloween.audio import validate_audio_files
            for name, seconds in validate_audio_files(cfg).items():
                print(f"OK {name.upper()}: {seconds:.2f} segundos")
            print("Configuração válida. Câmera e saída de som não foram abertas.")
        elif args.testar_audio:
            test_audio(cfg)
        else:
            run_camera(cfg, args)
        return 0
    except KeyboardInterrupt:
        print("\nEncerrado.")
        return 0
    except Exception as exc:
        LOG.error("%s", exc)
        if "cfg" in locals() and cfg.log_level == "DEBUG":
            LOG.exception("Detalhes do erro")
        return 1


if __name__ == "__main__":
    sys.exit(main())
