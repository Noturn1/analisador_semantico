"""
Testes do léxico: dígitos são só ASCII (docs/DECISOES.md #24).

Executar a partir da raiz do projeto:
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lexer import Lexer  # noqa: E402
from tokens import TokenType  # noqa: E402


def varrer(codigo: str):
    lexer = Lexer(codigo)
    tokens = lexer.analisar()
    return tokens, lexer.erros


def erros_de(codigo: str) -> list[tuple[int, int, str]]:
    return [(e.linha, e.coluna, e.mensagem) for e in varrer(codigo)[1]]


class TestDigitosAscii(unittest.TestCase):
    def test_digito_nao_ascii_e_erro_lexico(self):
        # '²' é um dígito para str.isdigit(), mas não faz parte do alfabeto.
        codigo = "int x = ²;"
        self.assertEqual(erros_de(codigo), [
            (1, codigo.index("²") + 1, "Caractere não reconhecido: '²'"),
        ])

    def test_digito_arabe_indico_tambem_e_erro_lexico(self):
        # '٣' (U+0663) vale 3 para int(), mas só 0-9 são dígitos da linguagem.
        codigo = "int x = ٣;"
        self.assertEqual(erros_de(codigo), [
            (1, codigo.index("٣") + 1, "Caractere não reconhecido: '٣'"),
        ])

    def test_digito_nao_ascii_depois_de_numero(self):
        # O número termina no último dígito ASCII; o resto é erro, e cada erro
        # léxico emite um token ERRO (decisão #9).
        codigo = "12²"
        tokens, erros = varrer(codigo)
        self.assertEqual([(t.tipo, t.lexema) for t in tokens[:-1]],
                         [(TokenType.INTEIRO, "12"), (TokenType.ERRO, "²")])
        self.assertEqual([(e.linha, e.coluna) for e in erros],
                         [(1, codigo.index("²") + 1)])

    def test_digito_nao_ascii_depois_do_ponto_nao_forma_decimal(self):
        tokens, _ = varrer("1.²")
        numeros = [t.lexema for t in tokens
                   if t.tipo in (TokenType.INTEIRO, TokenType.DECIMAL)]
        self.assertEqual(numeros, ["1"])

    def test_numeros_ascii_continuam_iguais(self):
        tokens, erros = varrer("12 3.5")
        self.assertEqual(erros, [])
        self.assertEqual([(t.tipo, t.lexema) for t in tokens[:-1]],
                         [(TokenType.INTEIRO, "12"), (TokenType.DECIMAL, "3.5")])

    def test_identificador_acentuado_continua_valido(self):
        # Decidido em 2026-11-19: só os dígitos viram ASCII; letras acentuadas
        # em identificadores continuam aceitas.
        tokens, erros = varrer("média")
        self.assertEqual(erros, [])
        self.assertEqual([(t.tipo, t.lexema) for t in tokens[:-1]],
                         [(TokenType.IDENTIFICADOR, "média")])


if __name__ == "__main__":
    unittest.main()
