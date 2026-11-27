"""
tac.py - Gerador de código de três endereços (TAC) da linguagem Arjanov

Implementa as seções 8 e 9 de docs/Especificacao_Semantica_Arjanov_v3.pdf
sobre a AST já anotada com tipos pelo analisador semântico. Só deve ser
chamado para programas sem erros semânticos (avisos não impedem).

O código gerado executa sem alterações na Berti VM, a máquina virtual usada na
avaliação (docs/DECISOES.md #30 a #34).

Convenções (seção 8):
  - A primeira instrução é 'goto main': a VM começa pela primeira linha.
  - Temporários t1, t2, ... e rótulos L1, L2, ... numerados globalmente, na
    ordem de criação.
  - A memória da VM é global. As variáveis da main usam o nome do fonte; as
    demais são qualificadas com o nome da função (fat.n). Nomes que a VM ou o
    gerador interpretariam de outra forma ganham um '_' na frente (t1 -> _t1).
  - Constantes são escritas como no fonte, com as strings entre aspas duplas.
    Dobras em tempo de compilação: '-' aplicado a literal (-1) e literal int em
    contexto float (2 -> 2.0).
  - Funções são emitidas na ordem do fonte, rotuladas pelo próprio nome.

Formato da saída: rótulos na coluna zero, instruções recuadas com quatro
espaços e uma linha em branco entre funções.
"""

from __future__ import annotations

import re
import unicodedata

from arvore import (
    Atrib, Binario, Break, Chamada, Conversao, Decl, Expr, For, Funcao, If,
    Literal, No, Programa, Return, Switch, Unario, Var, While,
)
from semantico import BOOL, FLOAT, INT, NUMERICOS, ResultadoSemantico, VAZIO, precisa_widen

RECUO = "    "

VALOR_PADRAO = {"int": "0", "float": "0.0", "str": '""', "bool": "false"}

OPS_RELACIONAIS = ("<", ">", "<=", ">=", "==", "!=")

# Operadores da Arjanov com outra grafia na VM. Entre valores bool, XOR é '!='.
OP_NA_VM = {"AND": "&&", "OR": "||", "XOR": "!=", "XNOR": "!="}

# Temporários e rótulos; nomes iniciados por 'not', que a VM lê como negação
# ('x = nota' vira 'not a'); constantes lógicas; rotinas do gerador; e nomes
# que todo objeto JavaScript já tem, que quebram a memória da VM. Em '__proto__'
# e '__define...__' os dois '_' iniciais fazem parte do nome reservado: assim
# '_proto__' não casa e não é levado para o próprio '__proto__'.
_NOME_RESERVADO = re.compile(
    r"_*([tL][0-9]+|not.*|VERDADEIRO|FALSO|potencia_(int|float).*|constructor"
    r"|toString|toLocaleString|valueOf|hasOwnProperty|isPrototypeOf"
    r"|propertyIsEnumerable|__proto__|__(define|lookup)(Getter|Setter)__)")
_CONSTANTE_INT = re.compile(r"-?[0-9]+")
_TEMPORARIO = re.compile(r"t[0-9]+")

# Pilha, em vetor, que guarda as variáveis durante chamadas recursivas. O '$'
# não existe em identificadores da Arjanov, então não há colisão.
PILHA, TOPO = "$pilha", "$topo"

# A VM não tem '^'. As rotinas abaixo só são emitidas quando usadas.
# potencia_int: quadrados sucessivos; expoente negativo é 1 / b^|e|, com a
# divisão inteira da linguagem.
_POTENCIA_INT = """\
potencia_int:
    $neg = $e < 0
    ifFalse $neg goto potencia_int_1
    $e = -$e
potencia_int_1:
    $r = 1
potencia_int_2:
    ifFalse $e > 0 goto potencia_int_4
    $x = $e % 2
    ifFalse $x == 1 goto potencia_int_3
    $r = $r * $b
potencia_int_3:
    $b = $b * $b
    $e = $e / 2
    goto potencia_int_2
potencia_int_4:
    ifFalse $neg goto potencia_int_5
    $r = 1 / $r
potencia_int_5:
    return $r"""

# potencia_float: a parte inteira do expoente por quadrados sucessivos e a
# fracionária, bit a bit, por raízes quadradas (Newton). Base negativa com
# expoente fracionário não tem resultado real (0.0 / 0.0).
_POTENCIA_FLOAT = """\
potencia_float:
    $neg = $e < 0.0
    ifFalse $neg goto potencia_float_1
    $e = -$e
potencia_float_1:
    $r = 1.0
    $s = $b
    $n = floattoint($e)
    $x = inttofloat($n)
    $f = $e - $x
potencia_float_2:
    ifFalse $n > 0 goto potencia_float_4
    $x = $n % 2
    ifFalse $x == 1 goto potencia_float_3
    $r = $r * $b
potencia_float_3:
    $b = $b * $b
    $n = $n / 2
    goto potencia_float_2
potencia_float_4:
    ifFalse $f > 0.0 goto potencia_float_9
    if $s > 0.0 goto potencia_float_5
    $r = 0.0
    if $s == 0.0 goto potencia_float_9
    $r = 0.0 / 0.0
    goto potencia_float_9
potencia_float_5:
    $x = $s
    if $x > 1.0 goto potencia_float_6
    $x = 1.0
potencia_float_6:
    $y = $s / $x
    $y = $x + $y
    $y = $y / 2.0
    ifFalse $y < $x goto potencia_float_7
    $x = $y
    goto potencia_float_6
potencia_float_7:
    $s = $x
    $f = $f * 2.0
    ifFalse $f >= 1.0 goto potencia_float_8
    $r = $r * $s
    $f = $f - 1.0
potencia_float_8:
    if $f > 0.0 goto potencia_float_5
potencia_float_9:
    ifFalse $neg goto potencia_float_10
    $r = 1.0 / $r
potencia_float_10:
    return $r"""

ROTINAS = {"potencia_int": _POTENCIA_INT, "potencia_float": _POTENCIA_FLOAT}


def _proteger(nome: str) -> str:
    """Prefixa '_' se o nome tiver outro significado no TAC."""
    return "_" + nome if _NOME_RESERVADO.fullmatch(nome) else nome


def _literal_str(conteudo: str) -> str:
    """String entre aspas duplas, como a VM exige. Ela não tem escape, então
    uma aspa dupla interna vira simples, que nenhuma string Arjanov contém."""
    return '"' + conteudo.replace('"', "'") + '"'


def rotulos_das_funcoes(nomes: list[str]) -> dict[str, str]:
    """Rótulo de cada função. A VM só aceita rótulos ASCII: acentos são
    removidos, e '_' no fim desfaz uma eventual coincidência."""
    rotulos = {n: _proteger(n) for n in nomes if n.isascii()}
    usados = set(rotulos.values())
    for nome in nomes:
        if nome in rotulos:
            continue
        base = unicodedata.normalize("NFKD", nome)
        base = "".join(c for c in base if not unicodedata.combining(c))
        base = _proteger("".join(c if c.isascii() else "_" for c in base))
        while base in usados:
            base += "_"
        usados.add(base)
        rotulos[nome] = base
    return rotulos


def _alcance(programa: Programa) -> dict[str, set[str]]:
    """Funções alcançáveis a partir de cada função, pelas chamadas do corpo."""
    diretas: dict[str, set[str]] = {}
    for f in programa.funcoes:
        chamadas, pendentes = set(), [f.corpo]
        while pendentes:
            no = pendentes.pop()
            if isinstance(no, Chamada):
                chamadas.add(no.nome)
            for valor in vars(no).values():
                for filho in valor if isinstance(valor, list) else [valor]:
                    if isinstance(filho, No):
                        pendentes.append(filho)
        diretas[f.nome] = chamadas

    alcance = {}
    for nome in diretas:
        vistos, pendentes = set(), list(diretas[nome])
        while pendentes:
            g = pendentes.pop()
            if g not in vistos:
                vistos.add(g)
                pendentes.extend(diretas.get(g, ()))
        alcance[nome] = vistos
    return alcance


class GeradorTAC:
    def __init__(self, programa: Programa, semantica: ResultadoSemantico):
        self.programa = programa
        self.funcoes = semantica.funcoes
        self.linhas: list[str] = []
        self.n_temp = 0
        self.n_rotulo = 0
        self.saidas: list[str] = []  # pilha de rótulos de saída (break)
        self.rotulos = rotulos_das_funcoes([f.nome for f in programa.funcoes])
        self.alcance = _alcance(programa)
        self.funcao = ""                    # nome da função em geração
        self.escopos: list[list[str]] = []  # variáveis visíveis, por escopo
        # Endereços de expressões já calculados e ainda não consumidos.
        self.pendentes: list[dict[int, str]] = []
        self.rotinas: set[str] = set()      # rotinas de ROTINAS em uso
        self.usa_pilha = False
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

    def _var(self, nome: str, funcao: str = "") -> str:
        """Endereço de uma variável da função dada (por padrão, a atual)."""
        funcao = funcao or self.funcao
        if funcao == "main":
            return _proteger(nome)
        return f"{self.rotulos[funcao]}.{nome}"

    def _operando_simples(self, endereco: str) -> str:
        """'param' e 'return' não aceitam espaços na VM: uma string literal
        passa antes por um temporário."""
        if not endereco.startswith('"'):
            return endereco
        t = self._temp()
        self._gen(f"{t} = {endereco}")
        return t

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
        for f in self.programa.funcoes:
            self.linhas.append("")
            self._funcao(f)
        for nome in sorted(self.rotinas):
            self.linhas.append("")
            self.linhas.extend(ROTINAS[nome].splitlines())
        inicio = [f"{RECUO}{TOPO} = 0"] if self.usa_pilha else []
        return inicio + [f"{RECUO}goto main"] + self.linhas

    def _funcao(self, f: Funcao):
        self.funcao = f.nome
        self.retorno_atual = f.tipo_retorno or VAZIO
        self.linhas.append(f"{self.rotulos[f.nome]}:")
        inicio = len(self.linhas)
        self.escopos = [[self._var(p.nome) for p in f.params]]
        for cmd in f.corpo.comandos:  # mesmo escopo dos parâmetros
            self._comando(cmd)
        # Return implícito: só em procedimento cuja última instrução não é return.
        ultima = self.linhas[-1].strip() if len(self.linhas) > inicio else ""
        if f.tipo_retorno is None and not (ultima == "return" or ultima.startswith("return ")):
            self._gen("return")

    # -- comandos (seções 9.3 a 9.7) ------------------------------------------

    def _comandos(self, comandos: list[No]):
        """Comandos de um bloco interno, que abre um escopo."""
        self.escopos.append([])
        for cmd in comandos:
            self._comando(cmd)
        self.escopos.pop()

    def _comando(self, cmd: No):
        if isinstance(cmd, Decl):
            nome = self._var(cmd.nome)
            if cmd.expr is None:
                self._gen(f"{nome} = {VALOR_PADRAO[cmd.tipo_decl]}")
            else:
                a = self._expr(cmd.expr)
                self._gen(f"{nome} = {self._widen(a, cmd.expr.tipo, cmd.tipo_decl)}")
            self.escopos[-1].append(nome)
        elif isinstance(cmd, Atrib):
            self._atrib(cmd)
        elif isinstance(cmd, Chamada):
            self._expr(cmd, como_comando=True)
        elif isinstance(cmd, Return):
            if cmd.expr is None:
                self._gen("return")
            else:
                a = self._expr(cmd.expr)
                a = self._operando_simples(self._widen(a, cmd.expr.tipo, self.retorno_atual))
                self._gen(f"return {a}")
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
        self._gen(f"{self._var(a.nome)} = {self._widen(endereco, a.expr.tipo, destino)}")

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
        self.escopos.append([])  # escopo do for: contém a declaração de ini
        self._comando(f.ini)
        self._marcar(inicio)
        self._cond(f.cond, saida)
        self._comandos(f.corpo.comandos)
        self._atrib(f.passo)
        self.escopos.pop()
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

    def _expr(self, raiz: Expr, como_comando: bool = False) -> str:
        """
        Gera o código de 'raiz' e devolve seu endereço.

        Pós-ordem com pilha explícita: a AST de 'a + b + c + ...' é profunda à
        esquerda e estouraria o limite de recursão (como em semantico.py).
        'como_comando' vale só para uma chamada usada como comando.
        """
        enderecos: dict[int, str] = {}
        self.pendentes.append(enderecos)
        pilha = [(raiz, False)]
        while pilha:
            no, filhos_prontos = pilha.pop()
            if filhos_prontos:
                # Os filhos são consumidos aqui; o que resta é valor pendente.
                filhos = [enderecos.pop(id(f)) for f in _subexpressoes(no)]
                enderecos[id(no)] = self._endereco(no, filhos, como_comando and no is raiz)
                continue
            pilha.append((no, True))
            for filho in reversed(_subexpressoes(no)):
                pilha.append((filho, False))
        self.pendentes.pop()
        return enderecos[id(raiz)]

    def _endereco(self, no: Expr, filhos: list[str], como_comando: bool) -> str:
        """Endereço de um nó cujas subexpressões já foram geradas."""
        if isinstance(no, Literal):
            return _literal_str(no.lexema) if no.categoria == "str" else no.lexema
        if isinstance(no, Var):
            return self._var(no.nome)
        if isinstance(no, Binario):
            a1, a2 = self._widen_operandos(no, *filhos)
            if no.op == "^":
                return self._potencia(no.tipo, a1, a2)
            t = self._temp()
            self._gen(f"{t} = {a1} {OP_NA_VM.get(no.op, no.op)} {a2}")
            if no.op == "XNOR":
                negado = self._temp()
                self._gen(f"{negado} = !{t}")
                return negado
            return t
        if isinstance(no, Unario):
            a = filhos[0]
            if no.op == "+":
                return a
            if no.op == "-" and isinstance(no.operando, Literal):
                return f"-{no.operando.lexema}"  # dobra de constante
            t = self._temp()
            self._gen(f"{t} = {'!' if no.op == 'NOT' else '-'}{a}")
            return t
        if isinstance(no, Conversao):
            a = filhos[0]
            if no.destino == INT:
                if no.expr.tipo == FLOAT:
                    t = self._temp()
                    self._gen(f"{t} = floattoint({a})")
                    return t
                return a
            return self._widen(a, no.expr.tipo, FLOAT)
        if isinstance(no, Chamada):
            return self._chamada(no, filhos, como_comando)
        raise TypeError(f"expressão inesperada na AST: {type(no).__name__}")

    def _operandos(self, b: Binario) -> tuple[str, str]:
        """Gera os dois operandos de 'b' (esquerdo, depois direito) e os converte."""
        e1 = self._expr(b.esq)
        self.pendentes.append({id(b.esq): e1})
        e2 = self._expr(b.dir)
        self.pendentes.pop()
        return self._widen_operandos(b, e1, e2)

    def _widen_operandos(self, b: Binario, a1: str, a2: str) -> tuple[str, str]:
        te, td = b.esq.tipo, b.dir.tipo
        if te in NUMERICOS and td in NUMERICOS:
            tc = FLOAT if FLOAT in (te, td) else INT
            return self._widen(a1, te, tc), self._widen(a2, td, tc)
        return a1, a2

    def _potencia(self, tipo: str, base: str, expoente: str) -> str:
        """base ^ expoente, por chamada à rotina do tipo."""
        rotina = f"potencia_{tipo}"
        self.rotinas.add(rotina)
        self._gen(f"param {base}")
        self._gen(f"param {expoente}")
        self._gen(f"$b = {base}")
        self._gen(f"$e = {expoente}")
        t = self._temp()
        self._gen(f"{t} = call {rotina}, 2")
        return t

    # -- chamadas (seção 9.7) -------------------------------------------------

    def _chamada(self, c: Chamada, args: list[str], como_comando: bool) -> str:
        if c.nome == "input":
            self._input(c.args[0])
            return ""
        if c.nome == "puts":
            self._gen(f"print {args[0]}")
            return ""

        simbolo = self.funcoes[c.nome]
        formais = [self._var(nome, c.nome) for _, nome in simbolo.params]

        # O código dos argumentos já foi gerado; cada conversão sai logo antes
        # do param do seu argumento (docs/DECISOES.md #22).
        reais = []
        for a, arg, (tipo_param, _) in zip(args, c.args, simbolo.params):
            a = self._operando_simples(self._widen(a, arg.tipo, tipo_param))
            self._gen(f"param {a}")
            reais.append(a)

        # Chamada que pode voltar a esta função: guarda o que ela sobrescreveria.
        salvos = self._vivos() if self.funcao in self.alcance[c.nome] else []
        for v in salvos:
            self.usa_pilha = True
            self._gen(f"{PILHA}[{TOPO}] = {v}")
            self._gen(f"{TOPO} = {TOPO} + 1")

        # A VM não liga os param aos parâmetros formais: a cópia é explícita.
        # Um argumento que é um formal já copiado passa antes por um temporário.
        for i, a in enumerate(reais):
            if a in formais[:i]:
                reais[i] = self._temp()
                self._gen(f"{reais[i]} = {a}")
        for formal, a in zip(formais, reais):
            if formal != a:
                self._gen(f"{formal} = {a}")

        t = "" if como_comando else self._temp()
        prefixo = "" if como_comando else f"{t} = "
        self._gen(f"{prefixo}call {self.rotulos[c.nome]}, {len(reais)}")

        for v in reversed(salvos):
            self._gen(f"{TOPO} = {TOPO} - 1")
            self._gen(f"{v} = {PILHA}[{TOPO}]")
        return t

    def _vivos(self) -> list[str]:
        """Variáveis visíveis e temporários pendentes no ponto da chamada."""
        vivos = [v for escopo in self.escopos for v in escopo]
        for enderecos in self.pendentes:
            vivos += [a for a in enderecos.values() if _TEMPORARIO.fullmatch(a)]
        return list(dict.fromkeys(vivos))

    def _input(self, v: Var):
        """read v, mais a conversão do valor digitado para o tipo de v."""
        nome = self._var(v.nome)
        self._gen(f"read {nome}")
        if v.tipo == FLOAT:  # '2' é lido pela VM como inteiro
            self._gen(f"{nome} = inttofloat({nome})")
        elif v.tipo == BOOL:  # 'true' é lido pela VM como texto
            t1, t2 = self._temp(), self._temp()
            self._gen(f'{t1} = {nome} == "true"')
            self._gen(f"{t2} = {nome} == 1")
            self._gen(f"{nome} = {t1} || {t2}")


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
