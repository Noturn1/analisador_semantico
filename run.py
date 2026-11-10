"""
run.py - Atalho para executar o compilador Arjanov a partir da raiz do projeto.

Uso:
    python3 run.py <arquivo-fonte> [opções]

Equivale a `python3 src/main.py <arquivo-fonte> [opções]`.
"""

import runpy
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"

# src/ precisa vir antes da biblioteca padrão: o projeto possui um módulo
# token.py, homônimo do módulo 'token' da stdlib.
sys.path.insert(0, str(SRC))
sys.modules.pop("token", None)

if __name__ == "__main__":
    sys.argv[0] = str(SRC / "main.py")
    runpy.run_path(str(SRC / "main.py"), run_name="__main__")
