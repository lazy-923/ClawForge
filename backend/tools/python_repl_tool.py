from __future__ import annotations

from io import StringIO
from contextlib import redirect_stdout


def run_python(code: str) -> str:
    stdout = StringIO()
    namespace: dict[str, object] = {}
    with redirect_stdout(stdout):
        exec(code, {"__builtins__": __builtins__}, namespace)
    output = stdout.getvalue().strip()
    return output or "Python code executed."

