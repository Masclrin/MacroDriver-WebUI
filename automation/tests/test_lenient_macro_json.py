# -*- coding: utf-8 -*-
"""宽松 JSON / 宏 IO 逗号兼容回归测试。

覆盖用户反馈：手工编辑 .json 宏时，动作结尾"多一个逗号"或"少一个逗号"
（含宏末尾动作、loop 内最后一条子动作）导致整份宏加载失败。

运行： python -m automation.tests.test_lenient_macro_json
"""
import sys
import tempfile
from pathlib import Path

from lenient_json import loads_lenient

_MESSY = '''[
    // 起手
    ["kd","shift",50]
    ["ku","shift",430],
    ["loop", 2, [
        ["kd","w","2f"],
        ["ku","w",0],
    ]],
    /* 收尾 */ ["md","right",20],
    ["mu","right",20],
]'''


def test_lenient_tolerates_comma_problems():
    """多余逗号 / 缺失逗号 / 注释都应被容忍。"""
    cases = {
        "结尾多逗号": '[\n ["kd","w",50],\n ["ku","w",0],\n]',
        "元素间少逗号": '[\n ["kd","w",50]\n ["ku","w",0]\n]',
        "loop内结尾多逗号": '[\n ["loop",3,[\n  ["kd","w",50],\n ]],\n]',
        "loop内少逗号": '[\n ["loop",3,[\n  ["kd","w",50]\n  ["ku","w",0]\n ]]\n]',
        "含注释": '[\n // 注释\n ["wait",10], /* 内联 */ ["wait",20]\n]',
    }
    for name, text in cases.items():
        v = loads_lenient(text)
        assert isinstance(v, list) and len(v) >= 1, f"{name} 解析结果异常: {v!r}"
        print(f"  OK {name}: {v}")


def test_lenient_matches_strict_json_on_valid_input():
    """合法 JSON 必须得到与标准解析完全一致的结果（不能改变既有语义）。"""
    import json
    for text in ('[["kd","w",50],["ku","w",0]]', '["loop",2,[["wait",1]]]'):
        assert loads_lenient(text) == json.loads(text)
    print("  OK 合法 JSON 结果与标准解析一致")


def test_macro_io_reads_and_round_trips_messy_file():
    """编辑器读取路径：注释保留为 note 行，动作全部识别，回写后能再读回。"""
    from macro_io.parser import load_macro_rows_with_notes, save_macro_rows_with_notes

    tmp = Path(tempfile.mkdtemp()) / "messy.json"
    tmp.write_text(_MESSY, encoding="utf-8")

    rows = load_macro_rows_with_notes(tmp)
    assert ["kd", "shift", 50] in rows, f"缺少第一条动作: {rows}"
    assert ["mu", "right", 20] in rows, f"缺少最后一条动作: {rows}"
    loops = [r for r in rows if r and r[0] == "loop"]
    assert loops and loops[0][2] == [["kd", "w", "2f"], ["ku", "w", 0]], f"loop 内容错误: {loops}"
    notes = [r for r in rows if r and r[0] == "note"]
    assert "起手" in [n[1] for n in notes], f"注释未保留为 note: {notes}"
    print(f"  读取 rows={rows}")

    out = Path(tempfile.mkdtemp()) / "out.json"
    save_macro_rows_with_notes(out, rows)
    rows2 = load_macro_rows_with_notes(out)
    assert rows2 == rows, f"回写后读取结果不一致\n{rows}\n{rows2}"
    print("  OK 回写 round-trip 一致")


def test_simplify_tool_loads_messy_file():
    """化简/合并工具同样要能读入带逗号问题的宏。"""
    from recorder.simplify_tool import load_macro
    tmp = Path(tempfile.mkdtemp()) / "messy.json"
    tmp.write_text(_MESSY, encoding="utf-8")
    data = load_macro(str(tmp))
    assert isinstance(data, list) and len(data) == 5, f"化简工具读取异常: {data}"
    print(f"  OK simplify load={data}")


def test_macro_converter_load_json_with_comments():
    """导入/导出使用 _load_json_with_comments，也要容忍逗号问题。"""
    from macro_converter import _load_json_with_comments
    tmp = Path(tempfile.mkdtemp()) / "messy.json"
    tmp.write_text(_MESSY, encoding="utf-8")
    parsed = _load_json_with_comments(tmp)
    assert isinstance(parsed, list) and len(parsed) == 5, f"转换器读取异常: {parsed}"
    print(f"  OK converter load={parsed}")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            print(f"[RUN] {name}")
            try:
                fn()
                print("  PASS\n")
            except AssertionError as e:
                failed += 1
                print(f"  FAIL: {e}\n")
            except Exception as e:
                failed += 1
                import traceback
                traceback.print_exc()
                print(f"  ERROR: {e}\n")
    print("全部通过" if failed == 0 else f"{failed} 项失败")
    sys.exit(1 if failed else 0)
