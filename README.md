# Compilador Arjanov

Compilador da linguagem Arjanov, desenvolvido para a disciplina de
Compiladores. Implementado em Python 3.9+, sem dependências externas.

## Fases

| Fase | Módulo | Situação |
|---|---|---|
| Análise léxica | `src/lexer.py`, `src/token.py` | concluída |
| Análise sintática SLR(1) | `src/grammar.py`, `src/slr.py`, `src/parser.py` | concluída |
| Análise semântica | — | em desenvolvimento |
| Geração de código de três endereços | — | em desenvolvimento |

## Uso

```sh
python3 run.py <arquivo.arj>            # analisa o arquivo
python3 run.py <arquivo.arj> --tokens   # inclui a tabela de tokens
python3 run.py <arquivo.arj> --acoes    # inclui o traço shift/reduce
python3 run.py --demo                   # analisa um programa embutido
```

Códigos de saída: `0` programa aceito, `1` erros encontrados, `2` erro de
argumentos ou de E/S.

## Estrutura

```
src/        código-fonte do compilador
exemplos/   programas de entrada em Arjanov
docs/       especificação semântica e registro de decisões (DECISOES.md)
run.py      atalho para src/main.py
```

A versão entregue na Parte 2 está marcada com a tag `parte-2`.
