"""
main.py - Compilador Arjanov: pipeline léxico, sintático e semântico (Versão B)

Uso (a partir da pasta do projeto):
    python3 src/main.py <arquivo-fonte>       Analisa o arquivo informado
    python3 src/main.py --demo                Analisa um programa embutido
    python3 src/main.py <arquivo> --acoes     Também imprime o traço shift/reduce
    python3 src/main.py <arquivo> --tokens    Também imprime a tabela de tokens
    python3 src/main.py <arquivo> --ast       Também imprime a AST, com os tipos
    python3 src/main.py <arquivo> --tabela    Também imprime a tabela de símbolos
    python3 src/main.py --help                Exibe esta ajuda

Alternativa: use o atalho `python3 run.py <arquivo>` na raiz do projeto.

Pipeline: arquivo -> Lexer (tokens) -> Parser SLR(1) -> AST -> Semântico -> relatório.
A AST e a análise semântica só rodam se não houver erros léxicos nem
sintáticos. Avisos semânticos não tornam o programa inválido.

Códigos de saída:
    0 : programa ACEITO (pode haver avisos semânticos)
    1 : foram detectados erros léxicos, sintáticos ou semânticos
    2 : erro de argumentos ou de E/S (arquivo não encontrado etc.)
"""

import sys
from pathlib import Path

from tokens import Token
from lexer import Lexer, LexerError
from sintatico import Parser, formatar_arvore
from arvore import construir_ast, formatar_ast
from semantico import analisar as analisar_semantica, formatar_tabela
from slr import TabelaSLR


CODIGO_DEMO = """func calcula_media(int num1, int num2): float {
    float media = (num1 + num2) / 2.0;
    return media;
}

func main(): int {
    int contador = 0;
    bool ativo = NOT (true AND false);
    puts('Media: ');
    input(contador);
    puts(calcula_media(contador, 3));

    for (int i = 0; i < contador; i = i + 1) {
        puts(i);
        if (i == 5) {
            break;
        }
    }

    switch (contador) {
        case 0:
            puts('zero');
            break;
        case -1:
            puts('menos um');
            break;
        default:
            puts('outro');
    }

    return 0;
}
"""


# Impressão auxiliar


def cabecalho(titulo: str):
    linha = "=" * 72
    print(linha)
    print(titulo)
    print(linha)


def imprimir_tokens(tokens: list[Token]):
    print(f"{'#':>4}  {'TIPO':<22} {'LEXEMA':<30} {'POSIÇÃO':<10}")
    print("-" * 72)
    for i, t in enumerate(tokens, start=1):
        lex = repr(t.lexema) if t.lexema else "''"
        print(f"{i:>4}  {t.tipo.name:<22} {lex:<30} {t.linha}:{t.coluna}")


def imprimir_erros_lexicos(erros: list[LexerError]):
    cabecalho(f"Erros Léxicos: {len(erros)}")
    for e in erros:
        print(f"  Linha {e.linha}, Coluna {e.coluna}: {e.mensagem}")


def imprimir_erros_sintaticos(erros):
    cabecalho(f"Erros Sintáticos: {len(erros)}")
    for e in erros:
        print(f"  Linha {e.linha}, Coluna {e.coluna}: {e.mensagem}")


# Pipeline principal


def analisar(codigo: str, origem: str, mostrar_acoes: bool, mostrar_tokens: bool,
             mostrar_ast: bool = False, mostrar_tabela: bool = False) -> int:
    # 1. Análise léxica
    lexer = Lexer(codigo)
    tokens = lexer.analisar()

    cabecalho(f"Compilador Arjanov — {origem}")

    if mostrar_tokens:
        imprimir_tokens(tokens)
        print()

    # 2. Análise sintática (SLR(1))
    tabela = TabelaSLR()
    if tabela.conflitos:
        # Não deveria acontecer (a gramática é SLR(1)); avisa se acontecer.
        print("AVISO: a tabela SLR possui conflitos:")
        for c in tabela.conflitos:
            print("  ", c)
        print()

    parser = Parser(tokens, tabela)
    resultado = parser.analisar()

    # 3. Relatório
    if mostrar_acoes:
        cabecalho(f"Traço de Ações (shift/reduce): {len(resultado.acoes)}")
        for passo, acao in enumerate(resultado.acoes, start=1):
            print(f"  {passo:>4}  {acao}")
        print()

    cabecalho("Árvore Sintática")
    if resultado.arvore is not None:
        for linha in formatar_arvore(resultado.arvore):
            print(linha)
    else:
        print("  (não foi possível construir a árvore)")
    print()

    if lexer.erros:
        imprimir_erros_lexicos(lexer.erros)
        print()
    if resultado.erros:
        imprimir_erros_sintaticos(resultado.erros)
        print()

    total_erros = len(lexer.erros) + len(resultado.erros)

    # 4. AST e análise semântica (só para programas sem erros anteriores)
    sem = None
    if total_erros == 0 and resultado.arvore is not None:
        programa = construir_ast(resultado.arvore)
        sem = analisar_semantica(programa)

        if mostrar_ast:
            # Impressa depois da semântica para exibir o tipo de cada expressão.
            cabecalho("Árvore Sintática Abstrata (AST)")
            for linha in formatar_ast(programa):
                print(linha)
            print()

        if mostrar_tabela:
            cabecalho("Tabela de Símbolos")
            for linha in formatar_tabela(sem):
                print(linha)
            print()

        diagnosticos = sem.diagnosticos()
        if diagnosticos:
            cabecalho(f"Análise Semântica: {len(sem.erros)} erro(s), "
                      f"{len(sem.avisos)} aviso(s)")
            for d in diagnosticos:
                print(f"  {d}")
            print()

    # 5. Veredito
    cabecalho("Resultado")
    if sem is not None and not sem.erros:
        print("  ACEITO — programa válido.")
        detalhe = f"{len(resultado.acoes)} ações sintáticas"
        if sem.avisos:
            detalhe += f"; {len(sem.avisos)} aviso(s) semântico(s)"
        print(f"  ({detalhe}; sem erros)")
        return 0

    print("  REJEITADO — foram encontrados erros.")
    if sem is not None:
        print(f"  Semânticos: {len(sem.erros)} | Avisos: {len(sem.avisos)}")
    else:
        print(
            f"  Léxicos: {len(lexer.erros)} | "
            f"Sintáticos: {len(resultado.erros)}"
        )
        if not mostrar_acoes:
            print("  (use --acoes para ver o traço shift/reduce completo)")
    return 1


def mostrar_ajuda():
    print(__doc__)


def main(argv: list[str]) -> int:
    args = argv[1:]

    if not args or args[0] in ("-h", "--help"):
        mostrar_ajuda()
        return 0 if args else 2

    mostrar_acoes = "--acoes" in args
    mostrar_tokens = "--tokens" in args
    mostrar_ast = "--ast" in args
    mostrar_tabela = "--tabela" in args
    posicionais = [a for a in args if not a.startswith("--")]

    if "--demo" in args:
        return analisar(CODIGO_DEMO, "<demo embutido>", mostrar_acoes, mostrar_tokens,
                        mostrar_ast, mostrar_tabela)

    if not posicionais:
        print("Erro: informe um arquivo-fonte ou use --demo.", file=sys.stderr)
        return 2

    caminho = Path(posicionais[0])
    if not caminho.exists():
        print(f"Erro: arquivo '{caminho}' não encontrado.", file=sys.stderr)
        return 2
    if not caminho.is_file():
        print(f"Erro: '{caminho}' não é um arquivo regular.", file=sys.stderr)
        return 2

    try:
        codigo = caminho.read_text(encoding="latin-1")
    except OSError as e:
        print(f"Erro ao ler '{caminho}': {e}", file=sys.stderr)
        return 2

    return analisar(codigo, str(caminho), mostrar_acoes, mostrar_tokens, mostrar_ast,
                    mostrar_tabela)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
