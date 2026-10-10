# -*- coding: utf-8 -*-
"""宽松 JSON 解析器（宏文件专用）。

用户手工编辑 .json 宏时经常出现：
  - 结尾多一个逗号：  ["ku","w",0]  ,  ]
  - 元素之间漏写逗号：["kd","w",50]  ["ku","w",0]
  - loop 循环体里的最后一条子动作多/少逗号
  - // 与 /* */ 注释

标准 json.loads 对以上任意一种都会整份报错，导致"宏加载失败"。
本模块提供一个只覆盖 JSON 子集（数组 / 对象 / 字符串 / 数字 / 布尔 / null）
的递归下降解析器，把注释、多余逗号、缺失逗号全部容忍掉。

设计原则：
  - 只做"宽容"，不做"语义猜错"：能解析出的结构尽量与标准 JSON 一致；
  - 不依赖任何项目内模块，可被独立脚本安全导入。
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

__all__ = ["loads_lenient", "load_lenient_file", "LenientJSONError"]

_WS = " \t\r\n"
_DELIM = ",]}"


class LenientJSONError(ValueError):
    """宽松解析仍然无法得到结果时抛出。"""


class _Parser:
    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    # ---------- 基础 ----------
    def _skip(self) -> None:
        """跳过空白与注释（可反复交替）。"""
        while self.i < self.n:
            c = self.s[self.i]
            if c in _WS:
                self.i += 1
                continue
            if self.s.startswith("//", self.i):
                j = self.s.find("\n", self.i)
                self.i = self.n if j < 0 else j + 1
                continue
            if self.s.startswith("/*", self.i):
                j = self.s.find("*/", self.i + 2)
                self.i = self.n if j < 0 else j + 2
                continue
            break

    def _peek(self) -> str:
        return self.s[self.i] if self.i < self.n else ""

    # ---------- 字符串 ----------
    def _parse_string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        out: List[str] = []
        while self.i < self.n:
            ch = self.s[self.i]
            if ch == "\\":
                if self.i + 1 >= self.n:
                    break
                nxt = self.s[self.i + 1]
                if nxt == "u":
                    hex_str = self.s[self.i + 2:self.i + 6]
                    try:
                        out.append(chr(int(hex_str, 16)))
                        self.i += 6
                        continue
                    except ValueError:
                        out.append(nxt)
                        self.i += 2
                        continue
                escapes = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f",
                           '"': '"', "'": "'", "\\": "\\", "/": "/"}
                out.append(escapes.get(nxt, nxt))
                self.i += 2
                continue
            if ch == quote:
                self.i += 1
                break
            out.append(ch)
            self.i += 1
        return "".join(out)

    # ---------- 字面量 ----------
    def _parse_bare(self) -> Any:
        start = self.i
        while self.i < self.n:
            c = self.s[self.i]
            if c in _WS or c in _DELIM:
                break
            if self.s.startswith("//", self.i) or self.s.startswith("/*", self.i):
                break
            self.i += 1
        token = self.s[start:self.i].strip()
        if token == "":
            # 无法前进时强制消费一个字符，避免死循环
            self.i += 1
            return None
        low = token.lower()
        if low == "true":
            return True
        if low == "false":
            return False
        if low in ("null", "none"):
            return None
        # 数字
        try:
            if any(ch in token for ch in ".eE") and low not in ("nan", "inf", "-inf"):
                return float(token)
            return int(token)
        except ValueError:
            pass
        try:
            return float(token)
        except ValueError:
            return token  # 宽容：无法识别的裸词按字符串处理

    # ---------- 数组 ----------
    def _parse_array(self) -> List[Any]:
        self.i += 1  # 吃掉 '['
        out: List[Any] = []
        while True:
            self._skip()
            if self.i >= self.n:
                break  # 容错：未闭合
            c = self.s[self.i]
            if c == "]":
                self.i += 1
                break
            if c == ",":
                self.i += 1  # 多余逗号
                continue
            out.append(self._parse_value())
            self._skip()
            if self._peek() == ",":
                self.i += 1
            # 没有逗号也继续（缺失逗号容忍）
        return out

    # ---------- 对象 ----------
    def _parse_object(self) -> dict:
        self.i += 1  # 吃掉 '{'
        out: dict = {}
        while True:
            self._skip()
            if self.i >= self.n:
                break
            c = self.s[self.i]
            if c == "}":
                self.i += 1
                break
            if c == ",":
                self.i += 1
                continue
            key: Any
            if self._peek() in ('"', "'"):
                key = self._parse_string()
            else:
                key = self._parse_bare()
            self._skip()
            if self._peek() == ":":
                self.i += 1
                self._skip()
                out[str(key)] = self._parse_value()
            else:
                # 缺冒号：宽容地把 key 当字符串值写入
                out[str(key)] = None
            self._skip()
            if self._peek() == ",":
                self.i += 1
        return out

    # ---------- 入口 ----------
    def _parse_value(self) -> Any:
        self._skip()
        c = self._peek()
        if c == "[":
            return self._parse_array()
        if c == "{":
            return self._parse_object()
        if c in ('"', "'"):
            return self._parse_string()
        return self._parse_bare()

    def parse(self) -> Any:
        # 定位到第一个有效结构起点（跳过前导注释/空白/BOM）
        if self.s.startswith("\ufeff"):
            self.i = 1
        self._skip()
        value = self._parse_value()
        return value


def loads_lenient(text: str) -> Any:
    """容忍注释 / 多余逗号 / 缺失逗号的 JSON 解析。

    若严格 json.loads 就能解析，优先用严格的（更快、语义最准）；
    否则回退到宽松解析器。
    """
    if text is None:
        return None
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8", errors="replace")

    # 快速路径：标准 JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    parser = _Parser(text)
    return parser.parse()


def load_lenient_file(path, encoding: str = "utf-8") -> Any:
    with open(path, "r", encoding=encoding) as f:
        return loads_lenient(f.read())
