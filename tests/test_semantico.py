"""
Testes do analisador semântico: um programa mínimo por código de erro/aviso
da seção 7 da especificação, mais casos de programas válidos.

Executar a partir da raiz do projeto:
    python3 -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexer import Lexer  # noqa: E402
from sintatico import Parser  # noqa: E402
from arvore import construir_ast  # noqa: E402
from semantico import analisar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def analisar_codigo(codigo: str):
    lexer = Lexer(codigo)
    tokens = lexer.analisar()
    assert not lexer.erros, lexer.erros
    resultado = Parser(tokens).analisar()
    assert resultado.aceito, resultado.erros
    return analisar(construir_ast(resultado.arvore))


def codigos(codigo: str) -> list[str]:
    return [d.codigo for d in analisar_codigo(codigo).diagnosticos()]


def main_com(corpo: str, antes: str = "") -> str:
    """Envolve 'corpo' numa main válida, precedida das funções em 'antes'."""
    return f"{antes}\nfunc main(): int {{\n{corpo}\n    return 0;\n}}\n"


class TestErros(unittest.TestCase):
    """Cada caso deve produzir exatamente os códigos esperados."""

    CASOS = {
        "E01": main_com("y = 1;"),
        "E02": main_com("int x; float x;"),
        "E03": main_com("int i; for (int i = 0; i < 3; i = i + 1) { }"),
        "E04": main_com("int x = 2.5;"),
        "E05": main_com("int x = 5 % 2.0;"),
        "E06": main_com("int k = 1; while (k) { }"),
        "E07": main_com("calcula(1);"),
        "E08": "func soma(int a): int { return a; }\n"
               "func soma(int b): int { return b; }\n"
               "func main() { soma(1); }",
        "E09": main_com("soma(1);", "func soma(int a, int b): int { return a + b; }"),
        "E10": main_com("soma(1, 'a');", "func soma(int a, int b): int { return a + b; }"),
        "E11": main_com("int x = mostra('a');", "func mostra(str m) { puts(m); }"),
        "E12": main_com("f();", "func f() { return 1; }"),
        "E13": main_com("f();", "func f(): int { return; }"),
        "E14": main_com("f();", "func f(): int { return 2.5; }"),
        "E15": main_com("f(1);", "func f(int n): int { if (n > 0) { return 1; } }"),
        "E16": "func soma(int a): int { return a; }",
        "E17": "func main(int x) { }",
        "E18": "func main(): str { return 'a'; }",
        "E19": main_com("int x; input(x + 1);"),
        "E20": main_com("float m = 1.0; switch (m) { }"),
        "E21": main_com("int n = 1; int x = 2; switch (n) { case x: break; }"),
        "E22": main_com("int n = 1; switch (n) { case 'a': break; }"),
        "E23": main_com("int n = 1; switch (n) { case 1: break; case 1: break; }"),
        "E24": main_com("f(1, 2);", "func f(int a, int a) { }"),
        "E25": main_com("break;"),
        "E26": main_com("str s = str(1);"),
        "W01": main_com("", "func nunca() { }"),
        "W02": main_com("int x = 1; x = x / 0;"),
    }

    def test_um_codigo_por_caso(self):
        for esperado, codigo in self.CASOS.items():
            with self.subTest(codigo=esperado):
                self.assertEqual(codigos(codigo), [esperado])

    def test_mensagem_e_formato(self):
        d = analisar_codigo(self.CASOS["E04"]).diagnosticos()[0]
        self.assertEqual(
            str(d),
            "[Erro Semântico] Linha 3, Coluna 1: não é possível atribuir float "
            "a 'x' do tipo int",
        )
        w = analisar_codigo(self.CASOS["W02"]).diagnosticos()[0]
        self.assertTrue(str(w).startswith("[Aviso Semântico]"))

    def test_e05_formato_dos_tipos(self):
        msgs = [d.mensagem for d in analisar_codigo(
            main_com("bool b = NOT 1; str s = 'a' + 'b';")).diagnosticos()]
        self.assertEqual(msgs, [
            "operador 'NOT' não aceita operandos int",
            "operador '+' não aceita operandos str e str",
        ])


class TestRegras(unittest.TestCase):
    def test_indefinido_evita_cascata(self):
        # Só o E01: a soma com 'y' indefinido não gera E05 nem E04.
        self.assertEqual(codigos(main_com("int x = y + 1;")), ["E01"])

    def test_variavel_visivel_so_depois_da_declaracao(self):
        self.assertEqual(codigos(main_com("int x = x;")), ["E01"])

    def test_parametro_e_corpo_no_mesmo_escopo(self):
        self.assertEqual(codigos(main_com("f(1);", "func f(int a) { int a; }")), ["E02"])

    def test_escopos_irmaos_podem_repetir_nomes(self):
        prog = main_com("for (int i = 0; i < 2; i = i + 1) { }\n"
                        "for (int i = 0; i < 2; i = i + 1) { }")
        self.assertEqual(codigos(prog), [])

    def test_conversao_implicita_int_para_float(self):
        prog = main_com("float f = 1; f = media(2, 3);",
                        "func media(int a, float b): float { return (a + b) / 2; }")
        self.assertEqual(codigos(prog), [])

    def test_recursao_e_chamada_antes_da_definicao(self):
        prog = "func main(): int { return fat(5); }\n" \
               "func fat(int n): int { if (n <= 1) { return 1; } else { return n * fat(n - 1); } }"
        self.assertEqual(codigos(prog), [])

    def test_w01_considera_alcancabilidade(self):
        # 'b' só é chamada por 'a', que nunca é chamada: as duas recebem W01.
        prog = main_com("", "func a() { b(); }\nfunc b() { }")
        self.assertEqual(codigos(prog), ["W01", "W01"])

    def test_case_negativo_e_default(self):
        prog = main_com("int n = 1; switch (n) { case -1: break; case 1: n = 2; "
                        "default: n = 3; }")
        self.assertEqual(codigos(prog), [])

    def test_diagnosticos_ordenados_por_posicao(self):
        prog = main_com("y = 1;", "func f() { return 1; }")
        res = analisar_codigo(prog).diagnosticos()
        # W01 fica na posição do 'func', antes do 'return' do E12.
        self.assertEqual([d.codigo for d in res], ["W01", "E12", "E01"])
        self.assertEqual(res, sorted(res, key=lambda d: (d.linha, d.coluna)))

    def test_tipos_anotados_na_ast(self):
        lexer = Lexer(main_com("float f = 1 + 2.5;"))
        arvore = Parser(lexer.analisar()).analisar().arvore
        programa = construir_ast(arvore)
        analisar(programa)
        decl = programa.funcoes[0].corpo.comandos[0]
        self.assertEqual(decl.expr.tipo, "float")
        self.assertEqual(decl.expr.esq.tipo, "int")


class TestExemplos(unittest.TestCase):
    def test_exemplo_valido_sem_diagnosticos(self):
        codigo = (RAIZ / "exemplos" / "ExemploArjanov.arj").read_text(encoding="latin-1")
        self.assertEqual(codigos(codigo), [])

    def test_exemplo_de_erros_tem_um_caso_por_codigo(self):
        codigo = (RAIZ / "exemplos" / "erros_semanticos.arj").read_text(encoding="latin-1")
        esperados = sorted(c for c in TestErros.CASOS if c != "E16")
        self.assertEqual(sorted(codigos(codigo)), esperados)

    def test_exemplo_sem_main(self):
        codigo = (RAIZ / "exemplos" / "erro_sem_main.arj").read_text(encoding="latin-1")
        self.assertEqual(codigos(codigo), ["E16"])

    def test_expressao_longa_nao_estoura_recursao(self):
        soma = " + ".join(["1"] * 3000)
        self.assertEqual(codigos(main_com(f"int s = {soma};")), [])


if __name__ == "__main__":
    unittest.main()
