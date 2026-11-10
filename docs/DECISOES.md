# Registro de decisões de projeto — Compilador Arjanov

Este documento registra as decisões de projeto do compilador. A numeração é
estável: os módulos do código-fonte referenciam as entradas por número
(ex.: `ver docs/DECISOES.md #5`). Novas decisões são acrescentadas ao final.

Formato de cada entrada: **contexto**, **decisão** e **consequências**.

---

## Partes 1 e 2 — Análise léxica e sintática

### #1 — Implementação em Python, sem geradores de analisadores

- **Contexto:** o trabalho exige a construção do compilador pelo grupo.
- **Decisão:** léxico, tabela SLR(1) e parser são implementados à mão em
  Python, sem ferramentas como Lex/Yacc, PLY ou ANTLR.
- **Consequências:** o código expõe diretamente os algoritmos vistos em aula
  (autômato do léxico, CLOSURE/GOTO, FIRST/FOLLOW, ACTION/GOTO). Não há
  dependências externas além da biblioteca padrão.

### #2 — Erros acumulados, sem interromper a análise

- **Contexto:** abortar no primeiro erro torna o compilador pouco útil para
  depuração.
- **Decisão:** erros são objetos (`LexerError`, `ErroSintatico`) acumulados em
  listas, e não exceções. O léxico usa modo pânico: descarta o caractere
  inválido e continua a varredura.
- **Consequências:** todas as mensagens seguem o formato
  `[Erro <Fase>] Linha L, Coluna C: mensagem` e um único arquivo de entrada
  pode exercitar vários erros.

### #3 — GLC simplificada com terminais agrupados

- **Contexto:** o léxico classifica operadores por nível de precedência
  (`OP_ADITIVO`, `OP_RELACIONAL`, ...), e o operador específico fica no lexema.
- **Decisão:** a gramática usa esses mesmos grupos como terminais, em vez de um
  terminal por operador. O alfabeto de terminais do parser coincide com os
  nomes de `TokenType`.
- **Consequências:** a gramática e a tabela SLR ficam menores. Fases
  posteriores que precisam do operador exato (semântica, geração de código)
  devem consultar o lexema do token.

### #4 — Saída do analisador sintático

- **Decisão:** o parser produz (a) o veredito aceito/rejeitado, (b) a lista de
  erros sintáticos, (c) o traço de ações shift/reduce (opção `--acoes`) e
  (d) a árvore sintática completa.
- **Consequências:** a árvore sintática é a entrada das fases seguintes
  (ver #11).

### #5 — Recuperação de erros sintáticos em modo pânico

- **Contexto:** método clássico para parsers LR (Aho et al., "Dragão").
- **Decisão:**
  1. desempilhar estados até um estado `s` com GOTO sobre um não-terminal de
     sincronização `A`, com prioridade global `comando` → `bloco` → `funcao`;
  2. descartar tokens até um símbolo de FOLLOW(`A`) ou o fim de entrada;
  3. empilhar GOTO[`s`, `A`] com um nó marcador de erro e retomar.
- **Consequências:** sincronizar primeiro em `comando` descarta apenas o
  comando defeituoso e evita cascatas de erros espúrios. Uma guarda de
  progresso força o descarte de um token quando o erro se repete na mesma
  posição, garantindo terminação.

### #6 — Leitura do código-fonte em Latin-1

- **Decisão:** o arquivo-fonte é lido com codificação `latin-1`.
- **Consequências:** qualquer sequência de bytes é decodificável, então a
  leitura nunca falha por codificação; caracteres fora do alfabeto da
  linguagem são reportados como erro léxico.

### #7 — Literais string e o caractere `!`

- **Decisão:** strings são delimitadas por aspas simples, sem sequências de
  escape, e não podem atravessar linhas. O lexema armazenado é o conteúdo sem
  as aspas. O caractere `!` só é válido na forma `!=`; isolado, é erro léxico.
- **Consequências:** a negação lógica da linguagem é a palavra reservada `NOT`
  (ver #10), coerente com `AND`/`OR`/`XOR`.

### #8 — Impressão iterativa da árvore sintática

- **Contexto:** as listas recursivas à esquerda e a cadeia de precedência de
  expressões geram árvores profundas.
- **Decisão:** a serialização da árvore usa pilha explícita em vez de
  recursão.
- **Consequências:** programas longos não estouram o limite de recursão do
  Python.

### #9 — Token `ERRO` emitido pelo léxico

- **Contexto:** na Parte 1, uma string não terminada apenas registrava o erro,
  deslocando a sequência de tokens em relação ao fonte.
- **Decisão:** o léxico emite um token `ERRO` em cada erro léxico. Esse token
  não é símbolo da gramática: ao encontrá-lo, o parser registra o erro e
  dispara diretamente a recuperação em modo pânico (#5).
- **Consequências:** o parser mantém a sincronia posicional com o fonte e as
  mensagens apontam para a posição correta.

---

## Parte 3 — Análise semântica e código de três endereços

### #10 — Adoção da Versão B da especificação semântica

- **Contexto:** `docs/Especificacao_Semantica_Arjanov_v2.pdf` compara uma
  versão sem alterações nas Partes 1 e 2 (Versão A) com uma versão que altera
  o léxico e a gramática (Versão B).
- **Decisão:** adota-se a Versão B, confirmando os pontos da seção 12:
  - parâmetros tipados e tipo de retorno opcional (`func f(int a): int`);
  - negação lógica com a palavra reservada `NOT` e menos/mais unários;
  - conversão explícita no estilo função: `int(e)`, `float(e)`;
  - `switch` no estilo C, com `break` e `default`;
  - função com tipo de retorno que pode terminar sem `return` é erro (E15);
  - divisão inteira entre `int`, sombreamento proibido e `AND`/`OR` sem
    curto-circuito.
- **Consequências:** o léxico ganha três tokens (`OP_NOT`, `BREAK`,
  `DEFAULT`) e a gramática passa a ter 84 produções (Apêndice A da
  especificação). Programas no formato da Parte 2 deixam de ser aceitos, pois
  os parâmetros passam a exigir tipo.

### #11 — Árvore sintática abstrata (AST) entre o parser e as fases seguintes

- **Contexto:** a árvore sintática reflete a gramática, incluindo a cadeia de
  precedência (`expr_or` → `expr_xor` → ... → `expr_prim`), listas
  recursivas à esquerda e produções ε.
- **Decisão:** uma fase de construção converte a árvore sintática em uma AST
  com um nó por construção da linguagem (função, declaração, comandos,
  operação binária/unária, chamada, conversão, literal, variável). Cada nó
  guarda linha e coluna do primeiro token da construção.
- **Consequências:** o analisador semântico e o gerador de código trabalham
  sobre uma estrutura pequena e independente da gramática. O analisador
  semântico anota na AST o tipo de cada expressão, usado pelo gerador de
  código para inserir as conversões.

### #12 — Organização do repositório

- **Decisão:** o compilador completo fica em `src/`. O estado entregue na
  Parte 2 é preservado pela tag Git `parte-2`, em vez de uma cópia da pasta.
- **Consequências:** há uma única base de código; a versão anterior pode ser
  consultada com `git checkout parte-2`.
