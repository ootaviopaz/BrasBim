---
documento: Penas por elemento e texto da cota movido
requisito: pedido do revisor (2026-11-23): "facilitar a configuração de pena nos elementos, assim como ocorre no Archicad"; "mover o texto, e somente ele, nas cotas"
autor: Claude Code (sessão limpa, sem acesso a _restrito/)
data: 2026-11-23
status: implementada com as escolhas do revisor (§6)
revisor: OTTO
---

# Penas por elemento e texto da cota movido

## 1. Propósito
Até aqui a pena vinha só da categoria (spec/ui 27): todas as paredes cortadas com a
mesma pena, todas as cotas com a mesma. Nas anotações, a spec/ui 55 deu cor e espessura
soltas. O revisor pediu a escolha **da pena** em cada elemento, como nos programas BIM: um
número da tabela, com a amostra da cor, que acompanha quando a tabela muda.

## 2. Penas de cada elemento
| Elemento | Penas |
|---|---|
| Parede, pilar, viga, laje, cobertura | **Contorno** (linhas do corte), **Hachura** (preenchimento do corte), **Vista** (linhas em vista e acima do plano) |
| Porta, janela, objeto | **Contorno** (as linhas do símbolo) |

- Cada uma é "Da tabela" (padrão: a pena da categoria) ou um número de pena (1 a 64).
- Fica no Pset `BrasBim_PenasElemento` (`Contorno`, `Hachura`, `Vista`, inteiros);
  operação `element_pens.set` (`before`/`after` `{"pens": {...}}`), com Desfazer.
- **Na planta e no PDF** a cor e a espessura vêm da tabela da janela (Exibir > Tabela de
  penas); "Imprimir em preto" continua valendo. A cor da situação (vista Projeto) vence.
- **Copiar, espelhar com cópia e dividir** levam as penas; o **conta‑gotas** também
  (inclusive "da tabela").
- **Próximas criações:** a barra Opções das ferramentas Parede, Pilar, Viga, Laje,
  Cobertura, Porta, Janela e Objeto mostra as mesmas penas; valem para o que for criado
  até mudar (da sessão, não do arquivo).

## 3. Penas das anotações
O estilo das anotações (spec/ui 55 §2.1) troca cor e espessura soltas por:
- **Pena da linha** (`pen`): linhas, marcadores (setas, pontos) — cor e espessura da pena;
- **Pena do texto** (`text_pen`): cor do texto.

Escolher a pena tira a cor solta que houver. O IFC grava a cor e a espessura da pena da
tabela do projeto (`IfcCurveStyle`, `IfcTextStyleForDefinedFont`). Arquivos feitos com a
cor solta continuam abrindo e desenhando igual.

## 4. Mover só o texto da cota
- Cada número da cota tem uma **alça** (um pouco acima do texto). Arrastar leva só aquele
  texto; a linha de cota, as chamadas e os outros números ficam.
- Fica na cota, `text_moves`: `{trecho: [ao longo, para fora]}` em metros, no sistema da
  linha de cota — o texto acompanha quando a cota muda ou é movida. Espelhar inverte o
  "para fora".
- Texto levado para longe (mais que a altura dele) ganha uma linha de chamada até o
  lugar de origem.
- Painel Propriedades: **Textos de volta ao lugar**.
- **Fantasma** (pedido do revisor, 2026‑11‑24): enquanto a alça é arrastada, a planta
  mostra na cor da pré‑visualização o texto no lugar novo e a linha de chamada que ele
  terá; a linha de cota fica como está. Ao soltar, o fantasma vira o texto
  (`SelectTool.ghost`, `PlanView._draw_ghost`; teste TC03).

## 5. Testes
- **PE01** penas da parede no IFC e na planta (só a parede escolhida); tirar uma pena;
  número inválido recusado; Desfazer/diário.
- **PE02** cópia e conta‑gotas levam as penas.
- **PE03** penas das próximas criações.
- **PE04** pena da linha e do texto da cota; a pena tira a cor solta; cor no IFC.
- **PE05** penas na barra com a seleção e na ferramenta Parede.
- **TC01** mover o texto: a linha de cota fica; chamada; espelhar; voltar ao lugar.
- **TC02** alça do número arrastada na planta.

## 6. Decisões do revisor (2026‑11‑23)
- Penas em anotações **e** elementos agora.
- Elementos com Contorno, Hachura e Vista.
- Cor e espessura soltas trocadas pela pena.

## 7. Fica para depois
- Penas por elemento nos cortes e fachadas (hoje só planta e PDF da planta).
- Hachura com pena de frente e de fundo separadas.
- Penas no tipo (padrão do tipo, com o elemento passando por cima).

## 8. Fontes
- Uso comum em programas BIM: cada elemento escolhe as penas do contorno, da hachura e
  das linhas de vista por número da tabela (ajuda pública do Archicad, Pen Sets e
  configurações de elemento; sem cópia de textos ou diálogos).
- ABNT NBR 8403 (espessuras de linha) e NBR 10126 (cotagem), citadas pelo nome.
- Código atual do BrasBim: `core/pens.py`, `core/plan.py`, `core/annotations/*`.
