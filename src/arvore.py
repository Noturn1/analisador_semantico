"""
arvore.py - Árvore sintática abstrata (AST) da linguagem Arjanov

Este módulo define os nós da AST e o conversor árvore sintática -> AST
(ver docs/DECISOES.md #11, #13, #14 e #15).

A árvore sintática produzida pelo parser espelha a gramática: listas recursivas
à esquerda (lista_comandos, lista_params, ...), produções ε e a cadeia de
precedência de expressões (expressao -> expr_or -> expr_xor -> ... ->
expr_prim). A AST elimina tudo isso e guarda um nó por construção da linguagem.

Convenções:
  - Todo nó tem 'linha' e 'coluna' do primeiro token da construção (é a
    posição usada nas mensagens de erro semântico).
  - Todo nó de expressão tem o campo 'tipo', vazio (None) na construção e
    preenchido pelo analisador semântico.
  - O operador exato de Binario/Unario vem do lexema do token, porque a
    gramática usa terminais agrupados (docs/DECISOES.md #3).
  - Posição e 'tipo' não participam da comparação (==) entre nós: dois nós são
    iguais se tiverem a mesma estrutura. Isso simplifica os testes.

O nome do módulo não é 'ast.py' porque ele colidiria com o módulo 'ast' da
biblioteca padrão, que o próprio 'dataclasses' importa (docs/DECISOES.md #13
e #16).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from sintatico import NoArvore


# ---------------------------------------------------------------------------
# Nós da AST
# ---------------------------------------------------------------------------


@dataclass
class No:
    """Base de todos os nós: posição do primeiro token da construção."""

    linha: int = field(compare=False)
    coluna: int = field(compare=False)


@dataclass
class Expr(No):
    """Base dos nós de expressão. 'tipo' é preenchido pela análise semântica."""

    tipo: Optional[str] = field(default=None, init=False, compare=False)


# -- Expressões ---------------------------------------------------------------


@dataclass
class Literal(Expr):
    """Constante: 'categoria' é 'int', 'float', 'str' ou 'bool'."""

    valor: Union[int, float, str, bool]
    categoria: str


@dataclass
class Var(Expr):
    nome: str


@dataclass
class Binario(Expr):
    """Operação binária. 'op' é o operador exato: '+', '<=', 'AND', 'XNOR', ..."""

    op: str
    esq: Expr
    dir: Expr


@dataclass
class Unario(Expr):
    """Operação unária: 'op' é '-', '+' ou 'NOT'."""

    op: str
    operando: Expr


@dataclass
class Conversao(Expr):
    """Conversão explícita no estilo função: int(e), float(e), str(e), bool(e)."""

    destino: str
    expr: Expr


@dataclass
class Chamada(Expr):
    """Chamada de função de usuário ou das primitivas 'puts' e 'input'.

    Aparece tanto em expressões quanto como comando isolado (o valor de
    retorno é descartado).
    """

    nome: str
    args: list[Expr]


# -- Comandos -----------------------------------------------------------------


@dataclass
class Decl(No):
    """Declaração 'tipo nome' ou 'tipo nome = expr' (expr None se ausente)."""

    tipo_decl: str
    nome: str
    expr: Optional[Expr]


@dataclass
class Atrib(No):
    nome: str
    expr: Expr


@dataclass
class Bloco(No):
    """Sequência de comandos entre chaves."""

    comandos: list[No]


@dataclass
class If(No):
    cond: Expr
    entao: Bloco
    senao: Optional[Bloco]


@dataclass
class While(No):
    cond: Expr
    corpo: Bloco


@dataclass
class For(No):
    """for (ini; cond; passo) corpo. O passo é uma atribuição comum (#15)."""

    ini: Union[Decl, Atrib]
    cond: Expr
    passo: Atrib
    corpo: Bloco


@dataclass
class Caso(No):
    """Um 'case valor:' ou, com valor None, o 'default:' de um switch."""

    valor: Optional[Expr]
    comandos: list[No]


@dataclass
class Switch(No):
    expr: Expr
    casos: list[Caso]
    padrao: Optional[Caso]


@dataclass
class Break(No):
    pass


@dataclass
class Return(No):
    expr: Optional[Expr]


# -- Estrutura do programa ----------------------------------------------------


@dataclass
class Param(No):
    tipo_param: str
    nome: str


@dataclass
class Funcao(No):
    """Função. 'tipo_retorno' é None para procedimentos (sem ': tipo')."""

    nome: str
    params: list[Param]
    tipo_retorno: Optional[str]
    corpo: Bloco


@dataclass
class Programa(No):
    funcoes: list[Funcao]


# ---------------------------------------------------------------------------
# Conversor árvore sintática -> AST
# ---------------------------------------------------------------------------

# Não-terminais binários recursivos à esquerda: X -> X OP Y | Y
_BINARIOS = ("expr_or", "expr_xor", "expr_and", "expr_rel", "expr_ad", "expr_mul")

# Não-terminais unários recursivos à direita: X -> OP X | Y
_UNARIOS = ("expr_not", "expr_un")

_LITERAIS = {
    "INTEIRO": ("int", int),
    "DECIMAL": ("float", float),
    "STRING": ("str", str),
    "TRUE": ("bool", lambda _: True),
    "FALSE": ("bool", lambda _: False),
}


def _primeiro_token(no: NoArvore):
    """Token mais à esquerda da subárvore (None se ela só derivar ε)."""
    pilha = [no]
    while pilha:
        atual = pilha.pop()
        if atual.eh_folha():
            return atual.token
        pilha.extend(reversed(atual.filhos))
    return None


def _pos(no: NoArvore) -> dict:
    tok = _primeiro_token(no)
    return {"linha": tok.linha, "coluna": tok.coluna}


def _achatar_lista(no: NoArvore) -> list[NoArvore]:
    """
    Achata uma lista recursiva à esquerda nos seus elementos, em ordem.

    Cobre as três formas usadas na gramática:
        L -> L item | ε          (lista_comandos, lista_casos)
        L -> L item | item       (lista_funcoes)
        L -> L , item | item     (lista_params, lista_expr)

    É iterativa: o comprimento da lista não consome pilha de recursão.
    """
    itens = []
    atual = no
    while atual.filhos:
        filhos = atual.filhos
        if filhos[0].simbolo == atual.simbolo:  # L -> L ... item
            itens.append(filhos[-1])
            atual = filhos[0]
        else:  # L -> item
            itens.append(filhos[0])
            break
    itens.reverse()
    return itens


def _lexema_tipo(no_tipo: NoArvore) -> str:
    """'tipo -> INT | FLOAT | STR | BOOL' -> 'int', 'float', 'str' ou 'bool'."""
    return no_tipo.filhos[0].token.lexema


def construir_ast(arvore: NoArvore) -> Programa:
    """
    Converte a árvore sintática de um programa aceito em AST.

    Pré-condição: a análise sintática terminou sem erros, ou seja, a árvore
    não contém nós-marcadores de recuperação.
    """
    # programa -> lista_funcoes
    lista = arvore.filhos[0]
    funcoes = [_funcao(f) for f in _achatar_lista(lista)]
    return Programa(**_pos(arvore), funcoes=funcoes)


# -- Funções ------------------------------------------------------------------


def _funcao(no: NoArvore) -> Funcao:
    # funcao -> FUNC nome_funcao ( parametros ) tipo_retorno bloco
    _, nome_funcao, _, parametros, _, tipo_retorno, bloco = no.filhos
    nome = nome_funcao.filhos[0].token.lexema

    params = []
    if parametros.filhos:  # parametros -> lista_params | ε
        for p in _achatar_lista(parametros.filhos[0]):
            # param -> tipo IDENTIFICADOR
            tipo, ident = p.filhos
            params.append(Param(**_pos(p), tipo_param=_lexema_tipo(tipo),
                                nome=ident.token.lexema))

    retorno = None
    if tipo_retorno.filhos:  # tipo_retorno -> : tipo | ε
        retorno = _lexema_tipo(tipo_retorno.filhos[1])

    return Funcao(**_pos(no), nome=nome, params=params,
                  tipo_retorno=retorno, corpo=_bloco(bloco))


def _bloco(no: NoArvore) -> Bloco:
    # bloco -> { lista_comandos }
    return Bloco(**_pos(no), comandos=_comandos(no.filhos[1]))


def _comandos(lista_comandos: NoArvore) -> list[No]:
    return [_comando(c) for c in _achatar_lista(lista_comandos)]


# -- Comandos -----------------------------------------------------------------


def _comando(no: NoArvore) -> No:
    # comando -> X ; | cmd_if | cmd_while | cmd_for | cmd_switch | BREAK ;
    filho = no.filhos[0]
    s = filho.simbolo
    if s == "declaracao":
        return _declaracao(filho)
    if s == "atribuicao":
        return _atribuicao(filho)
    if s == "chamada":
        return _chamada(filho)
    if s == "retorno":
        # retorno -> RETURN expressao | RETURN
        expr = _expr(filho.filhos[1]) if len(filho.filhos) == 2 else None
        return Return(**_pos(filho), expr=expr)
    if s == "cmd_if":
        return _if(filho)
    if s == "cmd_while":
        # cmd_while -> WHILE ( expressao ) bloco
        return While(**_pos(filho), cond=_expr(filho.filhos[2]),
                     corpo=_bloco(filho.filhos[4]))
    if s == "cmd_for":
        return _for(filho)
    if s == "cmd_switch":
        return _switch(filho)
    if s == "BREAK":
        return Break(**_pos(filho))
    raise ValueError(f"comando inesperado na árvore sintática: {s}")


def _declaracao(no: NoArvore) -> Decl:
    # declaracao -> tipo IDENTIFICADOR | tipo IDENTIFICADOR = expressao
    f = no.filhos
    expr = _expr(f[3]) if len(f) == 4 else None
    return Decl(**_pos(no), tipo_decl=_lexema_tipo(f[0]),
                nome=f[1].token.lexema, expr=expr)


def _atribuicao(no: NoArvore) -> Atrib:
    # atribuicao -> IDENTIFICADOR = expressao
    ident, _, expr = no.filhos
    return Atrib(**_pos(no), nome=ident.token.lexema, expr=_expr(expr))


def _if(no: NoArvore) -> If:
    # cmd_if -> IF ( expressao ) bloco senao ;  senao -> ELSE bloco | ε
    senao = no.filhos[5]
    bloco_senao = _bloco(senao.filhos[1]) if senao.filhos else None
    return If(**_pos(no), cond=_expr(no.filhos[2]),
              entao=_bloco(no.filhos[4]), senao=bloco_senao)


def _for(no: NoArvore) -> For:
    # cmd_for -> FOR ( for_ini ; expressao ; atribuicao ) bloco
    f = no.filhos
    ini_no = f[2].filhos[0]  # for_ini -> declaracao | atribuicao
    ini = _declaracao(ini_no) if ini_no.simbolo == "declaracao" else _atribuicao(ini_no)
    return For(**_pos(no), ini=ini, cond=_expr(f[4]),
               passo=_atribuicao(f[6]), corpo=_bloco(f[8]))


def _switch(no: NoArvore) -> Switch:
    # cmd_switch -> SWITCH ( expressao ) { lista_casos padrao }
    f = no.filhos
    casos = []
    for c in _achatar_lista(f[5]):
        # caso -> CASE expressao : lista_comandos
        casos.append(Caso(**_pos(c), valor=_expr(c.filhos[1]),
                          comandos=_comandos(c.filhos[3])))

    padrao = None
    if f[6].filhos:  # padrao -> DEFAULT : lista_comandos | ε
        padrao = Caso(**_pos(f[6]), valor=None,
                      comandos=_comandos(f[6].filhos[2]))

    return Switch(**_pos(no), expr=_expr(f[2]), casos=casos, padrao=padrao)


# -- Expressões ---------------------------------------------------------------


def _chamada(no: NoArvore) -> Chamada:
    # chamada -> nome_chamada ( argumentos ) ;  argumentos -> lista_expr | ε
    nome_chamada, _, argumentos, _ = no.filhos
    args = []
    if argumentos.filhos:
        args = [_expr(e) for e in _achatar_lista(argumentos.filhos[0])]
    return Chamada(**_pos(no), nome=nome_chamada.filhos[0].token.lexema, args=args)


def _expr(no: NoArvore) -> Expr:
    """
    Converte uma subárvore de expressão.

    Desce pela cadeia de precedência sem criar nós para as produções unitárias
    (expr_or -> expr_xor, ...). As cadeias binárias (a + b + c + ...) são
    percorridas com laço, então só o aninhamento de parênteses e de operadores
    à direita consome recursão.
    """
    # Pula produções unitárias: expressao -> expr_or, expr_or -> expr_xor, ...
    while len(no.filhos) == 1 and not no.eh_folha() and no.simbolo != "expr_prim":
        no = no.filhos[0]

    s = no.simbolo

    if s in _BINARIOS:
        # X -> X OP Y, recursivo à esquerda: coleta (op, Y) descendo pela
        # espinha esquerda e depois dobra da esquerda para a direita.
        pares = []
        atual = no
        while atual.simbolo == s and len(atual.filhos) == 3:
            pares.append((atual.filhos[1].token.lexema, atual.filhos[2]))
            atual = atual.filhos[0]
        esq = _expr(atual)
        for op, direita in reversed(pares):
            esq = Binario(linha=esq.linha, coluna=esq.coluna, op=op,
                          esq=esq, dir=_expr(direita))
        return esq

    if s in _UNARIOS:
        # X -> OP X: coleta os operadores prefixos e aplica de dentro para fora.
        ops = []
        atual = no
        while atual.simbolo == s and len(atual.filhos) == 2:
            ops.append(atual.filhos[0].token)
            atual = atual.filhos[1]
        resultado = _expr(atual)
        for tok in reversed(ops):
            resultado = Unario(linha=tok.linha, coluna=tok.coluna,
                               op=tok.lexema, operando=resultado)
        return resultado

    if s == "expr_pot":
        # expr_pot -> expr_prim OP_POTENCIA expr_un (associativa à direita)
        base, tok, expoente = no.filhos
        esq = _expr(base)
        return Binario(linha=esq.linha, coluna=esq.coluna, op=tok.token.lexema,
                       esq=esq, dir=_expr(expoente))

    if s == "expr_prim":
        return _primario(no)

    raise ValueError(f"expressão inesperada na árvore sintática: {s}")


def _primario(no: NoArvore) -> Expr:
    f = no.filhos
    primeiro = f[0]

    if primeiro.simbolo == "PAREN_ESQ":  # ( expressao ): os parênteses somem
        return _expr(f[1])
    if primeiro.simbolo == "chamada":
        return _chamada(primeiro)
    if primeiro.simbolo == "tipo":  # tipo ( expressao )
        return Conversao(**_pos(no), destino=_lexema_tipo(primeiro), expr=_expr(f[2]))

    tok = primeiro.token
    if primeiro.simbolo == "IDENTIFICADOR":
        return Var(linha=tok.linha, coluna=tok.coluna, nome=tok.lexema)

    categoria, converter = _LITERAIS[primeiro.simbolo]
    return Literal(linha=tok.linha, coluna=tok.coluna,
                   valor=converter(tok.lexema), categoria=categoria)


# ---------------------------------------------------------------------------
# Impressão da AST
# ---------------------------------------------------------------------------


def _formatar_literal(lit: Literal) -> str:
    if lit.categoria == "str":
        return f"'{lit.valor}'"
    if lit.categoria == "bool":
        return "true" if lit.valor else "false"
    return str(lit.valor)


def _rotulo(no: No) -> str:
    """Texto de uma linha que descreve o nó (sem os filhos)."""
    if isinstance(no, Programa):
        texto = "Programa"
    elif isinstance(no, Funcao):
        params = ", ".join(f"{p.tipo_param} {p.nome}" for p in no.params)
        retorno = f": {no.tipo_retorno}" if no.tipo_retorno else ""
        texto = f"Funcao {no.nome}({params}){retorno}"
    elif isinstance(no, Decl):
        texto = f"Decl {no.tipo_decl} {no.nome}"
    elif isinstance(no, Atrib):
        texto = f"Atrib {no.nome}"
    elif isinstance(no, Caso):
        texto = "Default" if no.valor is None else "Case"
    elif isinstance(no, Literal):
        texto = f"Literal {_formatar_literal(no)}"
    elif isinstance(no, Var):
        texto = f"Var {no.nome}"
    elif isinstance(no, (Binario, Unario)):
        texto = f"{type(no).__name__} {no.op}"
    elif isinstance(no, Conversao):
        texto = f"Conversao {no.destino}"
    elif isinstance(no, Chamada):
        texto = f"Chamada {no.nome}"
    else:
        texto = type(no).__name__

    if isinstance(no, Expr) and no.tipo is not None:
        texto += f"  : {no.tipo}"
    return f"{texto}  [{no.linha}:{no.coluna}]"


def _filhos(no: No) -> list:
    """
    Filhos de um nó para impressão, em ordem. Cada item é um nó ou um par
    (rótulo, nó) quando o papel do filho não é óbvio pela posição.
    """
    if isinstance(no, Programa):
        return list(no.funcoes)
    if isinstance(no, Funcao):
        return [no.corpo]
    if isinstance(no, Bloco):
        return list(no.comandos)
    if isinstance(no, (Decl, Atrib, Return)):
        return [no.expr] if no.expr is not None else []
    if isinstance(no, If):
        filhos = [("cond", no.cond), ("então", no.entao)]
        if no.senao is not None:
            filhos.append(("senão", no.senao))
        return filhos
    if isinstance(no, While):
        return [("cond", no.cond), ("corpo", no.corpo)]
    if isinstance(no, For):
        return [("ini", no.ini), ("cond", no.cond), ("passo", no.passo),
                ("corpo", no.corpo)]
    if isinstance(no, Switch):
        filhos = [("expr", no.expr), *no.casos]
        if no.padrao is not None:
            filhos.append(no.padrao)
        return filhos
    if isinstance(no, Caso):
        valor = [("valor", no.valor)] if no.valor is not None else []
        return valor + list(no.comandos)
    if isinstance(no, Binario):
        return [no.esq, no.dir]
    if isinstance(no, (Unario, Conversao)):
        return [no.operando if isinstance(no, Unario) else no.expr]
    if isinstance(no, Chamada):
        return list(no.args)
    return []


def formatar_ast(raiz: No) -> list[str]:
    """
    Serializa a AST em linhas indentadas (pré-ordem).

    Iterativa, com pilha explícita, como a impressão da árvore sintática
    (docs/DECISOES.md #8).
    """
    linhas: list[str] = []
    pilha = [(raiz, "", "")]  # (nó, indentação, rótulo do papel)
    while pilha:
        no, pref, papel = pilha.pop()
        prefixo_papel = f"{papel}: " if papel else ""
        linhas.append(pref + prefixo_papel + _rotulo(no))
        for item in reversed(_filhos(no)):
            if isinstance(item, tuple):
                pilha.append((item[1], pref + "  ", item[0]))
            else:
                pilha.append((item, pref + "  ", ""))
    return linhas
