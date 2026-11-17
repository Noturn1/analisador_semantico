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
| 2 — AST | ⏳ **próxima** (aguarda decisões pendentes) |
| 3 — Analisador semântico | ⬜ a fazer |
| 4 — Gerador de TAC | ⬜ a fazer |
| 5 — Integração no `main.py` | ⬜ a fazer |
| 6 — Testes e exemplos | ⬜ a fazer |
| 7 — Entrega | ⬜ a fazer |

O léxico e a gramática já estão na Versão B: 84 produções, 146 estados,
0 conflitos. `exemplos/ExemploArjanov.arj` (reescrito na nova sintaxe) é
aceito, o programa da seção 10 da spec é aceito e `exemplos/erros.arj` é
rejeitado com 1 erro léxico e 4 sintáticos.

### Decisões pendentes (precisam do grupo antes da Fase 2)

Cada item vira uma entrada nova em `DECISOES.md` quando for decidido.

1. **Nome do módulo da AST.** Confirmado na prática: um arquivo `src/ast.py`
   faz `import dataclasses` falhar (`dataclasses` → `inspect` → `ast` resolve
   para o nosso arquivo). Opções: `src/arvore.py` (sugerido), `src/ast_arjanov.py`,
   ou manter `ast.py` sem usar `dataclasses`/`inspect`, o que é frágil.
2. **Forma dos nós.** `dataclasses` (menos código, `__repr__` pronto) ou
   classes simples com `__init__` explícito (mais didático, sem mágica).
3. **Expressões de `for`.** O passo é uma `atribuicao`; representá-lo como nó
   `Atrib` comum (sugerido) ou como campos soltos (`var`, `expr`) dentro de
   `For`.

---

## Fase 0 — Organização ✅

- [x] `.gitignore` (caches, `.DS_Store`, `*.tac`, `.zip`, PDFs da disciplina)
- [x] Tag `parte-2` marcando o estado entregue na Parte 2
- [x] Código-fonte único em `src/` e atalho `run.py` na raiz
- [x] `docs/DECISOES.md` com as decisões #1 a #12

## Fase 1 — Léxico e gramática da Versão B ✅

Spec, seção 2 e Apêndice A. Decisão #10.

- [x] `src/token.py`: novos `TokenType` `OP_NOT`, `BREAK`, `DEFAULT` e as
      palavras-chave `NOT`, `break`, `default` em `KEYWORDS`
      (o `lexer.py` não muda: `lookup_keyword` já resolve palavras reservadas)
- [x] `src/grammar.py`: transcrever as produções 0 a 83 do Apêndice A
      (novas ou alteradas: 4–6, 9, 11–13, 25, 50, 54–55, 61–64, 69–73, 83)
- [x] `src/parser.py`: nomes legíveis para os novos terminais nas mensagens
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

## Fase 2 — Árvore sintática abstrata (≈ 1–2 dias)

Decisão #11. Novo módulo da AST; o nome depende da decisão pendente 1 acima
(`src/ast.py` colide com o módulo `ast` da biblioteca padrão).

- [ ] Classes de nó (sugestão: `dataclasses`), cada uma com `linha` e `coluna`
      do primeiro token da construção:
      `Programa`, `Funcao`, `Param`, `Bloco`, `Decl`, `Atrib`, `If`, `While`,
      `For`, `Switch`, `Caso`, `Break`, `Return`, `Chamada`, `Binario`,
      `Unario`, `Conversao`, `Literal`, `Var`
- [ ] Conversor árvore sintática → AST, achatando listas recursivas, produções
      ε e a cadeia de precedência (`expr_or → expr_xor → … → expr_prim`)
- [ ] Operador exato lido do lexema do token (decisão #3)
- [ ] Campo `tipo` em todo nó de expressão, preenchido pela Fase 3
- [ ] Impressão da AST (opção `--ast`), iterativa como a da árvore (decisão #8)

## Fase 3 — Analisador semântico (≈ 4–5 dias)

Spec, seções 3 a 7. Novo módulo `src/semantico.py`, produzindo erros no
formato `[Erro Semântico] Linha L, Coluna C: mensagem` e avisos
`[Aviso Semântico] ...`.

- [ ] Tipos `int`, `float`, `str`, `bool`, `vazio`, `indefinido`; tabela de
      compatibilidade e `widen` (seção 3)
- [ ] Tabela de funções e pilha de escopos de variáveis (seção 4, regras 1–9)
- [ ] **Passada 1 — cadastro das funções:** E08, E16, E17, E18, E24
- [ ] **Passada 2 — corpos das funções:**
  - [ ] expressões: E01, E05, E26, W02 (seção 6.1)
  - [ ] declaração e atribuição: E02, E03, E04 (seção 6.2)
  - [ ] controle e `break`: E06, E25 (seções 6.3 e 6.4)
  - [ ] `switch`: E20, E21, E22, E23 (seção 6.5)
  - [ ] chamadas e E/S: E07, E09, E10, E11, E19 (seção 6.6)
  - [ ] retorno: E12, E13, E14, E15 (seção 6.7)
- [ ] W01: grafo de chamadas e alcançabilidade a partir da `main` (seção 5)
- [ ] Anotar na AST o tipo de cada expressão e as conversões implícitas
- [ ] Impressão da tabela de símbolos (opção `--tabela`)

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

## Fase 4 — Gerador de TAC (≈ 4–5 dias)

Spec, seções 8 a 10, e o anexo de instruções da disciplina. Novo módulo
`src/tac.py`.

- [ ] Contadores globais de temporários `t1, t2, …` e rótulos `L1, L2, …`
- [ ] Renomear variáveis do usuário que colidam com temporários ou rótulos
      (ex.: `t1` → `_t1`)
- [ ] `widen(a, de, para)` (9.1)
- [ ] Expressões (9.2): `XNOR` via `!`, menos unário com dobra de constante
- [ ] Declaração e atribuição (9.3)
- [ ] `cond(B, Lf)` com o caso especial da comparação única (9.4)
- [ ] `if`, `while`, `for` e `break` com pilha de rótulos de saída (9.5)
- [ ] `switch` com fallthrough (9.6)
- [ ] Chamadas, `puts`, `input`, `return` e `return` implícito no fim de
      procedimentos (9.7)

**Pronto quando:** o programa da seção 10 gera **exatamente** o TAC impresso
na spec.

## Fase 5 — Integração no `main.py` (≈ ½ dia)

- [ ] Encadear léxico → sintático → AST → semântico → TAC; cada fase só roda se
      a anterior terminar sem erros; avisos não bloqueiam
- [ ] Opções `--ast`, `--tabela`, `--tac` e `-o saida.tac`
- [ ] Manter os códigos de saída: `0` aceito, `1` erros, `2` argumentos/E/S
- [ ] Atualizar a seção "Uso" do `README.md`

## Fase 6 — Testes e exemplos (≈ 2 dias)

- [ ] `exemplos/ExemploArjanov.arj`: válido e usando todas as primitivas
- [ ] `exemplos/erros_semanticos.arj`: um caso para cada E01–E26 e W01–W02
- [ ] `tests/` com `unittest` (sem dependências externas):
  - [ ] um programa pequeno por código de erro, verificando o código esperado
  - [ ] comparação exata do TAC da seção 10
  - [ ] regressão: tabela SLR com 146 estados e 0 conflitos

## Fase 7 — Entrega (≈ 1 dia)

- [ ] Fechar a seção 12 da spec e atualizar o PDF se alguma decisão mudar
- [ ] Revisar o `README.md`
- [ ] Montar o `.zip` com a spec, `src/` e `exemplos/`

---

## Como continuar o desenvolvimento

1. Leia a seção correspondente da spec e as decisões em `docs/DECISOES.md`.
   Os módulos citam as decisões pelo número (ex.: `ver docs/DECISOES.md #5`).
2. Trabalhe em um branch por fase: `git switch -c fase-2-ast`.
3. Rode os dois exemplos antes de cada commit:
   ```sh
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
