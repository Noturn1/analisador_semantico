"""
grammar.py - Gramática Livre de Contexto da linguagem Arjanov (Versão B)

Esta é a versão **simplificada** da GLC (ver docs/DECISOES.md #3): as produções
de expressão usam os terminais *agrupados* do analisador léxico
(OP_RELACIONAL, OP_ADITIVO, OP_MULTIPLICATIVO, OP_POTENCIA, OP_AND, OP_OR,
OP_XOR, OP_NOT) em vez de um terminal por operador. Assim, o alfabeto de
terminais do parser coincide com os TokenType do léxico.

As produções seguem o Apêndice A de docs/Especificacao_Semantica_Arjanov_v3.pdf
(Versão B, docs/DECISOES.md #10): 84 produções (0..83), 146 estados, 0 conflitos.

Representação:
  - Cada símbolo é uma string.
  - Terminais são os NOMES de TokenType (ex.: "IDENTIFICADOR", "OP_ADITIVO",
    "PAREN_ESQ", ...) mais "$" (fim de entrada).
  - Não-terminais são nomes em minúsculas (ex.: "programa", "expressao", ...),
    além do símbolo inicial aumentado "programa'".
  - Uma produção é um par (cabeca, corpo), onde corpo é uma tupla de símbolos.
    O corpo vazio () representa ε.

A ordem das produções em PRODUCOES define seus números (0..N-1), usados na
saída de reduções.
"""

from tokens import TokenType

# Símbolo inicial aumentado (produção 0) e símbolo inicial da linguagem.
SIMBOLO_INICIAL_AUMENTADO = "programa'"
SIMBOLO_INICIAL = "programa"

# Marcador de fim de entrada.
FIM = "$"

# ε é representado por corpo vazio.
EPSILON = ()


# ---------------------------------------------------------------------------
# Produções (numeradas pela posição na lista)
# ---------------------------------------------------------------------------
# Convenção de leitura: (cabeca, (simbolo, simbolo, ...))
PRODUCOES: list[tuple[str, tuple[str, ...]]] = [
    # 0 — produção aumentada
    ("programa'", ("programa",)),

    # 1
    ("programa", ("lista_funcoes",)),

    # 2..3 — lista de funções (recursão à esquerda)
    ("lista_funcoes", ("lista_funcoes", "funcao")),
    ("lista_funcoes", ("funcao",)),

    # 4 — função (tipo de retorno opcional: sem ele, é procedimento)
    ("funcao", ("FUNC", "nome_funcao", "PAREN_ESQ", "parametros", "PAREN_DIR",
                "tipo_retorno", "bloco")),

    # 5..6 — tipo de retorno
    ("tipo_retorno", ("DOIS_PONTOS", "tipo")),
    ("tipo_retorno", EPSILON),

    # 7..8
    ("nome_funcao", ("IDENTIFICADOR",)),
    ("nome_funcao", ("MAIN",)),

    # 9..10 — parâmetros
    ("parametros", ("lista_params",)),
    ("parametros", EPSILON),

    # 11..12 — lista de parâmetros (recursão à esquerda)
    ("lista_params", ("lista_params", "VIRGULA", "param")),
    ("lista_params", ("param",)),

    # 13 — parâmetro tipado
    ("param", ("tipo", "IDENTIFICADOR")),

    # 14 — bloco
    ("bloco", ("CHAVE_ESQ", "lista_comandos", "CHAVE_DIR")),

    # 15..16 — lista de comandos
    ("lista_comandos", ("lista_comandos", "comando")),
    ("lista_comandos", EPSILON),

    # 17..25 — comandos
    ("comando", ("declaracao", "PONTO_VIRGULA")),
    ("comando", ("atribuicao", "PONTO_VIRGULA")),
    ("comando", ("chamada", "PONTO_VIRGULA")),
    ("comando", ("retorno", "PONTO_VIRGULA")),
    ("comando", ("cmd_if",)),
    ("comando", ("cmd_while",)),
    ("comando", ("cmd_for",)),
    ("comando", ("cmd_switch",)),
    ("comando", ("BREAK", "PONTO_VIRGULA")),

    # 26..27 — declaração
    ("declaracao", ("tipo", "IDENTIFICADOR")),
    ("declaracao", ("tipo", "IDENTIFICADOR", "ATRIBUICAO", "expressao")),

    # 28..31 — tipos
    ("tipo", ("INT",)),
    ("tipo", ("FLOAT",)),
    ("tipo", ("STR",)),
    ("tipo", ("BOOL",)),

    # 32 — atribuição
    ("atribuicao", ("IDENTIFICADOR", "ATRIBUICAO", "expressao")),

    # 33 — chamada
    ("chamada", ("nome_chamada", "PAREN_ESQ", "argumentos", "PAREN_DIR")),

    # 34..36
    ("nome_chamada", ("IDENTIFICADOR",)),
    ("nome_chamada", ("PUTS",)),
    ("nome_chamada", ("INPUT",)),

    # 37..38 — argumentos
    ("argumentos", ("lista_expr",)),
    ("argumentos", EPSILON),

    # 39..40 — lista de expressões
    ("lista_expr", ("lista_expr", "VIRGULA", "expressao")),
    ("lista_expr", ("expressao",)),

    # 41..42 — retorno
    ("retorno", ("RETURN", "expressao")),
    ("retorno", ("RETURN",)),

    # 43 — if
    ("cmd_if", ("IF", "PAREN_ESQ", "expressao", "PAREN_DIR", "bloco", "senao")),

    # 44..45
    ("senao", ("ELSE", "bloco")),
    ("senao", EPSILON),

    # 46 — while
    ("cmd_while", ("WHILE", "PAREN_ESQ", "expressao", "PAREN_DIR", "bloco")),

    # 47 — for
    ("cmd_for", ("FOR", "PAREN_ESQ", "for_ini", "PONTO_VIRGULA", "expressao",
                 "PONTO_VIRGULA", "atribuicao", "PAREN_DIR", "bloco")),

    # 48..49
    ("for_ini", ("declaracao",)),
    ("for_ini", ("atribuicao",)),

    # 50 — switch (o default, se houver, vem depois de todos os case)
    ("cmd_switch", ("SWITCH", "PAREN_ESQ", "expressao", "PAREN_DIR",
                    "CHAVE_ESQ", "lista_casos", "padrao", "CHAVE_DIR")),

    # 51..52 — lista de casos
    ("lista_casos", ("lista_casos", "caso")),
    ("lista_casos", EPSILON),

    # 53 — caso
    ("caso", ("CASE", "expressao", "DOIS_PONTOS", "lista_comandos")),

    # 54..55 — caso padrão
    ("padrao", ("DEFAULT", "DOIS_PONTOS", "lista_comandos")),
    ("padrao", EPSILON),

    # 56 — expressão (raiz da cadeia de precedência)
    ("expressao", ("expr_or",)),

    # 57..58 — OR
    ("expr_or", ("expr_or", "OP_OR", "expr_xor")),
    ("expr_or", ("expr_xor",)),

    # 59..60 — XOR/XNOR (ambos mapeados a OP_XOR pelo léxico)
    ("expr_xor", ("expr_xor", "OP_XOR", "expr_and")),
    ("expr_xor", ("expr_and",)),

    # 61..62 — AND
    ("expr_and", ("expr_and", "OP_AND", "expr_not")),
    ("expr_and", ("expr_not",)),

    # 63..64 — NOT unário (associativo à direita: NOT a == b é NOT (a == b))
    ("expr_not", ("OP_NOT", "expr_not")),
    ("expr_not", ("expr_rel",)),

    # 65..66 — relacionais (== != < > <= >=  ->  OP_RELACIONAL)
    ("expr_rel", ("expr_rel", "OP_RELACIONAL", "expr_ad")),
    ("expr_rel", ("expr_ad",)),

    # 67..68 — aditivos (+ -  ->  OP_ADITIVO)
    ("expr_ad", ("expr_ad", "OP_ADITIVO", "expr_mul")),
    ("expr_ad", ("expr_mul",)),

    # 69..70 — multiplicativos (* / %  ->  OP_MULTIPLICATIVO)
    ("expr_mul", ("expr_mul", "OP_MULTIPLICATIVO", "expr_un")),
    ("expr_mul", ("expr_un",)),

    # 71..72 — menos/mais unário (OP_ADITIVO em posição prefixa)
    ("expr_un", ("OP_ADITIVO", "expr_un")),
    ("expr_un", ("expr_pot",)),

    # 73..74 — potência (associativa à direita; o expoente pode ter sinal,
    #          e -2 ^ 2 é -(2 ^ 2))
    ("expr_pot", ("expr_prim", "OP_POTENCIA", "expr_un")),
    ("expr_pot", ("expr_prim",)),

    # 75..83 — primários
    ("expr_prim", ("PAREN_ESQ", "expressao", "PAREN_DIR")),
    ("expr_prim", ("chamada",)),
    ("expr_prim", ("IDENTIFICADOR",)),
    ("expr_prim", ("INTEIRO",)),
    ("expr_prim", ("DECIMAL",)),
    ("expr_prim", ("STRING",)),
    ("expr_prim", ("TRUE",)),
    ("expr_prim", ("FALSE",)),
    # 83 — conversão explícita no estilo função: int(e), float(e)
    ("expr_prim", ("tipo", "PAREN_ESQ", "expressao", "PAREN_DIR")),
]


# ---------------------------------------------------------------------------
# Terminais e não-terminais derivados das produções
# ---------------------------------------------------------------------------

def _coletar_simbolos():
    """Separa símbolos das produções em não-terminais e terminais."""
    nao_terminais = {cabeca for cabeca, _ in PRODUCOES}
    simbolos = set()
    for _, corpo in PRODUCOES:
        simbolos.update(corpo)
    terminais = (simbolos - nao_terminais) | {FIM}
    return nao_terminais, terminais


NAO_TERMINAIS, TERMINAIS = _coletar_simbolos()


# Não-terminais escolhidos como pontos de sincronização na recuperação de erro
# (modo pânico, "método do Dragão"). Ordem = PRIORIDADE GLOBAL: procuramos na
# pilha, do topo para baixo, um estado com GOTO sobre 'comando' (recuperação em
# nível de comando/statement — a que melhor localiza o erro); só se não houver,
# recuamos para 'bloco' e por fim 'funcao'. Sincronizar em nível de comando faz
# o parser descartar o statement inteiro que contém o erro e retomar limpo no
# próximo statement, evitando cascatas de erros espúrios.
NAO_TERMINAIS_RECUPERACAO = ("comando", "bloco", "funcao")


def simbolo_do_token(token) -> str:
    """
    Traduz um Token (produzido pelo léxico) para o símbolo terminal
    correspondente na gramática.

    - EOF  -> "$"
    - demais -> o próprio nome do TokenType (ex.: OP_ADITIVO, IDENTIFICADOR)

    O token ERRO NÃO é símbolo da gramática; ele é tratado à parte pelo parser
    (dispara a recuperação). Ainda assim retornamos seu nome para diagnósticos.
    """
    if token.tipo == TokenType.EOF:
        return FIM
    return token.tipo.name


def formatar_producao(indice: int) -> str:
    """Formata uma produção como 'cabeca -> s1 s2 ...' (ε para corpo vazio)."""
    cabeca, corpo = PRODUCOES[indice]
    direita = " ".join(corpo) if corpo else "ε"
    return f"{cabeca} -> {direita}"
