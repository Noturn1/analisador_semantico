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


def pos(fonte: str, trecho: str, ocorrencia: int = 1) -> tuple[int, int]:
    """(linha, coluna), de base 1, do primeiro caractere de 'trecho' no texto.

    A posição esperada de cada diagnóstico sai do texto do programa de teste,
    e não da saída do compilador."""
    indice = -1
    for _ in range(ocorrencia):
        indice = fonte.index(trecho, indice + 1)
    linha = fonte.count("\n", 0, indice) + 1
    coluna = indice - (fonte.rfind("\n", 0, indice) + 1) + 1
    return linha, coluna


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


class TestInterpretacoes(unittest.TestCase):
    """Interpretações da Fase 3 em que a spec é omissa, confirmadas em
    2026-11-19 (docs/PLANO.md, Fase 3; decisão #21)."""

    # Item 1: posição de cada diagnóstico. Cada entrada diz com qual trecho do
    # programa de TestErros.CASOS o diagnóstico começa: (trecho, ocorrência).
    POSICOES = {
        "E01": ("y = 1", 1),
        "E02": ("float x", 1),            # 2ª declaração
        "E03": ("int i = 0", 1),          # declaração interna
        "E04": ("int x = 2.5", 1),
        "E05": ("5 % 2.0", 1),            # operando esquerdo
        "E06": ("k)", 1),                 # a condição
        "E07": ("calcula(1)", 1),         # nome da chamada
        "E08": ("func soma(int b)", 1),   # 2ª definição
        "E09": ("soma(1);", 1),
        "E10": ("'a'", 1),                # o argumento
        "E11": ("mostra('a')", 1),
        "E12": ("return 1", 1),
        "E13": ("return;", 1),
        "E14": ("return 2.5", 1),
        "E15": ("func f(int n)", 1),
        "E16": ("func soma", 1),          # primeira linha do programa
        "E17": ("func main(int x)", 1),
        "E18": ("func main(): str", 1),
        "E19": ("input(x + 1)", 1),
        "E20": ("m)", 1),                 # a expressão do switch
        "E21": ("x:", 1),                 # o valor do case
        "E22": ("'a':", 1),
        "E23": ("1:", 2),                 # o 2º case 1
        "E24": ("int a", 2),              # o 2º parâmetro
        "E25": ("break;", 1),
        "E26": ("str(1)", 1),
        "W01": ("func nunca", 1),
        "W02": ("x / 0", 1),              # operando esquerdo
    }

    def test_posicao_de_cada_diagnostico(self):
        self.assertEqual(sorted(self.POSICOES), sorted(TestErros.CASOS))
        for codigo, (trecho, ocorrencia) in self.POSICOES.items():
            fonte = TestErros.CASOS[codigo]
            with self.subTest(codigo=codigo):
                obtido = [(d.codigo, d.linha, d.coluna)
                          for d in analisar_codigo(fonte).diagnosticos()]
                self.assertEqual(obtido, [(codigo, *pos(fonte, trecho, ocorrencia))])

    def test_e09_suprime_e10(self):
        # Com o número errado de argumentos os tipos não são comparados.
        prog = main_com("soma('a');", "func soma(int a, int b): int { return a + b; }")
        self.assertEqual(codigos(prog), ["E09"])

    def test_case_nao_constante_gera_so_e21(self):
        # 'x' não existe, mas o valor do case não é analisado: nada de E01.
        self.assertEqual(codigos(main_com("int n = 1; switch (n) { case x: break; }")),
                         ["E21"])

    def test_funcao_duplicada_primeira_vale_e_segundo_corpo_e_analisado(self):
        def prog(chamada: str) -> str:
            return ("func soma(int a): int { return a; }\n"
                    "func soma(int b, int c): int { return d; }\n"
                    f"func main() {{ int x = {chamada}; }}")
        # O corpo da 2ª definição é analisado (E01 em 'd') e a 1ª vale nas
        # chamadas: 'soma(1)' está certa, 'soma(1, 2)' tem argumentos demais.
        self.assertEqual(codigos(prog("soma(1)")), ["E08", "E01"])
        self.assertEqual(codigos(prog("soma(1, 2)")), ["E08", "E01", "E09"])

    def test_apos_e02_fica_a_declaracao_original(self):
        # 'x' continua int: atribuir 2.5 gera E04.
        self.assertEqual(codigos(main_com("int x = 1; float x; x = 2.5;")), ["E02", "E04"])

    def test_apos_e03_o_nome_novo_vale_no_escopo_interno(self):
        # 'i' interno é float: 'i = i + 0.5' não gera E04.
        prog = main_com("int i = 0; for (float i = 0.0; i < 1.0; i = i + 0.5) { }")
        self.assertEqual(codigos(prog), ["E03"])

    # Item 4 (W01 omitido quando há E16) já está protegido por CASOS["E16"]: um
    # programa só com 'soma' teria W01 se o aviso não fosse omitido.


class TestAvisoDivisaoPorZero(unittest.TestCase):
    """W02 e E05 (docs/PLANO.md, Fase 3, item 7; decisão #21)."""

    def test_modulo_por_zero_decimal_so_gera_e05(self):
        # '%' exige int e int (seção 6.1): o E05 já rejeita o programa, e o
        # W02 no mesmo nó seria ruído.
        self.assertEqual(codigos(main_com("int k = 1; int z = k % 0.0;")), ["E05"])

    def test_operando_indefinido_mantem_o_w02(self):
        # O erro anterior (E01) deixa o operando indefinido; o W02 continua.
        self.assertEqual(codigos(main_com("int x = y / 0;")), ["E01", "W02"])

    def test_divisor_zero_valido_gera_w02(self):
        prog = main_com("float f = 1.0; f = f / 0.0; int i = 1; i = i % 0;")
        self.assertEqual(codigos(prog), ["W02", "W02"])


class TestInput(unittest.TestCase):
    """Argumento de input: quantidade (E09), tipo de argumento (E19) e
    declaração (E01), seção 6.6 da spec e decisão #26."""

    # corpo da main -> códigos esperados, na ordem das posições (decisão #17)
    CASOS = {
        "input();": ["E09"],
        "int a; int b; input(a, b);": ["E09"],
        "input(2, 3);": ["E09"],             # a contagem vem antes: sem E19
        "input(2);": ["E19"],
        "input('a');": ["E19"],
        "input(true);": ["E19"],
        "int x = 1; input(x + 1);": ["E19"],
        "input(zz);": ["E01"],               # variável escrita e não declarada
        "input(zz + 1);": ["E19", "E01"],    # dois erros: o argumento e o nome
        "int x; input((x));": [],            # parênteses em volta da variável
        "int x; input(x);": [],
    }

    def test_codigo_de_cada_argumento(self):
        for corpo, esperado in self.CASOS.items():
            with self.subTest(corpo=corpo):
                self.assertEqual(codigos(main_com(corpo)), esperado)

    def test_posicao_do_diagnostico(self):
        # E09 e E19 ficam no nome da chamada; o E01 fica no nome da variável.
        esperado = {
            "input();": ("E09", "input()"),
            "input(2);": ("E19", "input(2)"),
            "input(zz);": ("E01", "zz"),
        }
        for corpo, (codigo, trecho) in esperado.items():
            fonte = main_com(corpo)
            with self.subTest(corpo=corpo):
                obtido = [(d.codigo, d.linha, d.coluna)
                          for d in analisar_codigo(fonte).diagnosticos()]
                self.assertEqual(obtido, [(codigo, *pos(fonte, trecho))])


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
