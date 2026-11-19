"""
Testes do analisador sintático: cada token com erro é registrado uma vez só
(docs/DECISOES.md #27).

Executar a partir da raiz do projeto:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from lexer import Lexer  # noqa: E402
from sintatico import Parser  # noqa: E402

MAIN = "func main(): int {\n    return 0;\n}\n"


def erros_sintaticos(codigo: str) -> list[tuple[int, int, str]]:
    resultado = Parser(Lexer(codigo).analisar()).analisar()
    return [(e.linha, e.coluna, e.mensagem) for e in resultado.erros]


def posicoes(codigo: str) -> list[tuple[int, int]]:
    return [(linha, coluna) for linha, coluna, _ in erros_sintaticos(codigo)]


def pos(fonte: str, trecho: str, ocorrencia: int = 1) -> tuple[int, int]:
    """(linha, coluna), de base 1, do primeiro caractere de 'trecho' no texto.

    A posição esperada sai do texto do programa de teste, e não da saída do
    compilador."""
    indice = -1
    for _ in range(ocorrencia):
        indice = fonte.index(trecho, indice + 1)
    linha = fonte.count("\n", 0, indice) + 1
    coluna = indice - (fonte.rfind("\n", 0, indice) + 1) + 1
    return linha, coluna


def fim(fonte: str) -> tuple[int, int]:
    """Posição do fim de arquivo: logo depois do último caractere."""
    return fonte.count("\n") + 1, len(fonte) - (fonte.rfind("\n") + 1) + 1


class TestUmErroPorToken(unittest.TestCase):
    """Quando a recuperação em modo pânico não descarta o token com erro, o
    parser erra nele de novo. Esse segundo erro não pode ser registrado."""

    def test_chave_a_mais(self):
        fonte = MAIN + "}"
        self.assertEqual(posicoes(fonte), [pos(fonte, "}", 2)])

    def test_chave_ausente_no_fim_do_arquivo(self):
        fonte = "func main(): int { return 0;"
        self.assertEqual(posicoes(fonte), [fim(fonte)])

    def test_case_fora_de_switch(self):
        fonte = "func main(): int {\n    case 1:\n    return 0;\n}\n"
        self.assertEqual(posicoes(fonte), [pos(fonte, "case")])

    def test_default_antes_de_case(self):
        fonte = ("func main(): int {\n    int x = 1;\n"
                 "    switch (x) {\n        default: x = 2;\n        case 1: x = 3;\n    }\n"
                 "    return 0;\n}\n")
        self.assertEqual(posicoes(fonte), [pos(fonte, "case")])

    def test_texto_depois_da_ultima_funcao(self):
        fonte = MAIN + "garbage"
        self.assertEqual(posicoes(fonte), [pos(fonte, "garbage")])

    def test_parentese_esquecido_na_condicao(self):
        # O primeiro erro é o '{' no lugar do ')'. Os que vêm depois são
        # consequência da recuperação, mas nenhum token aparece duas vezes.
        fonte = "func main(): int {\n    if (true {\n    }\n    return 0;\n}\n"
        encontradas = posicoes(fonte)
        self.assertEqual(encontradas[0], pos(fonte, "{", 2))
        self.assertEqual(len(encontradas), len(set(encontradas)))

    def test_erros_em_comandos_diferentes_continuam_separados(self):
        # Dois comandos defeituosos são dois erros: a correção não pode esconder
        # um erro de outro token.
        fonte = "func main(): int {\n    int x = ;\n    int y = ;\n    return 0;\n}\n"
        self.assertEqual(posicoes(fonte), [pos(fonte, ";", 1), pos(fonte, ";", 2)])

    def test_erros_em_funcoes_diferentes_continuam_separados(self):
        fonte = ("func a() { int x = ; }\nfunc b() { int y = ; }\n"
                 "func main(): int { int z = ; return 0; }\n")
        self.assertEqual(posicoes(fonte),
                         [pos(fonte, ";", 1), pos(fonte, ";", 2), pos(fonte, ";", 3)])

    def test_exemplo_com_erros_nao_repete_posicao(self):
        fonte = (RAIZ / "exemplos" / "erros.arj").read_text(encoding="utf-8")
        encontradas = posicoes(fonte)
        self.assertTrue(encontradas)
        self.assertEqual(len(encontradas), len(set(encontradas)))


if __name__ == "__main__":
    unittest.main()
