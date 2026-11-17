# Plano de implementação — Parte 3

Roteiro para concluir o compilador Arjanov: análise semântica e geração de
código de três endereços (TAC). A referência normativa é
[`Especificacao_Semantica_Arjanov_v2.pdf`](Especificacao_Semantica_Arjanov_v2.pdf)
(a "spec"); as decisões já tomadas estão em [`DECISOES.md`](DECISOES.md).

- **Prazo de entrega:** 02/12, 23:59
- **Apresentações:** 03 e 04/12
- **Metas intermediárias:** Fases 1 a 3 até 20/11; Fase 4 até 26/11

Marque as caixas (`[x]`) no próprio commit que concluir cada item. Assim este
arquivo é sempre o retrato atual do projeto.

---

## Situação atual

| Fase | Situação |
|---|---|
| 0 — Organização do repositório | ✅ concluída |
| 1 — Léxico e gramática da Versão B | ✅ concluída |
| 2 — AST | ✅ concluída |
| 3 — Analisador semântico | ✅ concluída (interpretações a revisar, ver abaixo) |
| 4 — Gerador de TAC | ✅ concluída (interpretações a revisar, ver abaixo) |
| 5 — Integração no `main.py` | ✅ concluída |
| 6 — Testes e exemplos | ⏳ **próxima** (faltam os exemplos de erros) |
| 7 — Entrega | ⬜ a fazer |

O léxico e a gramática já estão na Versão B: 84 produções, 146 estados,
0 conflitos. `exemplos/ExemploArjanov.arj` (reescrito na nova sintaxe) é
aceito, o programa da seção 10 da spec é aceito e `exemplos/erros.arj` é
rejeitado com 1 erro léxico e 4 sintáticos.

A AST (`src/arvore.py`) é construída para todo programa sem erros léxicos e
sintáticos e pode ser vista com `--ast`. O analisador semântico
(`src/semantico.py`) cobre todos os códigos E01–E26 e W01–W02, anota o tipo de
cada expressão na AST e imprime a tabela de símbolos com `--tabela`. Os testes
rodam com `python3 -m unittest discover -s tests`. O gerador de TAC
(`src/tac.py`) reproduz exatamente o TAC da seção 10 da spec, verificado por
teste. Sem opções, o compilador imprime diagnósticos, TAC e veredito
(decisão #20); `-o saida.tac` grava o TAC em arquivo. Os módulos `token.py` e `parser.py`
foram renomeados para `tokens.py` e `sintatico.py` (decisão #16).

---

## Fase 0 — Organização ✅

- [x] `.gitignore` (caches, `.DS_Store`, `*.tac`, `.zip`, PDFs da disciplina)
- [x] Tag `parte-2` marcando o estado entregue na Parte 2
- [x] Código-fonte único em `src/` e atalho `run.py` na raiz
- [x] `docs/DECISOES.md` com as decisões #1 a #12

## Fase 1 — Léxico e gramática da Versão B ✅

Spec, seção 2 e Apêndice A. Decisão #10.

- [x] `src/token.py` (hoje `src/tokens.py`, decisão #16): novos `TokenType` `OP_NOT`, `BREAK`, `DEFAULT` e as
      palavras-chave `NOT`, `break`, `default` em `KEYWORDS`
      (o `lexer.py` não muda: `lookup_keyword` já resolve palavras reservadas)
- [x] `src/grammar.py`: transcrever as produções 0 a 83 do Apêndice A
      (novas ou alteradas: 4–6, 9, 11–13, 25, 50, 54–55, 61–64, 69–73, 83)
- [x] `src/parser.py` (hoje `src/sintatico.py`): nomes legíveis para os novos terminais nas mensagens
- [x] Validar: tabela com **146 estados e 0 conflitos**
- [x] Validar: o programa da seção 10 da spec é aceito
- [x] Atualizar `exemplos/*.arj` para a nova sintaxe (parâmetros tipados)
- [x] Atualizar o `--demo` embutido em `src/main.py`

**Pronto quando:** `python3 run.py exemplos/ExemploArjanov.arj` aceita o
exemplo reescrito e a recuperação em modo pânico continua funcionando em
`exemplos/erros.arj`. ✅

Notas: `exemplos/erros.arj` não precisou mudar (só tem `main()` sem
parâmetros). O novo `ExemploArjanov.arj` já foi escrito para ser válido
também nas regras semânticas (sem sombreamento, toda função chamada a partir
da `main`, `return` em todos os caminhos), para servir de teste positivo nas
Fases 3 e 6. Ao copiar o programa da seção 10 do PDF, remova o caractere
form feed (`\f`) da quebra de página, senão o léxico o rejeita.

## Fase 2 — Árvore sintática abstrata ✅

Decisões #11, #13 a #16. Módulo `src/arvore.py`.

- [x] Classes de nó (`dataclasses`), cada uma com `linha` e `coluna`
      do primeiro token da construção:
      `Programa`, `Funcao`, `Param`, `Bloco`, `Decl`, `Atrib`, `If`, `While`,
      `For`, `Switch`, `Caso`, `Break`, `Return`, `Chamada`, `Binario`,
      `Unario`, `Conversao`, `Literal`, `Var`
- [x] Conversor árvore sintática → AST, achatando listas recursivas, produções
      ε e a cadeia de precedência (`expr_or → expr_xor → … → expr_prim`)
- [x] Operador exato lido do lexema do token (decisão #3)
- [x] Campo `tipo` em todo nó de expressão, preenchido pela Fase 3
- [x] Impressão da AST (opção `--ast`), iterativa como a da árvore (decisão #8)
- [x] Renomear `token.py` → `tokens.py` e `parser.py` → `sintatico.py`
      (decisão #16; necessário para usar `dataclasses`)

Guia rápido da AST para a Fase 3:

| Nó | Campos |
|---|---|
| `Programa` | `funcoes` |
| `Funcao` | `nome`, `params: list[Param]`, `tipo_retorno` (`None` = procedimento), `corpo: Bloco` |
| `Param` | `tipo_param`, `nome` |
| `Bloco` | `comandos` |
| `Decl` | `tipo_decl`, `nome`, `expr` (ou `None`) |
| `Atrib` | `nome`, `expr` |
| `If` / `While` | `cond`, `entao`, `senao` (ou `None`) / `cond`, `corpo` |
| `For` | `ini` (`Decl` ou `Atrib`), `cond`, `passo: Atrib`, `corpo` |
| `Switch` | `expr`, `casos: list[Caso]`, `padrao: Caso` (ou `None`) |
| `Caso` | `valor` (`None` no `default`), `comandos` |
| `Break` / `Return` | — / `expr` (ou `None`) |
| `Chamada` | `nome` (inclui `puts` e `input`), `args`; também aparece como comando |
| `Binario` / `Unario` | `op` (lexema: `'+'`, `'<='`, `'XNOR'`, `'NOT'`...), `esq`, `dir` / `op`, `operando` |
| `Conversao` | `destino` (`'int'`, `'float'`, `'str'`, `'bool'`), `expr` |
| `Literal` / `Var` | `valor`, `categoria` (`'int'`, `'float'`, `'str'`, `'bool'`) / `nome` |

Todo `Expr` tem `tipo` (inicialmente `None`). Parênteses não geram nó, e
`case -1:` vira `Unario('-', Literal(1))`.

## Fase 3 — Analisador semântico ✅

Spec, seções 3 a 7. Módulo `src/semantico.py`, produzindo erros no
formato `[Erro Semântico] Linha L, Coluna C: mensagem` e avisos
`[Aviso Semântico] ...`. Decisões #17 a #19.

- [x] Tipos `int`, `float`, `str`, `bool`, `vazio`, `indefinido`; tabela de
      compatibilidade e `widen` (seção 3)
- [x] Tabela de funções e pilha de escopos de variáveis (seção 4, regras 1–9)
- [x] **Passada 1 — cadastro das funções:** E08, E16, E17, E18, E24
- [x] **Passada 2 — corpos das funções:**
  - [x] expressões: E01, E05, E26, W02 (seção 6.1)
  - [x] declaração e atribuição: E02, E03, E04 (seção 6.2)
  - [x] controle e `break`: E06, E25 (seções 6.3 e 6.4)
  - [x] `switch`: E20, E21, E22, E23 (seção 6.5)
  - [x] chamadas e E/S: E07, E09, E10, E11, E19 (seção 6.6)
  - [x] retorno: E12, E13, E14, E15 (seção 6.7)
- [x] W01: grafo de chamadas e alcançabilidade a partir da `main` (seção 5)
- [x] Anotar na AST o tipo de cada expressão (as conversões implícitas são
      deduzidas pelo gerador comparando tipos; ver `precisa_widen`)
- [x] Impressão da tabela de símbolos (opção `--tabela`)

### Interpretações adotadas onde a spec é omissa (revisar)

Estão implementadas e cobertas por testes, mas podem mudar se o grupo
preferir outra leitura:

1. **Posição de cada erro** (spec: "primeiro token da construção"):
   E06/E20 na condição/expressão; E10 no argumento; E21–E23 no valor do
   `case`; E05 e W02 no início da operação (operando esquerdo); E11, E09,
   E07, E19 no nome da chamada; E12–E14 no `return`; E08, E15, E17, E18 e
   W01 no `func`; E16 na primeira linha do programa.
2. **E09 suprime E10:** com número errado de argumentos, os tipos não são
   comparados.
3. **E21 não analisa o valor:** `case x:` gera só E21, mesmo que `x` não
   exista.
4. **W01 é omitido quando há E16:** sem `main`, toda função seria
   inalcançável.
5. **Função duplicada (E08):** a primeira definição vale para as chamadas,
   mas o corpo da segunda também é analisado (com os próprios parâmetros).
6. **Após E03**, o novo nome passa a valer no escopo interno; após E02, a
   declaração original é mantida.
7. **W02** vale para divisor literal `0` e `0.0`, inclusive em `%`.

### Catálogo de erros e avisos (spec, seção 7)

| Código | Situação | Código | Situação |
|---|---|---|---|
| E01 | variável não declarada | E14 | tipo de retorno incompatível |
| E02 | redeclaração no mesmo escopo | E15 | função pode terminar sem `return` |
| E03 | sombreamento | E16 | programa sem `main` |
| E04 | atribuição com tipo incompatível | E17 | `main` com parâmetros |
| E05 | operandos inválidos para o operador | E18 | `main` com retorno diferente de `int` |
| E06 | condição não booleana | E19 | `input` sem variável |
| E07 | função não declarada | E20 | `switch` sobre tipo inválido |
| E08 | função duplicada | E21 | `case` não constante |
| E09 | número de argumentos | E22 | `case` com tipo incompatível |
| E10 | tipo de argumento | E23 | `case` repetido |
| E11 | valor vazio usado em expressão | E24 | parâmetro repetido |
| E12 | `return` com valor em procedimento | E25 | `break` fora de laço ou `switch` |
| E13 | `return` sem valor em função | E26 | conversão inválida |
| W01 | função nunca chamada | W02 | divisão por literal zero |

As mensagens exatas e exemplos de cada código estão na tabela da seção 7 da
spec; use o texto de lá.

## Fase 4 — Gerador de TAC ✅

Spec, seções 8 a 10. Módulo `src/tac.py`. Entrada: a AST anotada pelo
semântico (`tipo` em cada expressão e `tipo_destino` em cada `Atrib`).
Expressões são percorridas em pós-ordem com pilha explícita, como no
semântico. O nó `Literal` passou a guardar o `lexema` do fonte, porque a spec
manda escrever as constantes como no fonte.

- [x] Contadores globais de temporários `t1, t2, …` e rótulos `L1, L2, …`
- [x] Renomear variáveis do usuário que colidam com temporários ou rótulos
      (ex.: `t1` → `_t1`)
- [x] `widen(a, de, para)` (9.1)
- [x] Expressões (9.2): `XNOR` via `!`, menos unário com dobra de constante
- [x] Declaração e atribuição (9.3)
- [x] `cond(B, Lf)` com o caso especial da comparação única (9.4)
- [x] `if`, `while`, `for` e `break` com pilha de rótulos de saída (9.5)
- [x] `switch` com fallthrough (9.6)
- [x] Chamadas, `puts`, `input`, `return` e `return` implícito no fim de
      procedimentos (9.7)

**Pronto quando:** o programa da seção 10 gera **exatamente** o TAC impresso
na spec. ✅ (`tests/dados/secao10.arj` → `tests/dados/secao10.tac`)

### Interpretações adotadas onde a spec é omissa (revisar)

1. **Ordem de `widen` e `param` nas chamadas.** A spec escreve
   `param widen(e1, ...) ; ... ; param widen(en, ...)`, o que admite emitir
   cada `inttofloat` logo antes do seu `param`. Adotado: todas as conversões
   primeiro e depois os `param` juntos, logo antes do `call`, para que nenhuma
   instrução fique entre os `param` de uma mesma chamada. O exemplo da seção
   10 não é afetado.
2. **Renomeação com `_`** aplicada só a variáveis e parâmetros, como diz a
   spec. Uma *função* chamada `L1` geraria o rótulo `L1:`, que colide com os
   rótulos internos. Pode-se estender a regra às funções ou deixar como está,
   porque é um caso raro.
3. **Formato:** instruções recuadas com 4 espaços, rótulos na coluna zero e
   uma linha em branco entre funções. O arquivo de `-o` é gravado em UTF-8.
4. **Sem otimizações:** o `goto` que segue um `break` (código morto) é
   mantido, porque é o que os esquemas da seção 9 produzem.

## Fase 5 — Integração no `main.py` ✅

- [x] Encadear léxico → sintático → AST → semântico → TAC; cada fase só roda se
      a anterior terminar sem erros; avisos não bloqueiam
- [x] Opções `--ast`, `--tabela`, `--arvore` e `-o saida.tac`
- [x] Manter os códigos de saída: `0` aceito, `1` erros, `2` argumentos/E/S
- [x] Atualizar a seção "Uso" do `README.md`
- [x] Saída padrão: diagnósticos, TAC e veredito; árvore sintática só com
      `--arvore` (decisão #20)

## Fase 6 — Testes e exemplos (≈ 2 dias)

- [x] `exemplos/ExemploArjanov.arj`: válido e usando todas as primitivas
      (sem diagnósticos, gera TAC)
- [ ] `exemplos/erros_semanticos.arj`: um caso para cada E01–E26 e W01–W02
      exceto o E16, que vai em `exemplos/erro_sem_main.arj` (o E16 exige um
      programa sem `main`, incompatível com os casos E17 e E18)
- [ ] `tests/` com `unittest` (sem dependências externas):
  - [x] um programa pequeno por código de erro, verificando o código esperado
        (`tests/test_semantico.py`)
  - [x] comparação exata do TAC da seção 10 (`tests/test_tac.py`)
  - [x] esquemas de tradução da seção 9 (XNOR, renomeação, `widen`, `for`,
        `switch`, `return` implícito...)
  - [x] regressão: tabela SLR com 146 estados e 0 conflitos

## Fase 7 — Entrega (≈ 1 dia)

- [ ] Fechar a seção 12 da spec e atualizar o PDF se alguma decisão mudar
- [ ] Revisar o `README.md`
- [ ] Montar o `.zip` com a spec, `src/` e `exemplos/`

---

## Como continuar o desenvolvimento

1. Leia a seção correspondente da spec e as decisões em `docs/DECISOES.md`.
   Os módulos citam as decisões pelo número (ex.: `ver docs/DECISOES.md #5`).
2. Trabalhe em um branch por fase: `git switch -c fase-6-exemplos`.
3. Rode os testes e os dois exemplos antes de cada commit:
   ```sh
   python3 -m unittest discover -s tests        # deve passar
   python3 run.py exemplos/ExemploArjanov.arj   # deve aceitar
   python3 run.py exemplos/erros.arj            # deve rejeitar
   ```
4. Ao tomar uma decisão nova, acrescente uma entrada ao final de
   `DECISOES.md` (a numeração é estável: nunca renumere).
5. Marque os itens concluídos neste arquivo e abra um pull request para `main`.

### Convenções

- Python 3.9+, apenas biblioteca padrão
- Código, comentários, mensagens e commits em português
- Erros são objetos acumulados em listas, não exceções (decisão #2)
- Erros sempre com linha e coluna; os semânticos no formato
  `[Erro Semântico] Linha L, Coluna C: mensagem` (spec, seção 1)
- Commits pequenos, no imperativo ("Adiciona…", "Corrige…"), sem arquivos
  gerados (`__pycache__`, `*.tac`, `.zip`)
