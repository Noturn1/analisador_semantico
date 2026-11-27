"""
berti_vm.py - Porte, para os testes, do núcleo da Berti VM

Reproduz o reconhecimento de instruções e a execução do script.js da Berti VM
(https://github.com/phoberti/bertol-compilador-vm, licença MIT, imagem Docker
phoberti/bertol:1.0), usada pelo professor para executar o TAC. Só as
instruções que o compilador Arjanov emite foram portadas. As particularidades
da VM são mantidas de propósito: memória global, parâmetros descartados no
call, 'not' lido como negação mesmo colado no nome e um operando sem espaços
em param, return e print.
"""

import re


class ErroVM(Exception):
    pass


ARIT = {"+", "-", "*", "/", "%"}
REL = {"<", ">", "<=", ">=", "==", "!="}
LOG = {"and", "&&", "or", "||"}


def _tokens(s):
    return re.findall(r'"[^"]*"|\S+', s)


def _str(tok):
    return len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"'


def formatar(v):
    valor, tipo = v
    if tipo == "logico":
        return "VERDADEIRO" if valor else "FALSO"
    if tipo == "decimal" and valor == int(valor):
        return f"{valor:.1f}"
    return str(valor)


def _carregar(linhas):
    instrucoes, rotulos = [], {}
    for linha in (l.strip() for l in linhas):
        if not linha:
            continue
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", linha)
        if m:
            if m[1] in rotulos:
                raise ErroVM(f"rótulo repetido: {m[1]}")  # a VM não avisaria
            rotulos[m[1]] = len(instrucoes)
        else:
            instrucoes.append(_reconhecer(linha))
    return instrucoes, rotulos


def _reconhecer(linha):
    m = re.fullmatch(r'print\s+"(.*)"', linha)
    if m:
        return ("print_str", m[1])
    for nome in ("print", "read", "goto", "param"):
        m = re.fullmatch(nome + r"\s+(\S+)", linha)
        if m:
            return (nome, m[1])
    m = re.fullmatch(r"(ifFalse|if)\s+(.+?)\s+goto\s+(\S+)", linha)
    if m:
        return (m[1], _tokens(m[2]), m[3])
    m = re.fullmatch(r"return(?:\s+(\S+))?", linha)
    if m:
        return ("return", m[1])
    m = re.fullmatch(r"(?:(\S+)\s*=\s*)?call\s+(\S+?),\s*(\d+)", linha)
    if m:
        return ("call", m[1], m[2], int(m[3]))
    m = re.fullmatch(r"(\S+)\[(\S+)\]\s*=\s*(\S+)", linha)
    if m:
        return ("grava", m[1], m[2], m[3])
    m = re.fullmatch(r"(\S+)\s*=\s*(.+)", linha)
    if m:
        dest, dir_ = m[1], m[2].strip()
        partes = _tokens(dir_)
        if _str(dir_) and len(partes) == 1:
            return ("copia", dest, dir_)
        m = re.fullmatch(r"(\S+)\[(\S+)\]", dir_)
        if m:
            return ("le", dest, m[1], m[2])
        m = re.fullmatch(r"(inttofloat|floattoint)\((\S+)\)", dir_)
        if m:
            return (m[1], dest, m[2])
        m = re.fullmatch(r"(?:not|!)\s*(\S+)", dir_)
        if m:
            return ("not", dest, m[1])
        if len(partes) == 1:
            if dir_.startswith("-") and not re.fullmatch(r"-\d+(\.\d+)?", dir_):
                return ("neg", dest, dir_[1:])
            return ("copia", dest, dir_)
        if len(partes) == 3 and partes[1] in ARIT | REL | LOG:
            return ("bin", dest, *partes)
    raise ErroVM(f"instrução não reconhecida: {linha}")


def executar(linhas, entradas=(), limite=200000):
    """Executa o TAC e devolve a lista do que foi impresso."""
    instrucoes, rotulos = _carregar(linhas)
    memoria, vetores, params, pilha = {}, {}, [], []
    entradas, saida, pc = list(entradas), [], 0

    def valor(tok):
        if tok in ("true", "VERDADEIRO"):
            return (1, "logico")
        if tok in ("false", "FALSO"):
            return (0, "logico")
        if _str(tok):
            return (tok[1:-1], "texto")
        if re.fullmatch(r"-?\d+\.\d+", tok):
            return (float(tok), "decimal")
        if re.fullmatch(r"-?\d+", tok):
            return (int(tok), "inteiro")
        return memoria.setdefault(tok, (0, "inteiro"))

    def binaria(a, op, b):
        (x, tx), (y, ty) = valor(a), valor(b)
        if op in ARIT:
            dec = "decimal" in (tx, ty)
            if op in "/%" and y == 0:
                raise ErroVM("divisão por zero no teste")
            q = 0 if op not in "/%" else abs(x) // abs(y) * (1 if (x < 0) == (y < 0) else -1)
            r = {"+": lambda: x + y, "-": lambda: x - y, "*": lambda: x * y,
                 "/": lambda: x / y if dec else q, "%": lambda: x - y * q}[op]()
            return (r, "decimal" if dec else "inteiro")
        if op in REL:
            r = {"<": lambda: x < y, ">": lambda: x > y, "<=": lambda: x <= y,
                 ">=": lambda: x >= y, "==": lambda: x == y, "!=": lambda: x != y}[op]()
        else:
            r = (x and y) if op in ("and", "&&") else (x or y)
        return (1 if r else 0, "logico")

    def desvio(rotulo):
        if rotulo not in rotulos:
            raise ErroVM(f"rótulo indefinido: {rotulo}")
        return rotulos[rotulo]

    for _ in range(limite):
        if pc >= len(instrucoes):
            return saida
        op, *args = instrucoes[pc]
        pc += 1
        if op == "print_str":
            saida.append(args[0])
        elif op == "print":
            saida.append(formatar(valor(args[0])))
        elif op == "read":
            bruto = entradas.pop(0)
            lido = valor(bruto) if re.fullmatch(r"-?\d+(\.\d+)?", bruto) else (bruto, "texto")
            memoria[args[0]] = lido
        elif op == "goto":
            pc = desvio(args[0])
        elif op in ("if", "ifFalse"):
            cond = args[0]
            v = binaria(*cond) if len(cond) == 3 else valor(cond[0])
            if bool(v[0]) == (op == "if"):
                pc = desvio(args[1])
        elif op == "param":
            params.append(valor(args[0]))
        elif op == "call":
            destino, func, n = args
            del params[max(0, len(params) - n):]  # descartados, como na VM
            pilha.append((pc, destino))
            pc = desvio(func)
        elif op == "return":
            if not pilha:
                return saida
            v = valor(args[0]) if args[0] else None
            pc, destino = pilha.pop()
            if destino:
                memoria[destino] = v
        elif op == "grava":
            vetores[args[0], valor(args[1])[0]] = valor(args[2])
        elif op == "le":
            memoria[args[0]] = vetores[args[1], valor(args[2])[0]]
        elif op == "inttofloat":
            memoria[args[0]] = (float(valor(args[1])[0]), "decimal")
        elif op == "floattoint":
            memoria[args[0]] = (int(valor(args[1])[0]), "inteiro")
        elif op == "not":
            memoria[args[0]] = (0 if valor(args[1])[0] else 1, "logico")
        elif op == "neg":
            x, t = valor(args[1])
            memoria[args[0]] = (-x, t)
        elif op == "copia":
            memoria[args[0]] = valor(args[1])
        elif op == "bin":
            memoria[args[0]] = binaria(*args[1:])
    raise ErroVM("limite de instruções excedido")
