"""
semantico.py - Analisador semântico da linguagem Arjanov

Implementa as seções 3 a 7 de docs/Especificacao_Semantica_Arjanov_v2.pdf
(Versão B, docs/DECISOES.md #10) sobre a AST de arvore.py.

Duas passadas:
  1. Cadastro das funções: assinaturas, E08, E16, E17, E18, E24.
  2. Corpos: escopos, tipos das expressões, comandos e chamadas
     (E01-E07, E09-E15, E19-E23, E25, E26, W02).
  Ao final, W01 pelo grafo de chamadas a partir da main.

Efeitos sobre a AST: o campo 'tipo' de todo nó de expressão é preenchido, e
o 'tipo_destino' de cada Atrib recebe o tipo da variável atribuída.
O gerador de código deduz as conversões implícitas (int -> float) comparando
o tipo de cada expressão com o tipo esperado no contexto.

Erros são acumulados, não interrompem a análise (docs/DECISOES.md #2). Uma
expressão com erro recebe o tipo 'indefinido', compatível com tudo, para
evitar cascatas. Os diagnósticos são impressos ordenados por linha e coluna
(docs/DECISOES.md #17).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from arvore import (
    Atrib, Binario, Bloco, Break, Caso, Chamada, Conversao, Decl, Expr, For,
    Funcao, If, Literal, No, Programa, Return, Switch, Unario, Var, While,
)


# ---------------------------------------------------------------------------
# Tipos (seção 3)
# ---------------------------------------------------------------------------

INT = "int"
FLOAT = "float"
STR = "str"
BOOL = "bool"
VAZIO = "vazio"            # retorno de procedimento; não pode estar em expressão
INDEFINIDO = "indefinido"  # expressão que já teve erro; compatível com tudo

NUMERICOS = (INT, FLOAT)

OPS_ARITMETICOS = ("+", "-", "*", "^")
OPS_ORDEM = ("<", ">", "<=", ">=")
OPS_IGUALDADE = ("==", "!=")
OPS_LOGICOS = ("AND", "OR", "XOR", "XNOR")


def compativel(destino: str, origem: str) -> bool:
    """Tabela de compatibilidade de atribuição (seção 3).

    Vale para atribuição, inicialização, passagem de argumento e return.
    """
    if INDEFINIDO in (destino, origem):
        return True
    return destino == origem or (destino == FLOAT and origem == INT)


def precisa_widen(destino: str, origem: str) -> bool:
    """True se um valor 'origem' precisa de inttofloat para caber em 'destino'."""
    return destino == FLOAT and origem == INT


# ---------------------------------------------------------------------------
# Diagnósticos
# ---------------------------------------------------------------------------


@dataclass
class Diagnostico:
    """Erro (E01-E26) ou aviso (W01-W02) semântico."""

    codigo: str
    mensagem: str
    linha: int
    coluna: int

    @property
    def eh_aviso(self) -> bool:
        return self.codigo.startswith("W")

    def __str__(self) -> str:
        fase = "Aviso Semântico" if self.eh_aviso else "Erro Semântico"
        return f"[{fase}] Linha {self.linha}, Coluna {self.coluna}: {self.mensagem}"


# ---------------------------------------------------------------------------
# Tabelas de símbolos (seção 4)
# ---------------------------------------------------------------------------


@dataclass
class SimboloFuncao:
    nome: str
    params: list[tuple[str, str]]  # (tipo, nome)
    retorno: str                   # tipo declarado, ou VAZIO para procedimento
    linha: int
    coluna: int

    def assinatura(self) -> str:
        params = ", ".join(f"{t} {n}" for t, n in self.params)
        retorno = "" if self.retorno == VAZIO else f": {self.retorno}"
        return f"{self.nome}({params}){retorno}"


@dataclass
class SimboloVariavel:
    nome: str
    tipo: str
    linha: int
    coluna: int
    parametro: bool = False


@dataclass
class Escopo:
    """Um dicionário de variáveis. 'descricao' e 'profundidade' servem à
    impressão da tabela (--tabela); os escopos fechados são preservados."""

    descricao: str
    profundidade: int
    simbolos: dict[str, SimboloVariavel] = field(default_factory=dict)


@dataclass
class ResultadoSemantico:
    erros: list[Diagnostico] = field(default_factory=list)
    avisos: list[Diagnostico] = field(default_factory=list)
    funcoes: dict[str, SimboloFuncao] = field(default_factory=dict)
    # Por função (na ordem do fonte): todos os escopos abertos, em ordem.
    escopos: list[tuple[str, list[Escopo]]] = field(default_factory=list)

    def diagnosticos(self) -> list[Diagnostico]:
        """Erros e avisos juntos, ordenados por posição (decisão #17)."""
        return sorted(self.erros + self.avisos, key=lambda d: (d.linha, d.coluna))


# ---------------------------------------------------------------------------
# Analisador
# ---------------------------------------------------------------------------


class AnalisadorSemantico:
    def __init__(self, programa: Programa):
        self.programa = programa
        self.res = ResultadoSemantico()

        # Estado da função em análise (passada 2)
        self.funcao: Optional[Funcao] = None
        self.retorno_atual: str = VAZIO
        self.pilha: list[Escopo] = []
        self.historico: list[Escopo] = []
        self.quebraveis = 0  # profundidade de while/for/switch (para E25)

        # Grafo de chamadas para W01: nome -> nomes chamados
        self.chamadas: dict[str, set[str]] = {}

    # -- utilidades -----------------------------------------------------------

    def _diag(self, codigo: str, mensagem: str, no: No):
        d = Diagnostico(codigo, mensagem, no.linha, no.coluna)
        (self.res.avisos if d.eh_aviso else self.res.erros).append(d)

    # -- ponto de entrada -----------------------------------------------------

    def analisar(self) -> ResultadoSemantico:
        self._cadastrar_funcoes()
        for f in self.programa.funcoes:
            self._analisar_funcao(f)
        self._verificar_alcancabilidade()
        return self.res

    # -- passada 1: cadastro das funções (seção 5) ----------------------------

    def _cadastrar_funcoes(self):
        funcoes = self.res.funcoes
        for f in self.programa.funcoes:
            if f.nome in funcoes:
                anterior = funcoes[f.nome]
                self._diag("E08", f"função '{f.nome}' já definida na linha {anterior.linha}", f)
                continue

            vistos = set()
            for p in f.params:
                if p.nome in vistos:
                    self._diag("E24", f"parâmetro '{p.nome}' repetido em '{f.nome}'", p)
                vistos.add(p.nome)

            funcoes[f.nome] = SimboloFuncao(
                nome=f.nome,
                params=[(p.tipo_param, p.nome) for p in f.params],
                retorno=f.tipo_retorno or VAZIO,
                linha=f.linha,
                coluna=f.coluna,
            )

            if f.nome == "main":
                if f.params:
                    self._diag("E17", "main não pode ter parâmetros", f)
                if f.tipo_retorno not in (None, INT):
                    self._diag("E18", "main deve retornar int ou não declarar retorno", f)

        if "main" not in funcoes:
            self._diag("E16", "programa sem função main", self.programa)

    # -- escopos (seção 4) ----------------------------------------------------

    def _abrir_escopo(self, descricao: str):
        escopo = Escopo(descricao, len(self.pilha))
        self.pilha.append(escopo)
        self.historico.append(escopo)

    def _fechar_escopo(self):
        self.pilha.pop()

    def _buscar(self, nome: str) -> Optional[SimboloVariavel]:
        for escopo in reversed(self.pilha):
            if nome in escopo.simbolos:
                return escopo.simbolos[nome]
        return None

    def _declarar(self, nome: str, tipo: str, no: No, parametro: bool = False):
        atual = self.pilha[-1]
        if nome in atual.simbolos:
            anterior = atual.simbolos[nome]
            if not parametro:  # parâmetro repetido já foi reportado como E24
                self._diag("E02", f"variável '{nome}' já declarada neste escopo "
                                  f"(linha {anterior.linha})", no)
            return
        for escopo in reversed(self.pilha[:-1]):
            if nome in escopo.simbolos:
                anterior = escopo.simbolos[nome]
                self._diag("E03", f"declaração de '{nome}' oculta a declaração "
                                  f"visível da linha {anterior.linha}", no)
                break
        atual.simbolos[nome] = SimboloVariavel(nome, tipo, no.linha, no.coluna, parametro)

    # -- passada 2: corpos ----------------------------------------------------

    def _analisar_funcao(self, f: Funcao):
        self.funcao = f
        self.retorno_atual = f.tipo_retorno or VAZIO
        self.pilha = []
        self.historico = []
        self.quebraveis = 0
        self.chamadas.setdefault(f.nome, set())

        # Regra 1: parâmetros e corpo da função compartilham o mesmo escopo.
        self._abrir_escopo(f"função {f.nome}")
        for p in f.params:
            self._declarar(p.nome, p.tipo_param, p, parametro=True)
        for cmd in f.corpo.comandos:
            self._comando(cmd)
        self._fechar_escopo()

        if f.tipo_retorno is not None and not self._garante_retorno(f.corpo):
            self._diag("E15", f"'{f.nome}' pode terminar sem return", f)

        self.res.escopos.append((f.nome, self.historico))

    def _bloco(self, bloco: Bloco, descricao: str):
        self._abrir_escopo(descricao)
        for cmd in bloco.comandos:
            self._comando(cmd)
        self._fechar_escopo()

    def _comando(self, cmd: No):
        if isinstance(cmd, Decl):
            self._decl(cmd)
        elif isinstance(cmd, Atrib):
            self._atrib(cmd)
        elif isinstance(cmd, Chamada):
            self._expr(cmd, em_expressao=False)
        elif isinstance(cmd, Return):
            self._return(cmd)
        elif isinstance(cmd, If):
            self._condicao(cmd.cond, "if")
            self._bloco(cmd.entao, f"if (linha {cmd.linha})")
            if cmd.senao is not None:
                self._bloco(cmd.senao, f"else (linha {cmd.senao.linha})")
        elif isinstance(cmd, While):
            self._condicao(cmd.cond, "while")
            self.quebraveis += 1
            self._bloco(cmd.corpo, f"while (linha {cmd.linha})")
            self.quebraveis -= 1
        elif isinstance(cmd, For):
            self._for(cmd)
        elif isinstance(cmd, Switch):
            self._switch(cmd)
        elif isinstance(cmd, Break):
            if self.quebraveis == 0:
                self._diag("E25", "break fora de while, for ou switch", cmd)
        else:
            raise TypeError(f"comando inesperado na AST: {type(cmd).__name__}")

    def _decl(self, d: Decl):
        # Regra 5: a expressão é analisada antes de o nome entrar na tabela.
        if d.expr is not None:
            t = self._expr(d.expr)
            if not compativel(d.tipo_decl, t):
                self._diag("E04", f"não é possível atribuir {t} a '{d.nome}' "
                                  f"do tipo {d.tipo_decl}", d)
        self._declarar(d.nome, d.tipo_decl, d)

    def _atrib(self, a: Atrib):
        t = self._expr(a.expr)
        simbolo = self._buscar(a.nome)
        if simbolo is None:
            self._diag("E01", f"variável '{a.nome}' não declarada", a)
            return
        a.tipo_destino = simbolo.tipo
        if not compativel(simbolo.tipo, t):
            self._diag("E04", f"não é possível atribuir {t} a '{a.nome}' "
                              f"do tipo {simbolo.tipo}", a)

    def _condicao(self, cond: Expr, comando: str):
        t = self._expr(cond)
        if t not in (BOOL, INDEFINIDO):
            self._diag("E06", f"condição do {comando} deve ser bool, encontrado {t}", cond)

    def _for(self, f: For):
        # Regra 3: o for tem escopo próprio com ini, cond e passo; o bloco é filho.
        self._abrir_escopo(f"for (linha {f.linha})")
        if isinstance(f.ini, Decl):
            self._decl(f.ini)
        else:
            self._atrib(f.ini)
        self._condicao(f.cond, "for")
        self._atrib(f.passo)
        self.quebraveis += 1
        self._bloco(f.corpo, f"corpo do for (linha {f.corpo.linha})")
        self.quebraveis -= 1
        self._fechar_escopo()

    def _return(self, r: Return):
        nome = self.funcao.nome
        if self.retorno_atual == VAZIO:
            if r.expr is not None:
                self._expr(r.expr)
                self._diag("E12", f"'{nome}' não declara tipo de retorno; "
                                  f"use return sem valor", r)
            return
        if r.expr is None:
            self._diag("E13", f"'{nome}' deve retornar um valor do tipo "
                              f"{self.retorno_atual}", r)
            return
        t = self._expr(r.expr)
        if not compativel(self.retorno_atual, t):
            self._diag("E14", f"return do tipo {t} em '{nome}', declarada como "
                              f"{self.retorno_atual}", r)

    def _garante_retorno(self, bloco: Bloco) -> bool:
        """Regra conservadora da seção 5: o último comando garante retorno se
        for um return ou um if/else cujos dois blocos garantem retorno."""
        if not bloco.comandos:
            return False
        ultimo = bloco.comandos[-1]
        if isinstance(ultimo, Return):
            return True
        if isinstance(ultimo, If) and ultimo.senao is not None:
            return self._garante_retorno(ultimo.entao) and self._garante_retorno(ultimo.senao)
        return False

    # -- switch (seção 6.5) ---------------------------------------------------

    def _switch(self, s: Switch):
        t = self._expr(s.expr)
        if t == FLOAT:
            self._diag("E20", "expressão do switch não pode ser float", s.expr)

        vistos: dict[tuple, int] = {}  # (tipo, valor) -> linha do primeiro case
        self.quebraveis += 1
        for caso in s.casos:
            constante = self._constante_case(caso.valor)
            if constante is None:
                self._diag("E21", "valor de case deve ser uma constante", caso.valor)
            else:
                tipo_c, valor, texto = constante
                caso.valor.tipo = tipo_c
                if isinstance(caso.valor, Unario):
                    caso.valor.operando.tipo = tipo_c
                if t in (INT, STR, BOOL) and tipo_c != t:
                    self._diag("E22", f"case do tipo {tipo_c} em switch do tipo {t}",
                               caso.valor)
                chave = (tipo_c, valor)
                if chave in vistos:
                    self._diag("E23", f"valor {texto} repetido em case "
                                      f"(linha {vistos[chave]})", caso.valor)
                else:
                    vistos[chave] = caso.linha
            self._lista_caso(caso, f"case (linha {caso.linha})")
        if s.padrao is not None:
            self._lista_caso(s.padrao, f"default (linha {s.padrao.linha})")
        self.quebraveis -= 1

    def _lista_caso(self, caso: Caso, descricao: str):
        # Regra 4: cada case, e o default, abre um escopo.
        self._abrir_escopo(descricao)
        for cmd in caso.comandos:
            self._comando(cmd)
        self._fechar_escopo()

    @staticmethod
    def _constante_case(e: Expr):
        """(tipo, valor, texto) se 'e' é literal ou '-' literal numérico; senão None."""
        if isinstance(e, Literal):
            if e.categoria == STR:
                return STR, e.valor, f"'{e.valor}'"
            if e.categoria == BOOL:
                return BOOL, e.valor, "true" if e.valor else "false"
            return e.categoria, e.valor, str(e.valor)
        if (isinstance(e, Unario) and e.op == "-" and isinstance(e.operando, Literal)
                and e.operando.categoria in NUMERICOS):
            v = -e.operando.valor
            return e.operando.categoria, v, str(v)
        return None

    # -- expressões (seção 6.1) -----------------------------------------------

    def _expr(self, raiz: Expr, em_expressao: bool = True) -> str:
        """
        Calcula e anota o tipo de 'raiz' e de todas as subexpressões.

        Percurso em pós-ordem com pilha explícita: a AST de 'a + b + c + ...'
        é profunda à esquerda e estouraria o limite de recursão do Python.
        'em_expressao' é False só para uma chamada usada como comando.
        """
        pilha = [(raiz, False)]
        while pilha:
            no, filhos_prontos = pilha.pop()
            if filhos_prontos:
                no.tipo = self._tipar(no, em_expressao if no is raiz else True)
                continue
            pilha.append((no, True))
            for filho in reversed(_subexpressoes(no)):
                pilha.append((filho, False))
        return raiz.tipo

    def _tipar(self, no: Expr, em_expressao: bool) -> str:
        """Tipo de um nó cujas subexpressões já foram tipadas."""
        if isinstance(no, Literal):
            return no.categoria
        if isinstance(no, Var):
            simbolo = self._buscar(no.nome)
            if simbolo is None:
                self._diag("E01", f"variável '{no.nome}' não declarada", no)
                return INDEFINIDO
            return simbolo.tipo
        if isinstance(no, Binario):
            return self._tipar_binario(no)
        if isinstance(no, Unario):
            return self._tipar_unario(no)
        if isinstance(no, Conversao):
            return self._tipar_conversao(no)
        if isinstance(no, Chamada):
            return self._tipar_chamada(no, em_expressao)
        raise TypeError(f"expressão inesperada na AST: {type(no).__name__}")

    def _tipar_binario(self, b: Binario) -> str:
        te, td, op = b.esq.tipo, b.dir.tipo, b.op

        divisao_por_zero = (op in ("/", "%") and isinstance(b.dir, Literal)
                            and b.dir.categoria in NUMERICOS and b.dir.valor == 0)

        # O W02 não acompanha um E05 no mesmo nó (decisão #21): com a operação
        # inválida o programa já é rejeitado. Com operando indefinido (erro
        # anterior) o aviso continua saindo.
        if INDEFINIDO in (te, td):
            if divisao_por_zero:
                self._diag("W02", "divisão por zero", b)
            return INDEFINIDO

        resultado = None
        ambos_numericos = te in NUMERICOS and td in NUMERICOS
        if op in OPS_ARITMETICOS or op == "/":
            if ambos_numericos:
                resultado = INT if te == td == INT else FLOAT
        elif op == "%":
            if te == td == INT:
                resultado = INT
        elif op in OPS_ORDEM:
            if ambos_numericos:
                resultado = BOOL
        elif op in OPS_IGUALDADE:
            if ambos_numericos or (te == td and te in (STR, BOOL)):
                resultado = BOOL
        elif op in OPS_LOGICOS:
            if te == td == BOOL:
                resultado = BOOL

        if resultado is None:
            self._diag("E05", f"operador '{op}' não aceita operandos {te} e {td}", b)
            return INDEFINIDO
        if divisao_por_zero:
            self._diag("W02", "divisão por zero", b)
        return resultado

    def _tipar_unario(self, u: Unario) -> str:
        t = u.operando.tipo
        if t == INDEFINIDO:
            return INDEFINIDO
        if u.op == "NOT" and t == BOOL:
            return BOOL
        if u.op in ("-", "+") and t in NUMERICOS:
            return t
        self._diag("E05", f"operador '{u.op}' não aceita operandos {t}", u)
        return INDEFINIDO

    def _tipar_conversao(self, c: Conversao) -> str:
        t = c.expr.tipo
        if c.destino in NUMERICOS and t in (INT, FLOAT, INDEFINIDO):
            return c.destino
        if t != INDEFINIDO:
            self._diag("E26", f"não é possível converter {t} para {c.destino}", c)
        return INDEFINIDO

    def _tipar_chamada(self, c: Chamada, em_expressao: bool) -> str:
        if c.nome in ("puts", "input"):
            retorno = self._tipar_primitiva(c)
        else:
            retorno = self._tipar_chamada_usuario(c)

        if retorno == VAZIO and em_expressao:
            self._diag("E11", f"'{c.nome}' não retorna valor e não pode ser usada "
                              f"em expressão", c)
            return INDEFINIDO
        return retorno

    def _tipar_primitiva(self, c: Chamada) -> str:
        if len(c.args) != 1:
            self._diag("E09", f"'{c.nome}' espera 1 argumento(s), recebeu {len(c.args)}", c)
            return VAZIO
        if c.nome == "input" and not isinstance(c.args[0], Var):
            self._diag("E19", "input exige uma variável como argumento", c)
        # puts aceita qualquer tipo não vazio; um procedimento como argumento
        # já gerou E11 ao ser tipado.
        return VAZIO

    def _tipar_chamada_usuario(self, c: Chamada) -> str:
        simbolo = self.res.funcoes.get(c.nome)
        if simbolo is None:
            self._diag("E07", f"função '{c.nome}' não declarada", c)
            return INDEFINIDO

        self.chamadas[self.funcao.nome].add(c.nome)

        esperados = len(simbolo.params)
        if len(c.args) != esperados:
            self._diag("E09", f"'{c.nome}' espera {esperados} argumento(s), "
                              f"recebeu {len(c.args)}", c)
        else:
            for i, (arg, (tipo_param, _)) in enumerate(zip(c.args, simbolo.params), 1):
                if not compativel(tipo_param, arg.tipo):
                    self._diag("E10", f"argumento {i} de '{c.nome}' deve ser "
                                      f"{tipo_param}, recebeu {arg.tipo}", arg)
        return simbolo.retorno

    # -- W01: funções nunca chamadas (seção 5) --------------------------------

    def _verificar_alcancabilidade(self):
        if "main" not in self.res.funcoes:
            return  # E16 já reportado; todas seriam inalcançáveis
        alcancadas = {"main"}
        pendentes = ["main"]
        while pendentes:
            for chamada in self.chamadas.get(pendentes.pop(), ()):
                if chamada not in alcancadas:
                    alcancadas.add(chamada)
                    pendentes.append(chamada)
        for nome, simbolo in self.res.funcoes.items():
            if nome not in alcancadas:
                d = Diagnostico("W01", f"função '{nome}' nunca é chamada",
                                simbolo.linha, simbolo.coluna)
                self.res.avisos.append(d)


def _subexpressoes(no: Expr) -> list[Expr]:
    if isinstance(no, Binario):
        return [no.esq, no.dir]
    if isinstance(no, Unario):
        return [no.operando]
    if isinstance(no, Conversao):
        return [no.expr]
    if isinstance(no, Chamada):
        return list(no.args)
    return []


def analisar(programa: Programa) -> ResultadoSemantico:
    """Atalho: executa as duas passadas sobre a AST e devolve o resultado."""
    return AnalisadorSemantico(programa).analisar()


# ---------------------------------------------------------------------------
# Impressão da tabela de símbolos (--tabela)
# ---------------------------------------------------------------------------


def formatar_tabela(res: ResultadoSemantico) -> list[str]:
    linhas = ["Funções:"]
    if not res.funcoes:
        linhas.append("  (nenhuma)")
    largura = max((len(s.assinatura()) for s in res.funcoes.values()), default=0)
    for s in res.funcoes.values():
        linhas.append(f"  {s.assinatura():<{largura}}   linha {s.linha}")

    linhas.append("")
    linhas.append("Variáveis (por função e escopo):")
    for nome, escopos in res.escopos:
        linhas.append(f"  {nome}")
        for escopo in escopos:
            recuo = "    " + "  " * escopo.profundidade
            linhas.append(f"{recuo}[{escopo.descricao}]")
            for v in escopo.simbolos.values():
                extra = "  (parâmetro)" if v.parametro else ""
                linhas.append(f"{recuo}  {v.tipo:<6} {v.nome:<16} "
                              f"{v.linha}:{v.coluna}{extra}")
    return linhas
