# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import importlib
import os
import platform
import subprocess
import sys
import traceback
from pathlib import Path


_PIP_IMPORT_MAP = {
    "pywebview": "webview",
    "opencv-python": "cv2",
    "rapidocr_onnxruntime": "rapidocr_onnxruntime",
    "pynput": "pynput",
    "psutil": "psutil",
    "mss": "mss",
    "numpy": "numpy",
}


class ExtraApiMixin:

    # ── 环境检查 ──────────────────────────────────────────────

    def check_environment(self):
        results = {
            "python": self._check_python(),
            "system": self._check_system(),
            "interception_dll": self._check_interception_dll(),
            "interception_driver": self._check_interception_driver(),
            "packages": self._check_packages(),
            "dxgi": self._check_dxgi(),
        }
        all_ok = all(v.get("ok", True) for v in results.values())
        return self._ok(results=results, all_ok=all_ok)

    def _check_python(self):
        info = {
            "version": sys.version,
            "executable": sys.executable,
            "ok": True,
        }
        py_ver = sys.version_info
        if py_ver < (3, 8):
            info["ok"] = False
            info["warning"] = "Python < 3.8，建议升级到 3.10+"
        return info

    def _check_system(self):
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() if sys.platform == "win32" else False
        except Exception:
            is_admin = False
        return {
            "os": platform.platform(),
            "arch": platform.architecture()[0],
            "machine": platform.machine(),
            "is_admin": bool(is_admin),
            "ok": True,
        }

    def _check_interception_dll(self):
        try:
            from engine.input_interception import _resolve_dll_path
            dll_path = _resolve_dll_path()
            if dll_path and os.path.exists(dll_path):
                return {"ok": True, "path": dll_path, "exists": True}
            project_root = str(Path(__file__).parent.parent)
            arch_dir = "x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "x86"
            expected = os.path.join(project_root, "Interception", "library", arch_dir, "interception.dll")
            return {"ok": False, "path": expected, "exists": False, "warning": "interception.dll 未找到"}
        except Exception:
            return {"ok": False, "path": None, "exists": False, "warning": traceback.format_exc()}

    def _check_interception_driver(self):
        try:
            from engine.input_interception import _load_interception_dll
            try:
                dll = _load_interception_dll()
            except OSError as e:
                return {"ok": False, "loaded": False, "warning": f"DLL 加载失败: {e}"}

            dll.interception_create_context.restype = ctypes.c_void_p
            dll.interception_destroy_context.argtypes = [ctypes.c_void_p]
            dll.interception_destroy_context.restype = None
            ctx_ptr = dll.interception_create_context()
            if ctx_ptr:
                dll.interception_destroy_context(ctx_ptr)
                return {"ok": True, "loaded": True, "keyboard_devices": -1, "mouse_devices": -1}
            return {"ok": False, "loaded": False, "warning": "interception_create_context 返回空，驱动可能未安装"}
        except Exception as e:
            return {"ok": False, "loaded": False, "warning": str(e)}

    def _check_packages(self):
        req_path = Path(__file__).parent.parent / "bin" / "requirements.txt"
        missing = []
        installed = []
        if req_path.exists():
            try:
                content = req_path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split(">")[0].split("<")[0].strip()
                    if not pkg:
                        continue
                    import_name = _PIP_IMPORT_MAP.get(pkg, pkg.replace("-", "_"))
                    try:
                        importlib.import_module(import_name)
                        installed.append(pkg)
                    except ImportError:
                        missing.append(pkg)
            except Exception:
                pass
        return {
            "ok": len(missing) == 0,
            "installed": installed,
            "missing": missing,
        }

    def _check_dxgi(self):
        try:
            from automation.detection.dxgi_capture import DXGICapture
            cap = DXGICapture()
            success = cap.initialize()
            if success:
                cap.stop_background()
                return {"ok": True, "available": True}
            return {"ok": True, "available": False, "warning": "DXGI 初始化失败（可能缺少显卡驱动支持）"}
        except ImportError:
            return {"ok": True, "available": False, "warning": "DXGI 模块未找到"}
        except Exception as e:
            return {"ok": True, "available": False, "warning": str(e)}

    # ── 系统信息 ──────────────────────────────────────────────

    def get_system_info(self):
        monitors = []
        try:
            import screeninfo
            for m in screeninfo.get_monitors():
                monitors.append({"name": m.name, "width": m.width, "height": m.height, "is_primary": m.is_primary})
        except Exception:
            pass

        from core.paths import BASE_DIR
        return self._ok(
            os=platform.platform(),
            python=sys.version,
            executable=sys.executable,
            arch=platform.architecture()[0],
            monitors=monitors,
            app_dir=str(BASE_DIR),
        )

    # ── Interception 驱动管理 ─────────────────────────────────

    def install_interception_driver(self):
        bat_path = Path(__file__).parent.parent / "bin" / "安装驱动_管理员运行_l.bat"
        if not bat_path.exists():
            return self._fail("驱动安装脚本不存在")
        return self._run_bat_as_admin(bat_path, "安装 Interception 驱动")

    def uninstall_interception_driver(self):
        bat_path = Path(__file__).parent.parent / "bin" / "重置Interception驱动.bat"
        if not bat_path.exists():
            return self._fail("驱动卸载脚本不存在")
        return self._run_bat_as_admin(bat_path, "卸载 Interception 驱动")

    def _run_bat_as_admin(self, bat_path, action_name):
        try:
            bat_path = Path(bat_path).resolve()
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "cmd.exe", f'/c "{bat_path}"', str(bat_path.parent), 1
            )
            return self._ok(started=True, message=f"已请求{action_name}，请在弹出的管理员窗口确认")
        except Exception as e:
            return self._fail(f"{action_name}失败", str(e))

    # ── 管理员重启 ────────────────────────────────────────────

    def restart_as_admin(self):
        try:
            if ctypes.windll.shell32.IsUserAnAdmin():
                return self._ok(message="当前已是管理员权限", already_admin=True)
            script = sys.argv[0]
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script}"', str(Path(script).parent), 1
            )
            return self._ok(restarting=True, message="已请求管理员重启，当前窗口即将关闭")
        except Exception as e:
            return self._fail("管理员重启失败", str(e))

    # ── 功能说明 ──────────────────────────────────────────────

    def get_feature_list(self):
        features = [
            {"name": "宏执行绑定", "icon": "fa-solid fa-play", "desc": "绑定热键触发宏执行，支持多宏并行、重复执行、按键模式"},
            {"name": "录制与化简", "icon": "fa-solid fa-record-vinyl", "desc": "实时录制键盘鼠标操作并自动精简冗余动作"},
            {"name": "宏编辑保存", "icon": "fa-solid fa-pen-to-square", "desc": "手动编辑宏动作列表，支持插入、删除、调整顺序"},
            {"name": "全局参数", "icon": "fa-solid fa-sliders", "desc": "配置所有模块参数，支持导入导出"},
            {"name": "全局控制台", "icon": "fa-solid fa-terminal", "desc": "实时查看系统运行日志"},
            {"name": "自动化编辑器", "icon": "fa-solid fa-diagram-project", "desc": "可视化搭建自动化流程，支持插件扩展"},
            {"name": "精度/占用档位", "icon": "fa-solid fa-gauge-high", "desc": "在「全局参数→执行框架」一键切换 延迟优先/均衡/低占用/自定义，联动 15 项精度与 CPU 参数；顶栏常显当前档位与 Standby 引擎加载状态"},
            {"name": "热键冲突检测", "icon": "fa-solid fa-keyboard", "desc": "「全局参数」页一键检测所有全局快捷键是否互相冲突；「额外功能→快捷键速查」按真实配置展示并标注冲突项"},
            {"name": "额外功能", "icon": "fa-solid fa-toolbox", "desc": "环境检查、驱动管理、系统信息等工具"},
        ]
        return self._ok(features=features)

    # ── 依赖安装 ──────────────────────────────────────────────

    def install_missing_packages(self):
        req_path = Path(__file__).parent.parent / "bin" / "requirements.txt"
        if not req_path.exists():
            return self._fail("requirements.txt 不存在")

        try:
            content = req_path.read_text(encoding="utf-8")
            to_install = []
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split(">")[0].split("<")[0].strip()
                if not pkg:
                    continue
                import_name = _PIP_IMPORT_MAP.get(pkg, pkg.replace("-", "_"))
                try:
                    importlib.import_module(import_name)
                except ImportError:
                    to_install.append(line)

            if not to_install:
                return self._ok(message="所有依赖已安装，无需额外安装", installed_count=0)

            pip_args = [sys.executable, "-m", "pip", "install"] + to_install
            proc = subprocess.run(
                pip_args,
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode == 0:
                return self._ok(
                    message=f"已安装 {len(to_install)} 个缺失依赖",
                    output=output,
                    installed_count=len(to_install),
                )
            return self._fail(f"安装部分依赖失败 (exit={proc.returncode})", output)
        except subprocess.TimeoutExpired:
            return self._fail("安装超时（5分钟），请手动运行 pip install")
        except Exception as e:
            return self._fail("安装依赖失败", str(e))

    def install_dependencies(self):
        bat_path = Path(__file__).parent.parent / "bin" / "安装依赖_l.bat"
        if not bat_path.exists():
            return self._fail("依赖安装脚本不存在")
        return self._run_bat_as_admin(bat_path, "安装依赖")

    def install_all(self):
        bat_path = Path(__file__).parent.parent / "bin" / "1_管理员安装全部并启动WebUI.bat"
        if not bat_path.exists():
            return self._fail("一键安装脚本不存在")
        return self._run_bat_as_admin(bat_path, "一键安装全部")