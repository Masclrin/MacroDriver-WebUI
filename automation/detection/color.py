# -*- coding: utf-8 -*-
import numpy as np
import cv2


def check_color(image, target, tolerance, mode="contain", sample="center",
                last_image=None, change_threshold=10, area_ratio_threshold=0.5):
    if mode == "area":
        b, g, r = int(target[0]), int(target[1]), int(target[2])
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)], dtype=np.uint8)
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)], dtype=np.uint8)
        mask = cv2.inRange(image, lower, upper)
        matching = cv2.countNonZero(mask)
        total_pixels = image.shape[0] * image.shape[1]
        ratio = matching / total_pixels if total_pixels > 0 else 0.0
        found = ratio >= area_ratio_threshold
        if matching > 0:
            mean_color = cv2.mean(image, mask)[:3]
            actual_hex = "#{:02X}{:02X}{:02X}".format(
                int(mean_color[2]), int(mean_color[1]), int(mean_color[0])
            )
        else:
            actual_hex = "#{:02X}{:02X}{:02X}".format(r, g, b)
        return {"found": bool(found), "actual_color": actual_hex, "diff": float(ratio)}

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
