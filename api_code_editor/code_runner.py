import json
import ast
import re
import sys
import time
import subprocess
import tempfile
import textwrap

try:
    import resource
except ImportError:
    resource = None


BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib",
    "requests", "http", "ftplib", "smtplib", "importlib",
    "ctypes", "multiprocessing", "threading",
}

BLOCKED_PATTERNS = [
    r"__import__\s*\(",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
    r"\bopen\s*\(",
]


def is_safe_code(code):
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, f"Blocked pattern: {pattern}"

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                if name.split(".")[0] in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {name}"

    return True, ""


def run_python_code(code, test_input, time_limit_ms=3000):
    serialized = json.dumps(test_input)

    harness = textwrap.dedent(f"""
import json, sys
{code}

_input = json.loads('''{serialized}''')
_func = None

for _name, _val in list(globals().items()):
    if callable(_val) and not _name.startswith('_'):
        _func = _val
        break

if _func is None:
    print(json.dumps({{"error": "No callable function found", "result": None}}))
    sys.exit(0)

try:
    if isinstance(_input, list):
        _result = _func(*_input)
    elif isinstance(_input, dict):
        _result = _func(**_input)
    else:
        _result = _func(_input)

    print(json.dumps({{"result": _result, "error": None}}))

except Exception as e:
    print(json.dumps({{"result": None, "error": str(e)}}))
""")

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(harness)
        tmp = f.name

    try:
        timeout = min(time_limit_ms / 1000.0, 5.0)
        start = time.perf_counter()

        def set_limits():
            if resource:
                resource.setrlimit(resource.RLIMIT_AS, (128*1024*1024, 128*1024*1024))

        proc = subprocess.run(
            [sys.executable, tmp],
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=set_limits if sys.platform != "win32" else None,
        )

        elapsed = (time.perf_counter() - start) * 1000

        try:
            data = json.loads(proc.stdout.strip())
            data["runtime_ms"] = round(elapsed, 2)
            return data
        except:
            return {"result": proc.stdout.strip(), "error": None, "runtime_ms": elapsed}

    except subprocess.TimeoutExpired:
        return {"result": None, "error": "Timeout", "runtime_ms": time_limit_ms}

    finally:
        import os
        os.unlink(tmp)


def analyse_complexity(code):
    try:
        tree = ast.parse(code)
    except:
        return {"time": "Unknown", "space": "Unknown"}

    loops = sum(isinstance(n, (ast.For, ast.While)) for n in ast.walk(tree))

    if loops == 0:
        time_c = "O(1)"
    elif loops == 1:
        time_c = "O(n)"
    else:
        time_c = "O(n²)"

    space_c = "O(n)" if "list" in code else "O(1)"

    return {"time": time_c, "space": space_c}