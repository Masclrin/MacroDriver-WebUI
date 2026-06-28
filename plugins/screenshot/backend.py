# -*- coding: utf-8 -*-
import base64
import io
import logging
import os
import time
from pathlib import Path

_logger = logging.getLogger("plugin.screenshot")


def register():
    return [
        {"action": "capture", "name": "截图保存"},
        {"action": "ocr", "name": "截图OCR"},
    ]


def execute(action, params, context):
    if action in ("capture", "screenshot_capture"):
        return _capture(params, context)
    elif action in ("ocr", "screenshot_ocr"):
        return _ocr(params, context)
    return {"ok": False, "error": f"未知动作: {action}"}


def _resolve_hwnd(hwnd_var):
    if not hwnd_var:
        return None
    try:
        return int(hwnd_var)
    except (ValueError, TypeError):
        pass
    return None


def _capture_region(mode, capture_mode, rect, hwnd_var, context=None):
    """截图区域获取 - 优先使用context.capture_screen（支持DXGI），回退到mss"""
    from engine.coordinate import resolve_region, get_window_client_rect

    hwnd = _resolve_hwnd(hwnd_var)

    # 优先使用context提供的截图接口（可自动使用DXGI）
    def _do_capture(region):
        if context and hasattr(context, 'capture_screen'):
            return context.capture_screen(region)
        # 回退到原始capture_screen
        from automation.detection.capture import capture_screen
        return capture_screen(region)

    if capture_mode == "fullscreen":
        if mode == "window" and hwnd:
            try:
                cx, cy, cw, ch = get_window_client_rect(hwnd)
                region = (cx, cy, cw, ch)
                return _do_capture(region)
            except Exception:
                pass
        return _do_capture(None)

    elif capture_mode == "region":
        if not rect or len(rect) < 4:
            return _do_capture(None)
        region = resolve_region(mode, rect, hwnd)
        return _do_capture(region)

    elif capture_mode == "window":
        if hwnd:
            try:
                cx, cy, cw, ch = get_window_client_rect(hwnd)
                region = (cx, cy, cw, ch)
                return _do_capture(region)
            except Exception:
                pass
        return _do_capture(None)

    return _do_capture(None)


def _generate_filename(filename_template, ext, save_dir):
    now = time.localtime()
    timestamp = time.strftime("%Y%m%d_%H%M%S", now)
    date_str = time.strftime("%Y%m%d", now)

    if not filename_template:
        filename_template = "screenshot_${timestamp}"

    name = filename_template
    name = name.replace("${timestamp}", timestamp)
    name = name.replace("${date}", date_str)
    name = name.replace("${time}", time.strftime("%H%M%S", now))

    if not name.endswith("." + ext):
        name = name + "." + ext

    if save_dir:
        save_path = Path(save_dir)
    else:
        save_path = Path(os.environ.get("TEMP", ".")) / "宏驱动_截图"

    save_path.mkdir(parents=True, exist_ok=True)

    final_path = save_path / name
    counter = 1
    while final_path.exists():
        stem = Path(name).stem
        final_path = save_path / f"{stem}_{counter}.{ext}"
        counter += 1

    return str(final_path)


def _save_image(img, filepath, fmt="png", quality=95):
    import cv2
    import numpy as np
    encode_params = []
    if fmt == "jpg":
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, max(1, min(100, int(quality)))]
    elif fmt == "png":
        encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    try:
        ext_code = ".jpg" if fmt == "jpg" else (".bmp" if fmt == "bmp" else ".png")
        success, buf = cv2.imencode(ext_code, img, encode_params)
        if success and buf is not None:
            with open(filepath, "wb") as f:
                f.write(buf.tobytes())
            return True
        return False
    except Exception as e:
        _logger.error("[screenshot] 保存图片失败: %s", e)
        return False


def _capture(params, context):
    mode = params.get("mode", "screen")
    capture_mode = params.get("capture_mode", "fullscreen")
    rect = params.get("rect", [0, 0, 0, 0])
    hwnd_var = params.get("hwnd_var", "")
    save_dir = params.get("save_dir", "").strip()
    filename = params.get("filename", "screenshot_${timestamp}")
    fmt = params.get("format", "png")
    quality = int(params.get("quality", 95))
    store_var = params.get("store_var", "screenshot_path")

    try:
        img = _capture_region(mode, capture_mode, rect, hwnd_var, context)
        if img is None:
            return {"ok": False, "error": "截图失败：无法获取图像"}

        filepath = _generate_filename(filename, fmt, save_dir)
        success = _save_image(img, filepath, fmt, quality)

        if not success:
            return {"ok": False, "error": f"截图保存失败: {filepath}"}

        context.log("info", f"截图已保存: {filepath}")

        result = {
            "ok": True,
            "data": {
                "filepath": filepath,
                "filename": os.path.basename(filepath),
                "width": img.shape[1],
                "height": img.shape[0],
            },
            "set_variables": {store_var: filepath},
        }
        return result

    except Exception as e:
        _logger.error("[screenshot] 截图失败: %s", e)
        return {"ok": False, "error": f"截图失败: {e}"}


def _ocr(params, context):
    mode = params.get("mode", "screen")
    capture_mode = params.get("capture_mode", "region")
    rect = params.get("rect", [0, 0, 200, 50])
    hwnd_var = params.get("hwnd_var", "")
    engine = params.get("engine", "rapidocr")
    save_screenshot = params.get("save_screenshot", False)
    save_dir = params.get("save_dir", "").strip()
    filename = params.get("filename", "ocr_${timestamp}")
    store_text_var = params.get("store_text_var", "ocr_text")
    store_path_var = params.get("store_path_var", "screenshot_path")

    try:
        img = _capture_region(mode, capture_mode, rect, hwnd_var, context)
        if img is None:
            return {"ok": False, "error": "截图失败：无法获取图像"}

        text = ""
        confidence = 0.0

        try:
            from automation.detection.ocr import OCREngine
            ocr_engine = OCREngine()
            result = ocr_engine.detect(img, match_text="", match_mode="contain")
            text = result.get("text", "")
            confidence = result.get("confidence", 0.0)
        except Exception as e:
            _logger.warning("[screenshot] OCR识别失败: %s", e)
            return {"ok": False, "error": f"OCR识别失败: {e}"}

        filepath = ""
        set_vars = {store_text_var: text}

        if save_screenshot:
            filepath = _generate_filename(filename, "png", save_dir)
            _save_image(img, filepath, "png", 95)
            set_vars[store_path_var] = filepath
            context.log("info", f"OCR截图已保存: {filepath}")

        context.log("info", f"OCR识别结果: {text[:100]}")

        result = {
            "ok": True,
            "data": {
                "text": text,
                "confidence": confidence,
                "filepath": filepath,
            },
            "set_variables": set_vars,
        }
        return result

    except Exception as e:
        _logger.error("[screenshot] OCR失败: %s", e)
        return {"ok": False, "error": f"OCR失败: {e}"}
