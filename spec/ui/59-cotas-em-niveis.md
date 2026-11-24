---
documento: Cotas em níveis (cotagem externa e interna do pavimento)
requisito: pedido do revisor (2026-11-24): "o assistente não está fazendo cotas em mais de 1 nível. O usuário pode pedir cotas em 3 níveis, primeiro com medidas gerais, segundo considerando elementos estruturais e terceiro considerando aberturas… seguir o padrão e normas de cotas"
autor: Claude Code (sessão limpa, sem acesso a _restrito/)
data: 2026-11-24
status: proposta, aguarda revisão (§8)
revisor: OTTO
---

# Cotas em níveis

## 1. Propósito
Hoje o Assistente (e o botão Cotar) faz **uma** cota por parede: pontas e bordas dos vãos,
na face externa (spec/ui 16 §4.4). Na prática de projeto, a planta é cotada **por fachada,
em linhas paralelas**, da mais detalhada (perto do desenho) para a total (mais longe), e os
cômodos recebem cotas internas. O pedido é que o Assistente faça isso, inclusive quando o
usuário escolhe quais linhas quer ("cote em 3 níveis: total, estrutura e aberturas").

## 2. Os níveis (linhas de cota externas)
Para cada lado do edifício (fachada), linhas paralelas à fachada, de dentro para fora:

| Nível | Nome | O que mede | Pontos |
|---|---|---|---|
| 1 | **Aberturas** | vãos de portas e janelas e os trechos de parede entre eles | cantos externos da fachada, bordas de cada vão |
| 2 | **Estrutura** | pilares e paredes que chegam à fachada (eixos dos cômodos) | cantos externos, faces dos pilares (ou eixos, §8 b) e o eixo de cada parede interna que encontra a fachada |
| 3 | **Total** | a medida da fachada de ponta a ponta | os dois cantos externos |

- **Ordem**: o nível mais detalhado fica mais perto do desenho, o total mais longe, para
  que as linhas de chamada não cruzem números (uso corrente, NBR 10126 e NBR 6492 citadas
  pelo nome).
- **Espaçamento**: a primeira linha a 12 mm de papel da face externa (como hoje); entre
  linhas, 7 mm de papel. Os números seguem a altura de texto das cotas (2,5 mm).
- **Escolha dos níveis**: o usuário pode pedir só alguns ("só total e aberturas") ou
  outra ordem; a ferramenta aceita a lista de níveis. Padrão: os três.
- **Linha sem novidade não sai**: se a estrutura não acrescenta ponto em relação à de
  aberturas (ou ao total), aquela linha é pulada para não repetir a mesma medida.
- **Fachadas com recuo** (planta em L, U): cada trecho reto da face externa entra na
  linha da fachada, projetado na direção dela; o total vai de ponta a ponta da fachada.
- **Associativas**: todos os pontos presos às paredes, vãos e pilares (como a cota de
  hoje), acompanhando quando o modelo muda.

## 3. Cotas internas (nível opcional "Cômodos")
Em cada ambiente retangular, duas cotas internas (largura e profundidade, face a face das
paredes), perto da parede de baixo e da da esquerda, sem cruzar o nome do ambiente.
Pedido por "cote os cômodos" ou junto ("cote tudo").

## 4. Onde se usa
- **Assistente**: ferramenta nova `dimension_levels` (`levels`: lista entre `openings`,
  `structure`, `total`, `rooms`; `sides`: `north`, `south`, `east`, `west` ou todos;
  `storey`). As instruções da IA explicam os níveis e o padrão (três externos), e que o
  pedido do usuário manda ("cotas gerais" = total; "estrutura"/"pilares"/"eixos" =
  estrutura; "vãos"/"aberturas"/"esquadrias" = aberturas).
- **Interface**: Projeto > **Cotar pavimento…** (janela pequena com as marcas dos níveis
  e dos lados), para quem não usa o Assistente.
- Tudo numa transação (um Desfazer). Repetir não duplica: as cotas automáticas de uma
  fachada são refeitas (as que o usuário mexeu à mão ficam).

## 5. IFC
Nenhuma mudança de formato: cada linha é uma cota (`IfcAnnotation`, Pset
`BrasBim_Anotacao`), com uma marca `auto: {"side": "south", "level": "structure"}` no
estado para refazer sem duplicar.

## 6. Testes
- **CN01** casa retangular com janelas e pilares: 3 linhas por fachada, na ordem certa,
  espaçadas; total = soma da linha de aberturas.
- **CN02** só `total` e `openings`; linha de estrutura sem pontos novos é pulada.
- **CN03** planta em L: a fachada com recuo recebe os pontos dos dois trechos.
- **CN04** associativa: alongar uma parede muda as três linhas.
- **CN05** repetir não duplica; cota mexida à mão fica.
- **CN06** cômodos: largura e profundidade face a face.
- **CN07** Assistente: "cote em 3 níveis" chama `dimension_levels` com os três.

## 7. Fontes
- ABNT NBR 6492 (representação de projetos de arquitetura) e NBR 10126 (cotagem em
  desenho técnico), citadas pelo nome: cotas externas em linhas paralelas, da parcial à
  total, cotas internas dos cômodos.
- Uso corrente em escritórios e no ensino de desenho arquitetônico (comportamento geral).
- Código atual do BrasBim: `core/annotations/commands.auto_dimension_wall`,
  `core/annotations/dimensions.resolve` (pontos presos a parede, vão, pilar, viga).

## 8. Pontos para o revisor
- (a) Os três níveis e a ordem (aberturas perto, total longe) estão certos?
- (b) No nível **Estrutura**: medir as **faces** dos pilares ou os **eixos** dos pilares?
  E incluir o eixo das paredes internas que chegam à fachada (proposta: sim)?
- (c) Espaçamento 12 mm até a 1ª linha e 7 mm entre linhas (papel) serve?
- (d) Cotas internas dos cômodos entram já, ou depois?
- (e) A janela Projeto > Cotar pavimento também, ou só pelo Assistente por enquanto?
