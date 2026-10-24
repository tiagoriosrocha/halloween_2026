"""Prévia em cores na resolução capturada, com proporções preservadas."""

import cv2
import numpy as np

WINDOW = "Halloween - webcam"


def fit_image(image, width, height):
    """Preenche a tela com margens quando necessário, sem deformar a cena."""
    if width <= 0 or height <= 0:
        return image
    source_height, source_width = image.shape[:2]
    scale = min(width / source_width, height / source_height)
    target_width = max(1, min(width, round(source_width * scale)))
    target_height = max(1, min(height, round(source_height * scale)))
    resized = cv2.resize(image, (target_width, target_height),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    canvas = np.zeros((height, width, 3), dtype=image.dtype)
    x, y = (width - target_width) // 2, (height - target_height) // 2
    canvas[y:y + target_height, x:x + target_width] = resized
    return canvas


def camera_image(frame, result, cfg, calibrating, state):
    # A redução e o cinza usados pelo detector não são usados como prévia.
    image = frame.copy()
    overlay = cfg.show_detection_overlay or calibrating
    color = (40, 50, 255) if result.confirmed else (70, 210, 60)
    if overlay:
        height, width = image.shape[:2]
        detector_height, detector_width = result.frame.shape[:2]
        sx, sy = width / detector_width, height / detector_height
        x, y, w, h = result.roi
        cv2.rectangle(image, (round(x * sx), round(y * sy)),
                      (round((x + w) * sx) - 1, round((y + h) * sy) - 1), (210, 130, 30), 1)
        for bx, by, bw, bh in result.boxes:
            cv2.rectangle(image, (round((x + bx) * sx), round((y + by) * sy)),
                          (round((x + bx + bw) * sx), round((y + by + bh) * sy)), color, 2)
    if cfg.mirror_preview:
        image = cv2.flip(image, 1)
    if overlay:
        cv2.putText(image, state, (12, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        cv2.putText(image, f"Movimento: {result.ratio:.1%} | F tela cheia | Q sair | R fundo | S parar som",
                    (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
    if cfg.show_mask or calibrating:
        # Máscara em um painel da mesma janela, para manter a câmera em tela cheia.
        height, width = image.shape[:2]
        panel_width = max(1, width // 4)
        panel_height = max(1, height // 4)
        mask = cv2.cvtColor(result.mask, cv2.COLOR_GRAY2BGR)
        if cfg.mirror_preview:
            mask = cv2.flip(mask, 1)
        panel = fit_image(mask, panel_width, panel_height)
        image[height - panel_height:, width - panel_width:] = panel
    return image


class CameraPreview:
    def __init__(self, cfg, calibrating):
        self.cfg, self.calibrating = cfg, calibrating
        self.fullscreen = cfg.preview_fullscreen
        self.native_size_set = False
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        cv2.resizeWindow(WINDOW, cfg.camera_width, cfg.camera_height)
        self.set_fullscreen(self.fullscreen)

    def set_fullscreen(self, enabled):
        self.fullscreen = enabled
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN if enabled else cv2.WINDOW_NORMAL)

    def show(self, frame, result, state):
        if not self.native_size_set:
            # Usa a resolução realmente entregue pela câmera, que pode diferir da solicitada.
            if not self.fullscreen:
                cv2.resizeWindow(WINDOW, frame.shape[1], frame.shape[0])
            self.native_size_set = True
        image = camera_image(frame, result, self.cfg, self.calibrating, state)
        try:
            _, _, width, height = cv2.getWindowImageRect(WINDOW)
        except cv2.error:
            width, height = image.shape[1], image.shape[0]
        cv2.imshow(WINDOW, fit_image(image, width, height))
        return cv2.waitKey(1) & 0xFF

    def is_closed(self):
        return cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
