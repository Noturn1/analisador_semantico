"""
Testes da leitura do arquivo-fonte (docs/DECISOES.md #23): o BOM é descartado,
o arquivo é lido como UTF-8 e, se não for UTF-8 válido, como latin-1.

Os testes passam pela porta de entrada do compilador (main.main), com arquivos
temporários, e conferem o que o usuário vê: veredito, TAC e posições.

Executar a partir da raiz do projeto:
    python -m unittest discover -s tests -v
"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import main as executar  # noqa: E402

BOM = b"\xef\xbb\xbf"
PROGRAMA = "func main(): int {\n    puts('Média');\n    return 0;\n}\n"


def compilar(dados: bytes, *opcoes: str) -> tuple[int, str]:
    """Roda o compilador sobre um arquivo com os bytes 'dados'.

    Devolve (código de saída, saída padrão)."""
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "programa.arj"
        arquivo.write_bytes(dados)
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = executar(["main.py", str(arquivo), *opcoes])
    return codigo, saida.getvalue()


class TestLeituraDoFonte(unittest.TestCase):
    def test_bom_e_descartado(self):
        # Um BOM no início não pode gerar erros na linha 1.
        codigo, saida = compilar(BOM + PROGRAMA.encode("utf-8"))
        self.assertEqual(codigo, 0, saida)
        self.assertIn("ACEITO", saida)

    def test_acento_em_utf8_sai_certo_no_tac(self):
        codigo, saida = compilar(PROGRAMA.encode("utf-8"))
        self.assertEqual(codigo, 0, saida)
        self.assertIn('print "Média"', saida)
        self.assertNotIn("MÃ©dia", saida)

    def test_arquivo_de_saida_tem_o_acento_certo(self):
        with tempfile.TemporaryDirectory() as pasta:
            tac = Path(pasta) / "saida.tac"
            codigo, saida = compilar(PROGRAMA.encode("utf-8"), "-o", str(tac))
            self.assertEqual(codigo, 0, saida)
            self.assertIn('print "Média"', tac.read_text(encoding="utf-8"))

    def test_coluna_conta_caracteres_e_nao_bytes(self):
        # A coluna esperada sai do texto do programa: o acento ocupa 1 coluna.
        linha = "    puts('Média'); y = 1;"
        fonte = f"func main(): int {{\n{linha}\n    return 0;\n}}\n"
        coluna = linha.index("y = 1") + 1
        codigo, saida = compilar(fonte.encode("utf-8"))
        self.assertEqual(codigo, 1)
        self.assertIn(f"Linha 2, Coluna {coluna}: variável 'y' não declarada", saida)

    def test_arquivo_em_latin1_continua_aceito(self):
        # Sem UTF-8 válido, a leitura cai para latin-1 (como antes da #23).
        codigo, saida = compilar(PROGRAMA.encode("latin-1"))
        self.assertEqual(codigo, 0, saida)
        self.assertIn('print "Média"', saida)

    def test_digito_nao_ascii_nao_derruba_o_compilador(self):
        # Em UTF-8 o '²' chega ao léxico como um caractere só: tem que virar
        # erro léxico, e não uma exceção do Python (decisão #24).
        fonte = "func main(): int {\n    int x = ²;\n    return 0;\n}\n"
        codigo, saida = compilar(fonte.encode("utf-8"))
        self.assertEqual(codigo, 1)
        self.assertIn("Caractere não reconhecido: '²'", saida)

    def test_arquivo_inexistente_sai_com_2(self):
        erro = io.StringIO()
        with contextlib.redirect_stderr(erro):
            codigo = executar(["main.py", "nao_existe.arj"])
        self.assertEqual(codigo, 2)
        self.assertIn("não encontrado", erro.getvalue())


if __name__ == "__main__":
    unittest.main()
