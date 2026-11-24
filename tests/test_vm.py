"""
Executa o TAC gerado num porte da Berti VM (tests/berti_vm.py), a máquina
virtual da avaliação (docs/DECISOES.md #30 a #34). O resultado esperado sai da
semântica da linguagem, não da saída do compilador.

Executar a partir da raiz do projeto:
    python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

from berti_vm import executar  # noqa: E402
from test_tac import tac_de  # noqa: E402


def roda(codigo: str, *entradas: str) -> list[str]:
    return executar(tac_de(codigo), entradas)


def main_com(corpo: str) -> str:
    return "func main(): int {" + corpo + " return 0; }"


class TestExecucao(unittest.TestCase):
    def test_exemplo_completo(self):
        codigo = (RAIZ / "exemplos" / "ExemploArjanov.arj").read_text(encoding="utf-8")
        self.assertEqual(roda(codigo, "2"), [
            "0", "1", "2", "Nome: ", "Arjanov", "positivo", "ativo", "um ou dois",
            "excelente", "aprovado", "reprovado", "1",
        ])

    def test_execucao_comeca_na_main_definida_por_ultimo(self):
        self.assertEqual(roda("func f() { puts('f'); }" + main_com("puts('m'); f();")),
                         ["m", "f"])

    def test_parametros_sao_ligados_por_posicao(self):
        self.assertEqual(roda("func sub(int a, int b): int { return a - b; }"
                              + main_com("int b = 10; int a = 3; puts(sub(b, a));")), ["7"])

    def test_variaveis_homonimas_de_funcoes_diferentes(self):
        self.assertEqual(roda("func f(int x) { x = 99; int y = 1; }"
                              + main_com("int x = 1; int y = 2; f(5); puts(x + y);")), ["3"])

    def test_recursao_preserva_variaveis_e_temporarios(self):
        prog = ("func fib(int n): int { if (n < 2) { return n; }"
                " return fib(n - 1) + fib(n - 2); }"
                "func fat(int n): int { if (n <= 1) { return 1; } return n * fat(n - 1); }")
        self.assertEqual(roda(prog + main_com("puts(fib(12)); puts(fat(6));")), ["144", "720"])

    def test_recursao_com_parametros_trocados(self):
        prog = "func mdc(int a, int b): int { if (b == 0) { return a; } return mdc(b, a % b); }"
        troca = ("func dif(int a, int b, int n): int { if (n == 0) { return a - b; }"
                 " return dif(b, a, n - 1); }")
        self.assertEqual(roda(prog + troca + main_com("puts(mdc(48, 18)); puts(dif(10, 3, 1));")),
                         ["6", "-7"])

    def test_recursao_mutua(self):
        prog = ("func par(int n): bool { if (n == 0) { return true; } return impar(n - 1); }"
                "func impar(int n): bool { if (n == 0) { return false; } return par(n - 1); }")
        self.assertEqual(roda(prog + main_com("puts(par(7)); puts(impar(7));")),
                         ["FALSO", "VERDADEIRO"])

    def test_condicao_com_chamadas_recursivas_dos_dois_lados(self):
        prog = ("func f(int n): int { if (n <= 0) { return 0; }"
                " if (f(n - 1) + n > f(n - 2)) { return f(n - 1) + 1; } return 0; }")
        self.assertEqual(roda(prog + main_com("puts(f(4));")), ["4"])

    def test_nomes_com_outro_significado_na_vm(self):
        self.assertEqual(roda(main_com(
            "int nota = 7; int x = nota; int VERDADEIRO = 5; int t1 = 3; int _t1 = 4;"
            " int constructor = 6; puts(x); puts(VERDADEIRO); puts(t1 + _t1); puts(constructor);")),
            ["7", "5", "7", "6"])

    def test_funcoes_com_nome_de_rotulo_ou_acento(self):
        prog = ("func L1(int n): int { if (n > 0) { return 1; } return 2; }"
                "func média(): int { return 3; } func media(): int { return 4; }")
        self.assertEqual(roda(prog + main_com("puts(L1(1)); puts(L1(0)); puts(média()); puts(media());")),
                         ["1", "2", "3", "4"])

    def test_strings_com_espacos_e_aspas(self):
        prog = "func eco(str s): str { return s; } func fixa(): str { return 'a b c'; }"
        self.assertEqual(roda(prog + main_com(
            "puts(eco('um dois')); puts(fixa()); puts('diz \"oi\"'); puts('a b' == eco('a b'));")),
            ["um dois", "a b c", "diz 'oi'", "VERDADEIRO"])

    def test_operadores_logicos(self):
        self.assertEqual(roda(main_com(
            "puts(true XOR true); puts(true XOR false); puts(true XNOR true);"
            " puts(true AND false); puts(false OR true); puts(NOT false);")),
            ["FALSO", "VERDADEIRO", "VERDADEIRO", "FALSO", "VERDADEIRO", "VERDADEIRO"])

    def test_potencia(self):
        self.assertEqual(roda(main_com(
            "puts(2 ^ 10); puts(-2 ^ 2); puts(2 ^ 3 ^ 2); puts(2 ^ 0); puts(2 ^ -1);"
            " puts(2.0 ^ -1); puts(4.0 ^ 0.5); puts(0.0 ^ 0.5); puts((-2.0) ^ 3);")),
            ["1024", "-4", "512", "1", "0", "0.5", "2.0", "0.0", "-8.0"])
        self.assertAlmostEqual(float(roda(main_com("puts(10.0 ^ -2.5);"))[0]), 10 ** -2.5)

    def test_input_por_tipo(self):
        prog = main_com("int i; float f; bool b; str s; input(i); input(f); input(b); input(s);"
                        " puts(i / 2); puts(f / 4); puts(NOT b); puts(s);")
        self.assertEqual(roda(prog, "7", "10", "true", "ana maria"),
                         ["3", "2.5", "FALSO", "ana maria"])
        self.assertEqual(roda(prog, "7", "10", "0", "x"), ["3", "2.5", "VERDADEIRO", "x"])

    def test_switch_break_e_fallthrough(self):
        prog = main_com("for (int i = 0; i < 4; i = i + 1) { switch (i) { case 0: puts('a');"
                        " case 1: puts('b'); break; case 2: break; default: puts('d'); } }")
        self.assertEqual(roda(prog), ["a", "b", "b", "d"])


if __name__ == "__main__":
    unittest.main()
