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

- **Decisão:** o arquivo-fonte é lido com codificação `latin-1`. (Revisada
  pela decisão #23: UTF-8 primeiro, com `latin-1` de reserva.)
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

### #13 — Módulo da AST chamado `arvore.py`

- **Contexto:** um arquivo `src/ast.py` ocupa o nome do módulo `ast` da
  biblioteca padrão, que é importado indiretamente por `dataclasses`
  (`dataclasses` → `inspect` → `ast`). Com ele, `import dataclasses` falha.
- **Decisão:** a AST fica em `src/arvore.py`.
- **Consequências:** o nome segue o padrão em português do projeto e não há
  colisão. Ver também #16.

### #14 — Nós da AST como `dataclasses`

- **Decisão:** cada construção é uma `@dataclass` derivada de `No`, que guarda
  `linha` e `coluna`. Nós de expressão derivam de `Expr`, que acrescenta o
  campo `tipo` (fora do construtor, preenchido pela análise semântica).
- **Consequências:** menos código repetitivo e `__repr__` pronto para
  depuração. Posição e `tipo` são declarados com `compare=False`: dois nós
  são iguais quando têm a mesma estrutura, o que permite escrever testes que
  comparam a AST com uma árvore montada à mão.

### #15 — Passo do `for` como nó `Atrib`

- **Contexto:** em `for (ini; cond; passo)`, a gramática define o passo como
  uma `atribuicao`.
- **Decisão:** o nó `For` guarda o passo como um `Atrib` comum:
  `For(ini, cond, passo, corpo)`, com `ini` sendo `Decl` ou `Atrib`.
- **Consequências:** o analisador semântico e o gerador de código tratam o
  passo com a mesma rotina das atribuições.

### #16 — Nenhum módulo com nome da biblioteca padrão

- **Contexto:** os módulos de `src/` são importados pelo nome, com `src/` à
  frente da biblioteca padrão em `sys.path`. Um módulo do projeto com o mesmo
  nome de um módulo padrão o substitui para todo o processo. Na Parte 1 isso
  já acontecia com `token.py` (o `run.py` tinha um contorno), e na Fase 2
  passou a quebrar `import dataclasses`
  (`dataclasses` → `inspect` → `linecache` → `tokenize` → `token`).
- **Decisão:** `src/token.py` foi renomeado para `src/tokens.py` e
  `src/parser.py` para `src/sintatico.py` (`parser` também é um módulo
  padrão no Python 3.9). Novos módulos não devem repetir nomes da
  biblioteca padrão.
- **Consequências:** o contorno em `run.py` foi removido. O histórico dos
  arquivos é preservado pelo `git mv` (`git log --follow src/tokens.py`).

### #17 — Diagnósticos semânticos ordenados por posição

- **Contexto:** a análise semântica tem duas passadas (cadastro das funções e
  corpos) e o W01 só é calculado no fim, então a ordem de descoberta não
  segue o fonte.
- **Decisão:** erros e avisos semânticos são impressos juntos, ordenados por
  linha e coluna.
- **Consequências:** a saída acompanha a leitura do arquivo. Os objetos
  `Diagnostico` guardam o código (`E01`...`W02`) para os testes, mas a
  mensagem impressa segue o formato da spec, sem o código.

### #18 — Lista de tipos na mensagem do E05

- **Contexto:** a spec define `operador '<op>' não aceita operandos <tipos>`
  sem fixar como escrever `<tipos>`.
- **Decisão:** operadores binários listam os dois tipos ligados por "e";
  unários, o único tipo. Ex.: `operador '+' não aceita operandos str e str`,
  `operador 'NOT' não aceita operandos int`.

### #19 — Conteúdo da opção `--tabela`

- **Decisão:** imprime a tabela de funções (assinatura e linha) e, para cada
  função, todos os escopos abertos durante a análise, indentados pela
  profundidade, com as variáveis (tipo, nome, posição, marca de parâmetro).
- **Consequências:** o analisador guarda os escopos fechados em vez de
  descartá-los (`ResultadoSemantico.escopos`).

### #20 — Saída padrão do compilador

- **Contexto:** desde a Parte 2 o compilador imprimia sempre a árvore
  sintática completa, com centenas de linhas para o exemplo, e na Fase 4 o TAC
  só aparecia com `--tac`.
- **Decisão:** sem opções, o compilador imprime os erros e avisos, o código de
  três endereços (quando o programa é válido) e o veredito. A árvore sintática
  passa a sair só com `--arvore`. A opção `--tac` deixa de existir, porque o
  TAC já sai por padrão; `-o arquivo` continua gravando o TAC em arquivo.
- **Consequências:** a saída padrão mostra o produto final do compilador. As
  demais informações (`--tokens`, `--acoes`, `--arvore`, `--ast`, `--tabela`)
  ficam disponíveis para depuração e para a apresentação.

### #21 — Interpretações da Fase 3 confirmadas; W02 não acompanha o E05

- **Contexto:** a spec manda posicionar cada diagnóstico no "primeiro token da
  construção" e não define alguns casos (seções 5 e 6; ver `docs/PLANO.md`,
  Fase 3). Além disso, `k % 0.0` gerava E05 e W02 no mesmo nó.
- **Decisão:** em 2026-11-19 foram confirmadas como o código já fazia: a
  posição de cada código (o `func` em E08, E15, E17, E18 e W01; o `return` em
  E12 a E14; o nome da chamada em E07, E09, E11 e E19; a condição em E06 e
  E20; o argumento em E10; o valor do `case` em E21 a E23; o operando esquerdo
  em E05 e W02); E09 suprime E10; `case x:` gera só E21; W01 omitido quando
  há E16; em função duplicada (E08) a primeira definição vale nas chamadas e o
  corpo da segunda também é analisado; após E02 fica a declaração original e
  após E03 entra a nova. O W02 passa a ser emitido só quando a operação é
  válida ou quando algum operando é indefinido (erro anterior): um E05 no mesmo
  nó o suprime.
- **Consequências:** `TestInterpretacoes` fixa cada uma em teste, com a
  posição esperada calculada pelo texto do programa e não pela saída do
  compilador. `k % 0.0` passa a gerar só o E05; `int x = y / 0;` continua
  gerando E01 e W02.

### #22 — `inttofloat` intercalado com `param` nas chamadas

- **Contexto:** a seção 9.7 escreve a chamada como `e1.code ; ... ; en.code`
  seguido de `param widen(e1.addr, ...) ; ... ; param widen(en.addr, ...)`, e o
  `widen` (9.1) é quem gera o `inttofloat`. A Fase 4 emitia todos os
  `inttofloat` antes de qualquer `param`, para manter os `param` contíguos
  antes do `call`. O exemplo da seção 10 não tem conversão em argumento, então
  não distinguia as duas leituras.
- **Decisão:** em 2026-11-19 adotou-se a leitura literal da spec: o código dos
  argumentos primeiro e, em seguida, para cada argumento, o `inttofloat` (se
  houver) logo antes do seu `param`.
- **Consequências:** o TAC só muda quando um argumento não literal `int` vai
  para um parâmetro `float` e não é o primeiro: `param k`, `t3 =
  inttofloat(r)`, `param t3`, em vez de `t3 = inttofloat(r)`, `param k`,
  `param t3`. Pode haver `inttofloat` entre os `param` de uma mesma chamada.
  Se o Anexo de TAC exigir `param` contíguos, esta decisão deve ser revertida
  (a mudança está só em `GeradorTAC._emitir_chamada`).

### #23 — Leitura do arquivo-fonte: BOM descartado, UTF-8 primeiro, latin-1 de reserva

- **Contexto:** a #6 lia sempre em `latin-1`. Um arquivo UTF-8 com BOM gerava 3
  erros falsos na linha 1 e era rejeitado. Um acento dentro de uma string saía
  como `MÃ©dia` no TAC e no arquivo de `-o` (duplamente codificado), sem erro
  nenhum, e cada acento deslocava em 1 a coluna dos diagnósticos seguintes na
  mesma linha. Os exemplos e os testes eram só ASCII e não mostravam isso.
- **Decisão:** em 2026-11-19, `decodificar_fonte` (em `src/main.py`) descarta o
  BOM UTF-8, se houver, e lê como UTF-8. Se o arquivo não for UTF-8 válido, lê
  como `latin-1`, que decodifica qualquer sequência de bytes e mantém a
  garantia da #6 de que a leitura nunca falha por codificação.
- **Consequências:** strings com acento saem certas no TAC, as colunas contam
  caracteres e arquivos em `latin-1` continuam aceitos (`tests/test_leitura.py`).
  Com o texto decodificado como UTF-8, o léxico, que usa `isalpha()` e
  `isalnum()` (a definição regular documentada nele é só ASCII), passa a aceitar
  letras acentuadas em identificadores (`média`), como já fazia com arquivos em
  `latin-1`. **Limitações conhecidas:** o dígito não ASCII fora de string (por
  exemplo `²`), que derrubava o compilador com `ValueError` em `arvore.py` e já
  ocorria com o byte `b2` em `latin-1`, foi tratado na decisão #24. UTF-16
  (por exemplo, arquivos gravados por `>` no PowerShell 5.1 com certas opções)
  também não é tratado.

### #24 — Dígitos do léxico são só ASCII

- **Contexto:** o léxico usava `str.isdigit()`, que aceita dígitos de outros
  alfabetos e sobrescritos. Com o fonte decodificado como UTF-8 (#23), um `²`
  fora de string virava um literal inteiro e derrubava o compilador com
  `ValueError` em `arvore.py` (`int('²')`), e um dígito como `٣` era aceito como
  número. A definição regular documentada no léxico é `digito = [0-9]`.
- **Decisão:** em 2026-11-19, `_eh_digito` (em `src/lexer.py`) aceita só `0` a
  `9`, no início do número, na parte inteira, depois do `.` e na parte
  fracionária. Qualquer outro caractere vira erro léxico ("Caractere não
  reconhecido"). Letras acentuadas em identificadores continuam aceitas:
  `isalpha()` e `isalnum()` não mudaram.
- **Consequências:** `int x = ²;` gera 1 erro léxico e saída 1, e `12²` vira o
  inteiro `12` seguido de um erro. Um dígito não ASCII no meio de um
  identificador (`x²`) continua aceito, porque a continuação do identificador
  usa `isalnum()`; `²x` é erro. Os testes estão em `tests/test_lexer.py` e em
  `tests/test_leitura.py`.

### #25 — Função com nome de rótulo interno: mantida como limitação conhecida

- **Contexto:** a regra do `_` (seção 8 da spec) vale só para variáveis e
  parâmetros, e funções usam o próprio nome como rótulo. Uma função chamada
  `L1` gera o rótulo `L1:` junto com o rótulo interno `L1:` de um `if` ou laço
  do mesmo TAC, e uma função `t1` tem o mesmo nome de um temporário.
- **Decisão:** em 2026-11-19 manteve-se como está. A alternativa, aplicar o `_`
  também aos nomes de função, foi descartada: exigiria uma frase na seção 8 da
  spec e o caso é raro.
- **Consequências:** um programa com uma função cujo nome case com
  `_*(t|L)[0-9]+` pode gerar TAC ambíguo (rótulos duplicados), sem erro nem
  aviso. Se for preciso depois, basta aplicar `endereco_variavel` ao rótulo da
  função e aos `call` em `src/tac.py`.

### #26 — Argumento de `input`: E09, E19 e E01

- **Contexto:** a seção 6.6 da spec diz que `input(v)` recebe "exatamente 1
  argumento (E09), que deve ser uma variável declarada (E19)". O catálogo chama
  o E19 de "input sem variável" (exemplo `input(x + 1);`) e a regra 9 da seção 4
  manda E01 para todo uso de variável não declarada. A spec não diz qual dos três
  vale para `input()`, `input(2)` e `input(zz)`.
- **Decisão:** em 2026-11-19, cada código olha uma coisa. E09: a quantidade de
  argumentos (`input()`, `input(a, b)`). E19: com um único argumento, ele não é
  uma variável (`input(2)`, `input('a')`, `input(x + 1)`, `input(g())`). E01: a
  variável escrita não existe (`input(zz)`).
- **Consequências:** `input(2, 3)` gera só E09, porque a contagem vem antes.
  `input(zz + 1)` gera E19 e E01, dois erros diferentes. `input((x))` é
  aceito: parênteses em volta de uma variável não geram E19. E09 e E19 ficam no
  nome da chamada e o E01 no nome da variável. Os testes estão em `TestInput`,
  em `tests/test_semantico.py`. Para tirar a ambiguidade do PDF, a frase da 6.6
  poderia ficar "que deve ser uma variável (E19); se não estiver declarada,
  E01" (o PDF é do grupo e a fonte dele não está no repositório).
