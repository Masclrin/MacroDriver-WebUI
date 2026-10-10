# -*- coding: utf-8 -*-
"""附加宏指令(ext) + 未识别行"原文保留" 回归测试。

覆盖：
- macro_io.parser 不再丢弃无法解析 / 未识别的行：保留 {"__raw": ...}，保存往返一致；
- compile_macro 的 ext 命名空间：已注册即执行、未注册告警并跳过、**ext 延时恒为 0**
  （不参与随机延迟修正与误差补偿，因此不会位移 kd/ku 等核心动作的时间线）。

运行： python -m automation.tests.test_ext_and_raw_rows
"""
import importlib.util
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load_framework():
    """以 importlib 加载 宏执行框架3.2.py（文件名含点号与非 ASCII，无法常规 import）。"""
    p = _ROOT / "宏执行框架3.2.py"
    spec = importlib.util.spec_from_file_location("macro_framework_ext_test", str(p))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["macro_framework_ext_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parser_preserves_raw_rows():
    from macro_io.parser import load_macro_rows_with_notes, save_macro_rows_with_notes

    src = (
        "[\n"
        '  ["kd","w",50],\n'
        "  这不是合法JSON @@,\n"
        '  ["ext","fps.lock",30],\n'
        '  ["ku","w",0]\n'
        "]\n"
    )
    p = Path(tempfile.gettempdir()) / "_macro_raw_regress.json"
    p.write_text(src, encoding="utf-8")

    rows = load_macro_rows_with_notes(p)
    assert any(isinstance(r, dict) and "__raw" in r for r in rows), f"原文行未保留: {rows!r}"

    save_macro_rows_with_notes(p, rows)
    rows2 = load_macro_rows_with_notes(p)
    assert any(isinstance(r, dict) and "__raw" in r for r in rows2), f"保存后原文行丢失: {rows2!r}"
    assert any(isinstance(r, list) and r and r[0] == "ext" for r in rows2), "ext 行丢失"
    print("  OK parser 原文行保留 + 保存往返一致")


def test_ext_registry_and_no_timeline_shift():
    m = _load_framework()
    calls = []
    m.register_ext_handler("test.fps_lock", lambda args: calls.append(args))
    try:
        compiled = m.compile_macro([
            ["kd", "w", 50],
            ["ext", "test.fps_lock", 30],
            ["ext", "test.not_registered", "weak"],
            ["bogus_cmd", 1, 2],
            ["ku", "w", 0],
        ])
        kinds = [c[2] for c in compiled]
        assert kinds == ["kd", "ext", "ext", "ku"], kinds

        compiled[1][0]()  # 执行已注册的 ext
        assert calls == [[30]], calls

        # ext 延时恒为 0：不位移核心动作时间线
        assert compiled[1][1] == 0.0 and compiled[2][1] == 0.0
        # 未注册 → 保留为一步、无副作用、handled=False
        assert compiled[2][4]["handled"] is False and compiled[2][0] is None
    finally:
        m.unregister_ext_handler("test.fps_lock")
    print("  OK ext 注册执行 / 未注册跳过 / 零延时不影响时间线")


def main():
    test_parser_preserves_raw_rows()
    test_ext_registry_and_no_timeline_shift()
    print("全部通过")


if __name__ == "__main__":
    main()
