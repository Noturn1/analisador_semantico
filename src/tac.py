"""
tac.py - Gerador de código de três endereços (TAC) da linguagem Arjanov

Implementa as seções 8 e 9 de docs/Especificacao_Semantica_Arjanov_v2.pdf
sobre a AST já anotada com tipos pelo analisador semântico. Só deve ser
chamado para programas sem erros semânticos (avisos não impedem).

Convenções (seção 8):
  - Temporários t1, t2, ... e rótulos L1, L2, ... numerados globalmente, na
    ordem de criação.
  - Variáveis e parâmetros usam o nome do fonte; um nome que case com
    _*(t|L)[0-9]+ ganha um '_' na frente (t1 -> _t1).
  - Constantes são escritas como no fonte. Dobras em tempo de compilação:
    '-' aplicado a literal (-1) e literal int em contexto float (2 -> 2.0).
  - Funções são emitidas na ordem do fonte, rotuladas pelo próprio nome.

Formato da saída: rótulos na coluna zero, instruções recuadas com quatro
espaços e uma linha em branco entre funções.
"""

from __future__ import annotations

import re

from arvore import (
    Atrib, Binario, Break, Chamada, Conversao, Decl, Expr, For, Funcao, If,
    Literal, No, Programa, Return, Switch, Unario, Var, While,
)
from semantico import FLOAT, INT, NUMERICOS, ResultadoSemantico, VAZIO, precisa_widen

RECUO = "    "

VALOR_PADRAO = {"int": "0", "float": "0.0", "str": "''", "bool": "false"}

OPS_RELACIONAIS = ("<", ">", "<=", ">=", "==", "!=")

_NOME_RESERVADO = re.compile(r"_*[tL][0-9]+")
_CONSTANTE_INT = re.compile(r"-?[0-9]+")


def endereco_variavel(nome: str) -> str:
    """Nome de variável no TAC: prefixa '_' se colidir com temporário/rótulo."""
    return "_" + nome if _NOME_RESERVADO.fullmatch(nome) else nome


class GeradorTAC:
    def __init__(self, programa: Programa, semantica: ResultadoSemantico):
        self.programa = programa
        self.funcoes = semantica.funcoes
        self.linhas: list[str] = []
        self.n_temp = 0
        self.n_rotulo = 0
        self.saidas: list[str] = []  # pilha de rótulos de saída (break)
        self.retorno_atual = VAZIO

    # -- utilidades -----------------------------------------------------------

    def _temp(self) -> str:
        self.n_temp += 1
        return f"t{self.n_temp}"

    def _rotulo(self) -> str:
        self.n_rotulo += 1
        return f"L{self.n_rotulo}"

    def _gen(self, instrucao: str):
        self.linhas.append(RECUO + instrucao)

    def _marcar(self, rotulo: str):
        self.linhas.append(f"{rotulo}:")

    def _widen(self, endereco: str, de: str, para: str) -> str:
        """Seção 9.1: converte 'endereco' de 'de' para 'para' (só int -> float)."""
        if not precisa_widen(para, de):
            return endereco
        if _CONSTANTE_INT.fullmatch(endereco):
            return endereco + ".0"
        t = self._temp()
        self._gen(f"{t} = inttofloat({endereco})")
        return t

    # -- programa e funções ---------------------------------------------------

    def gerar(self) -> list[str]:
        for i, f in enumerate(self.programa.funcoes):
            if i > 0:
                self.linhas.append("")
            self._funcao(f)
        return self.linhas

    def _funcao(self, f: Funcao):
        self.retorno_atual = f.tipo_retorno or VAZIO
        self.linhas.append(f"{f.nome}:")
        inicio = len(self.linhas)
        self._comandos(f.corpo.comandos)
        # Return implícito: só em procedimento cuja última instrução não é return.
        ultima = self.linhas[-1].strip() if len(self.linhas) > inicio else ""
        if f.tipo_retorno is None and not (ultima == "return" or ultima.startswith("return ")):
            self._gen("return")

    # -- comandos (seções 9.3 a 9.7) ------------------------------------------

    def _comandos(self, comandos: list[No]):
        for cmd in comandos:
            self._comando(cmd)

    def _comando(self, cmd: No):
        if isinstance(cmd, Decl):
            nome = endereco_variavel(cmd.nome)
            if cmd.expr is None:
                self._gen(f"{nome} = {VALOR_PADRAO[cmd.tipo_decl]}")
            else:
                a = self._expr(cmd.expr)
                self._gen(f"{nome} = {self._widen(a, cmd.expr.tipo, cmd.tipo_decl)}")
        elif isinstance(cmd, Atrib):
            self._atrib(cmd)
        elif isinstance(cmd, Chamada):
            self._chamada(cmd, como_comando=True)
        elif isinstance(cmd, Return):
            if cmd.expr is None:
                self._gen("return")
            else:
                a = self._expr(cmd.expr)
                self._gen(f"return {self._widen(a, cmd.expr.tipo, self.retorno_atual)}")
        elif isinstance(cmd, If):
            self._if(cmd)
        elif isinstance(cmd, While):
            inicio, saida = self._rotulo(), self._rotulo()
            self.saidas.append(saida)
            self._marcar(inicio)
            self._cond(cmd.cond, saida)
            self._comandos(cmd.corpo.comandos)
            self._gen(f"goto {inicio}")
            self._marcar(saida)
            self.saidas.pop()
        elif isinstance(cmd, For):
            self._for(cmd)
        elif isinstance(cmd, Switch):
            self._switch(cmd)
        elif isinstance(cmd, Break):
            self._gen(f"goto {self.saidas[-1]}")
        else:
            raise TypeError(f"comando inesperado na AST: {type(cmd).__name__}")

    def _atrib(self, a: Atrib):
        # Atrib.tipo_destino (tipo da variável) é anotado pelo semântico.
        endereco = self._expr(a.expr)
        destino = a.tipo_destino
        self._gen(f"{endereco_variavel(a.nome)} = {self._widen(endereco, a.expr.tipo, destino)}")

    def _if(self, s: If):
        if s.senao is None:
            fim = self._rotulo()
            self._cond(s.cond, fim)
            self._comandos(s.entao.comandos)
            self._marcar(fim)
        else:
            senao, fim = self._rotulo(), self._rotulo()
            self._cond(s.cond, senao)
            self._comandos(s.entao.comandos)
            self._gen(f"goto {fim}")
            self._marcar(senao)
            self._comandos(s.senao.comandos)
            self._marcar(fim)

    def _for(self, f: For):
        inicio, saida = self._rotulo(), self._rotulo()
        self.saidas.append(saida)
        self._comando(f.ini)
        self._marcar(inicio)
        self._cond(f.cond, saida)
        self._comandos(f.corpo.comandos)
        self._atrib(f.passo)
        self._gen(f"goto {inicio}")
        self._marcar(saida)
        self.saidas.pop()

    def _switch(self, s: Switch):
        teste, fim = self._rotulo(), self._rotulo()
        self.saidas.append(fim)
        endereco = self._expr(s.expr)
        self._gen(f"goto {teste}")

        rotulos_casos = []
        for caso in s.casos:  # corpos em sequência: fallthrough natural
            rotulo = self._rotulo()
            rotulos_casos.append(rotulo)
            self._marcar(rotulo)
            self._comandos(caso.comandos)
        rotulo_padrao = None
        if s.padrao is not None:
            rotulo_padrao = self._rotulo()
            self._marcar(rotulo_padrao)
            self._comandos(s.padrao.comandos)
        self._gen(f"goto {fim}")

        self._marcar(teste)
        for caso, rotulo in zip(s.casos, rotulos_casos):
            valor = self._expr(caso.valor)  # literal ou -literal: não gera código
            self._gen(f"if {endereco} == {valor} goto {rotulo}")
        self._gen(f"goto {rotulo_padrao or fim}")
        self._marcar(fim)
        self.saidas.pop()

    def _cond(self, b: Expr, falso: str):
        """Seção 9.4: desvia para 'falso' se a condição for falsa."""
        if isinstance(b, Binario) and b.op in OPS_RELACIONAIS:
            a1, a2 = self._operandos(b)
            self._gen(f"ifFalse {a1} {b.op} {a2} goto {falso}")
        else:
            self._gen(f"ifFalse {self._expr(b)} goto {falso}")

    # -- expressões (seção 9.2) -----------------------------------------------

    def _expr(self, raiz: Expr) -> str:
        """
        Gera o código de 'raiz' e devolve seu endereço.

        Pós-ordem com pilha explícita: a AST de 'a + b + c + ...' é profunda à
        esquerda e estouraria o limite de recursão (como em semantico.py).
        """
        enderecos: dict[int, str] = {}
        pilha = [(raiz, False)]
        while pilha:
            no, filhos_prontos = pilha.pop()
            if filhos_prontos:
                enderecos[id(no)] = self._endereco(no, enderecos)
                continue
            pilha.append((no, True))
            for filho in reversed(_subexpressoes(no)):
                pilha.append((filho, False))
        return enderecos[id(raiz)]

    def _endereco(self, no: Expr, enderecos: dict[int, str]) -> str:
        """Endereço de um nó cujas subexpressões já foram geradas."""
        if isinstance(no, Literal):
            return f"'{no.lexema}'" if no.categoria == "str" else no.lexema
        if isinstance(no, Var):
            return endereco_variavel(no.nome)
        if isinstance(no, Binario):
            a1, a2 = self._widen_operandos(no, enderecos[id(no.esq)], enderecos[id(no.dir)])
            t = self._temp()
            if no.op == "XNOR":
                self._gen(f"{t} = {a1} XOR {a2}")
                negado = self._temp()
                self._gen(f"{negado} = ! {t}")
                return negado
            self._gen(f"{t} = {a1} {no.op} {a2}")
            return t
        if isinstance(no, Unario):
            a = enderecos[id(no.operando)]
            if no.op == "+":
                return a
            if no.op == "-" and isinstance(no.operando, Literal):
                return f"-{no.operando.lexema}"  # dobra de constante
            t = self._temp()
            self._gen(f"{t} = {'!' if no.op == 'NOT' else '-'} {a}")
            return t
        if isinstance(no, Conversao):
            a = enderecos[id(no.expr)]
            if no.destino == INT:
                if no.expr.tipo == FLOAT:
                    t = self._temp()
                    self._gen(f"{t} = floattoint({a})")
                    return t
                return a
            return self._widen(a, no.expr.tipo, FLOAT)
        if isinstance(no, Chamada):
            return self._emitir_chamada(no, [enderecos[id(a)] for a in no.args],
                                        como_comando=False)
        raise TypeError(f"expressão inesperada na AST: {type(no).__name__}")

    def _operandos(self, b: Binario) -> tuple[str, str]:
        """Gera os dois operandos de 'b' (esquerdo, depois direito) e os converte."""
        e1 = self._expr(b.esq)
        e2 = self._expr(b.dir)
        return self._widen_operandos(b, e1, e2)

    def _widen_operandos(self, b: Binario, a1: str, a2: str) -> tuple[str, str]:
        te, td = b.esq.tipo, b.dir.tipo
        if te in NUMERICOS and td in NUMERICOS:
            tc = FLOAT if FLOAT in (te, td) else INT
            return self._widen(a1, te, tc), self._widen(a2, td, tc)
        return a1, a2

    # -- chamadas (seção 9.7) -------------------------------------------------

    def _chamada(self, c: Chamada, como_comando: bool) -> str:
        if c.nome == "input":
            return self._emitir_chamada(c, [], como_comando)
        enderecos = [self._expr(a) for a in c.args]
        return self._emitir_chamada(c, enderecos, como_comando)

    def _emitir_chamada(self, c: Chamada, enderecos: list[str], como_comando: bool) -> str:
        if c.nome == "input":
            # input(v): v = call input, 0
            self._gen(f"{endereco_variavel(c.args[0].nome)} = call input, 0")
            return ""
        if c.nome == "puts":
            self._gen(f"param {enderecos[0]}")
            self._gen("call puts, 1")
            return ""

        simbolo = self.funcoes[c.nome]
        # Seção 9.7: param widen(e1...) ; ... ; param widen(en...). O código dos
        # argumentos já foi gerado; cada inttofloat sai logo antes do param do
        # seu argumento (docs/DECISOES.md #22).
        for a, arg, (tipo_param, _) in zip(enderecos, c.args, simbolo.params):
            self._gen(f"param {self._widen(a, arg.tipo, tipo_param)}")
        n = len(c.args)
        if como_comando:
            self._gen(f"call {c.nome}, {n}")
            return ""
        t = self._temp()
        self._gen(f"{t} = call {c.nome}, {n}")
        return t


def _subexpressoes(no: Expr) -> list[Expr]:
    if isinstance(no, Binario):
        return [no.esq, no.dir]
    if isinstance(no, Unario):
        return [no.operando]
    if isinstance(no, Conversao):
        return [no.expr]
    if isinstance(no, Chamada) and no.nome != "input":
        return list(no.args)  # o argumento de input é destino, não valor
    return []


def gerar_tac(programa: Programa, semantica: ResultadoSemantico) -> list[str]:
    """Gera o TAC de um programa sem erros semânticos, uma instrução por linha."""
    return GeradorTAC(programa, semantica).gerar()
