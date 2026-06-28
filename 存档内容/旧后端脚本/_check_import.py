import sys
sys.path.insert(0, r"d:\Rin\宏驱动 webui 1.3 - 副本")

try:
    from 宏执行框架3_2 import execute_macro_once
    print("OK: 宏执行框架3_2 import succeeded")
except ImportError as e:
    print(f"FAIL: 宏执行框架3_2 import failed: {e}")

try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("宏执行框架3_2", r"d:\Rin\宏驱动 webui 1.3 - 副本\宏执行框架3.2.py")
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["宏执行框架3_2"] = mod
        spec.loader.exec_module(mod)
        print("OK: Manual load as 宏执行框架3_2 succeeded")
        print(f"  Has execute_macro_once: {hasattr(mod, 'execute_macro_once')}")
        print(f"  Has load_macro_from_file: {hasattr(mod, 'load_macro_from_file')}")
        print(f"  Has compile_macro: {hasattr(mod, 'compile_macro')}")
        print(f"  Has batch_compiled_macro: {hasattr(mod, 'batch_compiled_macro')}")
    else:
        print("FAIL: Could not create spec for 宏执行框架3.2.py")
except Exception as e:
    print(f"FAIL: Manual load error: {e}")
