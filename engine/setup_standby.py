# -*- coding: utf-8 -*-
"""
_standby_engine C 扩展构建脚本。

用法:
    python engine/setup_standby.py build_ext --inplace

需要:
    - Visual Studio Build Tools 2022 (使用 C++ 的桌面开发工作负载)
    - Python 开发头文件 (CPython 安装时已自带)
"""
from setuptools import setup, Extension

module = Extension(
    '_standby_engine',
    sources=['engine/standby_engine.c'],
    libraries=['user32'],           # SendInput / SetCursorPos / MapVirtualKeyA
    # interception.dll 运行时 LoadLibrary, 不需要链接
    extra_compile_args=[
        '/O2',          # 最大优化
        '/GL',          # 全程序优化
        '/GS-',         # 关闭缓冲区安全检查 (减少开销, standby 线程无外部输入)
        '/arch:AVX2',   # 启用 AVX2 (含 _mm_pause)
        '/utf-8',       # 源文件 UTF-8 编码 (含中文注释)
    ],
    extra_link_args=['/LTCG'],      # 链接时代码生成 (配合 /GL)
)

setup(
    name='_standby_engine',
    version='1.0.0',
    description='Industrial-grade precision standby engine for macro execution',
    ext_modules=[module],
)
