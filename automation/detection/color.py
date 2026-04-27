# -*- coding: utf-8 -*-
"""
颜色检测模块 — numpy 实现
"""
import numpy as np


def check_color(image, target, tolerance, mode="contain", sample="center",
                last_image=None, change_threshold=10):
    if mode == "change":
        if last_image is None:
            return {"found": False, "actual_color": "#000000", "diff": 0.0}
        if image.shape != last_image.shape:
            return {"found": True, "actual_color": "#000000", "diff": 999.0}
        diff = np.mean(np.abs(image.astype(float) - last_image.astype(float)))
        found = diff > change_threshold
        mean_color = image.mean(axis=(0, 1))
        actual_hex = "#{:02X}{:02X}{:02X}".format(
            int(mean_color[2]), int(mean_color[1]), int(mean_color[0])
        )
        return {"found": bool(found), "actual_color": actual_hex, "diff": float(diff)}

    if mode == "exact":
        diff_map = np.linalg.norm(
            image.astype(float) - np.array(target, dtype=float), axis=2
        )
        found = bool(np.all(diff_map <= tolerance))
        mean_color = image.mean(axis=(0, 1))
        actual_hex = "#{:02X}{:02X}{:02X}".format(
            int(mean_color[2]), int(mean_color[1]), int(mean_color[0])
        )
        return {"found": found, "actual_color": actual_hex, "diff": float(diff_map.max())}

    if sample == "center":
        h, w = image.shape[:2]
        pixel = image[h // 2, w // 2]
        diff = np.linalg.norm(pixel.astype(float) - np.array(target, dtype=float))
        found = diff <= tolerance
        actual_bgr = pixel
    elif sample == "mean":
        mean_color = image.mean(axis=(0, 1))
        diff = np.linalg.norm(mean_color - np.array(target, dtype=float))
        found = diff <= tolerance
        actual_bgr = mean_color
    elif sample == "max_diff":
        diff_map = np.linalg.norm(
            image.astype(float) - np.array(target, dtype=float), axis=2
        )
        min_idx = np.unravel_index(diff_map.argmin(), diff_map.shape)
        actual_bgr = image[min_idx[0], min_idx[1]]
        diff = diff_map.min()
        found = diff <= tolerance
    else:
        h, w = image.shape[:2]
        pixel = image[h // 2, w // 2]
        diff = np.linalg.norm(pixel.astype(float) - np.array(target, dtype=float))
        found = diff <= tolerance
        actual_bgr = pixel

    actual_hex = "#{:02X}{:02X}{:02X}".format(
        int(actual_bgr[2]), int(actual_bgr[1]), int(actual_bgr[0])
    )
    return {"found": bool(found), "actual_color": actual_hex, "diff": float(diff)}
