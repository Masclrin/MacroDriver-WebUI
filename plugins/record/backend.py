# -*- coding: utf-8 -*-
import logging
import time
from pathlib import Path

_logger = logging.getLogger("plugin.record")


def register():
    return [
        {"action": "record_start", "name": "开始录制"},
        {"action": "record_stop", "name": "停止录制"},
    ]


def execute(action, params, context):
    if action in ("record_start", "start_replay"):
        return _start_record(params, context)
    elif action in ("record_stop", "stop_replay", "save_replay"):
        return _stop_record(params, context)
    return {"ok": False, "error": f"未知动作: {action}"}


def _get_obs_client(params):
    host = params.get("host", "localhost").strip()
    port = int(params.get("port", 4455))
    password = params.get("password", "").strip()

    try:
        import obsws_python as obs
        cl = obs.ReqClient(host=host, port=port, password=password, timeout=5)
        return cl
    except ImportError:
        return None
    except Exception as e:
        _logger.error("[record] OBS连接失败: %s", e)
        return None


def _start_record(params, context):
    host = params.get("host", "localhost").strip()
    port = int(params.get("port", 4455))
    password = params.get("password", "").strip()
    fps = int(params.get("fps", 30))
    record_format = params.get("record_format", "mp4").strip()
    save_dir = params.get("save_dir", "").strip()
    filename = params.get("filename", "record_${timestamp}").strip()
    store_var = params.get("store_var", "record_path")

    try:
        import obsws_python as obs
        cl = obs.ReqClient(host=host, port=port, password=password, timeout=5)

        try:
            if fps and fps > 0:
                cl.set_video_settings(numerator=fps, denominator=1)
        except Exception as e:
            _logger.warning("[record] 设置FPS失败: %s", e)

        if record_format:
            try:
                cl.set_record_settings(rec_format=record_format)
            except Exception as e:
                _logger.warning("[record] 设置录制格式失败: %s", e)

        if save_dir:
            try:
                cl.set_record_directory(record_directory=save_dir)
            except Exception as e:
                _logger.warning("[record] 设置保存目录失败: %s", e)

        try:
            cl.start_replay_buffer()
        except Exception as e:
            _logger.warning("[record] 启动回放缓冲失败(可能已启动): %s", e)

        context.log("info", f"OBS录屏已启动 (FPS:{fps}, 格式:{record_format})")
        _logger.info("[record] OBS录屏已启动")

        return {"ok": True, "set_variables": {"obs_connected": True}, "check_results": {"success": True}}

    except ImportError:
        err = "obsws-python 未安装，请执行: pip install obsws-python"
        context.log("error", err)
        return {"ok": False, "error": err, "check_results": {"success": False}}
    except Exception as e:
        err = f"OBS连接失败: {e}"
        context.log("error", err)
        _logger.error("[record] %s", e)
        return {"ok": False, "error": err, "check_results": {"success": False}}


def _stop_record(params, context):
    host = params.get("host", "localhost").strip()
    port = int(params.get("port", 4455))
    password = params.get("password", "").strip()
    filename = params.get("filename", "record_${timestamp}").strip()
    stop_buffer = params.get("stop_buffer", False)
    store_var = params.get("store_var", "record_path")

    try:
        import obsws_python as obs
        cl = obs.ReqClient(host=host, port=port, password=password, timeout=5)

        try:
            cl.save_replay_buffer()
            context.log("info", "精彩回放已保存")
            _logger.info("[record] 精彩回放已保存")
        except Exception as e:
            _logger.warning("[record] 保存回放缓冲失败: %s", e)

        if stop_buffer:
            try:
                cl.stop_replay_buffer()
                context.log("info", "回放缓冲已停止")
                _logger.info("[record] 回放缓冲已停止")
            except Exception as e:
                _logger.warning("[record] 停止回放缓冲失败: %s", e)

        try:
            resp = cl.get_record_directory()
            save_dir = resp.record_directory if resp else ""
        except Exception:
            save_dir = ""

        if save_dir:
            now = time.localtime()
            timestamp = time.strftime("%Y%m%d_%H%M%S", now)
            fname = filename.replace("${timestamp}", timestamp)
            if not fname.endswith((".mp4", ".mkv", ".flv")):
                fname = fname + ".mp4"
            filepath = str(Path(save_dir) / fname)
        else:
            filepath = ""

        return {"ok": True, "set_variables": {store_var: filepath, "record_saved": True}, "check_results": {"success": True, "filepath": filepath}}

    except ImportError:
        err = "obsws-python 未安装，请执行: pip install obsws-python"
        context.log("error", err)
        return {"ok": False, "error": err, "check_results": {"success": False}}
    except Exception as e:
        err = f"停止录制失败: {e}"
        context.log("error", err)
        _logger.error("[record] %s", e)
        return {"ok": False, "error": err, "check_results": {"success": False}}