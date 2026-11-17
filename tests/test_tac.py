"""
Testes do gerador de código de três endereços e regressão da tabela SLR.

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
from slr import TabelaSLR  # noqa: E402
from tac import gerar_tac  # noqa: E402

DADOS = Path(__file__).resolve().parent / "dados"


def tac_de(codigo: str) -> list[str]:
    lexer = Lexer(codigo)
    resultado = Parser(lexer.analisar()).analisar()
    assert not lexer.erros and resultado.aceito
    programa = construir_ast(resultado.arvore)
    sem = analisar(programa)
    assert not sem.erros, [str(e) for e in sem.erros]
    return gerar_tac(programa, sem)


def instrucoes(codigo: str) -> list[str]:
    """TAC sem recuo e sem linhas em branco, para comparações compactas."""
    return [linha.strip() for linha in tac_de(codigo) if linha.strip()]


class TestSecao10(unittest.TestCase):
    def test_tac_identico_ao_da_especificacao(self):
        # tests/dados/secao10.tac foi conferido linha a linha com a seção 10
        # da especificação (a comparação ignora apenas o recuo do PDF).
        codigo = (DADOS / "secao10.arj").read_text(encoding="latin-1")
        esperado = (DADOS / "secao10.tac").read_text(encoding="utf-8").splitlines()
        self.assertEqual(tac_de(codigo), esperado)


class TestEsquemas(unittest.TestCase):
    def test_xnor_vira_xor_e_negacao(self):
        self.assertEqual(instrucoes("func main() { bool b = true XNOR false; }"), [
            "main:", "t1 = true XOR false", "t2 = ! t1", "b = t2", "return",
        ])

    def test_nomes_que_colidem_com_temporarios_e_rotulos(self):
        self.assertEqual(instrucoes("func main() { int t1 = 1; int L2 = t1; int x9 = 0; }"), [
            "main:", "_t1 = 1", "_L2 = _t1", "x9 = 0", "return",
        ])

    def test_valores_padrao(self):
        self.assertEqual(instrucoes("func main() { int a; float b; str c; bool d; }"), [
            "main:", "a = 0", "b = 0.0", "c = ''", "d = false", "return",
        ])

    def test_widen_em_argumento_atribuicao_e_constante(self):
        prog = ("func f(float a) { }\n"
                "func main() { int i = 1; float x; f(i); x = i; x = 2; }")
        self.assertEqual(instrucoes(prog), [
            "f:", "return",
            "main:", "i = 1", "x = 0.0",
            "t1 = inttofloat(i)", "param t1", "call f, 1",
            "t2 = inttofloat(i)", "x = t2",
            "x = 2.0",
            "return",
        ])

    def test_condicao_composta_usa_ifFalse_do_endereco(self):
        prog = "func main() { int a = 1; if (a > 0 AND a < 5) { a = 2; } }"
        self.assertEqual(instrucoes(prog), [
            "main:", "a = 1",
            "t1 = a > 0", "t2 = a < 5", "t3 = t1 AND t2",
            "ifFalse t3 goto L1", "a = 2", "L1:", "return",
        ])

    def test_if_else(self):
        prog = "func main() { int a = 1; if (a == 1) { a = 2; } else { a = 3; } }"
        self.assertEqual(instrucoes(prog), [
            "main:", "a = 1", "ifFalse a == 1 goto L1", "a = 2", "goto L2",
            "L1:", "a = 3", "L2:", "return",
        ])

    def test_for_com_break_pula_o_passo(self):
        prog = "func main() { for (int i = 0; i < 3; i = i + 1) { break; } }"
        self.assertEqual(instrucoes(prog), [
            "main:", "i = 0", "L1:", "ifFalse i < 3 goto L2", "goto L2",
            "t1 = i + 1", "i = t1", "goto L1", "L2:", "return",
        ])

    def test_switch_sem_default(self):
        prog = "func main() { int k = 1; switch (k) { case -1: k = 0; } }"
        self.assertEqual(instrucoes(prog), [
            "main:", "k = 1", "goto L1", "L3:", "k = 0", "goto L2",
            "L1:", "if k == -1 goto L3", "goto L2", "L2:", "return",
        ])

    def test_return_implicito_so_quando_falta(self):
        self.assertEqual(instrucoes("func main() { return; }"), ["main:", "return"])
        self.assertEqual(instrucoes("func main(): int { return 0; }"), ["main:", "return 0"])

    def test_funcao_com_retorno_chamada_como_comando(self):
        prog = "func f(): int { return 1; }\nfunc main() { f(); }"
        self.assertIn("call f, 0", instrucoes(prog))

    def test_input_e_puts(self):
        self.assertEqual(instrucoes("func main() { str s; input(s); puts(s); }"), [
            "main:", "s = ''", "s = call input, 0", "param s", "call puts, 1", "return",
        ])

    def test_conversoes_explicitas(self):
        prog = "func main() { float f = 2.5; int i = int(f); float g = float(i); i = int(i); }"
        self.assertEqual(instrucoes(prog), [
            "main:", "f = 2.5", "t1 = floattoint(f)", "i = t1",
            "t2 = inttofloat(i)", "g = t2", "i = i", "return",
        ])

    def test_expressao_longa_nao_estoura_recursao(self):
        soma = " + ".join(["1"] * 3000)
        tac = instrucoes(f"func main() {{ int s = {soma}; }}")
        self.assertEqual(tac[-2], "s = t2999")


class TestGramatica(unittest.TestCase):
    def test_tabela_slr_da_versao_b(self):
        tabela = TabelaSLR()
        self.assertEqual(len(tabela.estados), 146)
        self.assertEqual(tabela.conflitos, [])


if __name__ == "__main__":
    unittest.main()
