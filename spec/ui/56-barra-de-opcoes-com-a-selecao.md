---
documento: Barra Opções com a seleção
requisito: pedido do revisor (2026-11-23): "o usuário tem que ter liberdade para alterar sempre que quiser, seja no momento da criação ou depois"; spec/ui 01 §4 (barra Opções)
autor: Claude Code (sessão limpa, sem acesso a _restrito/)
data: 2026-11-23
status: implementada a pedido do revisor (pontos (a)–(c) no §5)
revisor: OTTO
---

# Barra Opções com a seleção

## 1. Propósito
Até aqui a barra Opções só aparecia com uma ferramenta de criação: as características
(tipo, espessura, alturas, linha de referência…) eram escolhidas **antes** de criar. Depois
de pronto, o elemento só se editava pelo painel Propriedades. O revisor pediu (2026‑11‑23)
que a barra de características apareça também ao selecionar, para mudar a qualquer momento.

## 2. Comportamento
- Com a ferramenta **Selecionar** e algo selecionado, a barra Opções mostra as
  características da seleção, nos mesmos lugares da criação. Sem seleção, a barra
  **fica** com a dica "Selecione um elemento para ver e mudar as características dele":
  se ela sumisse e voltasse a cada clique, a vista mudaria de altura e o desenho andaria
  sob o cursor. Seleção sem campos na barra (forma livre): "Características no painel
  Propriedades".
- Cada campo mudado é uma transação (um Desfazer), feita pelos mesmos comandos do painel
  Propriedades; o painel continua igual, com o que não cabe na barra.
- **Vários selecionados da mesma classe:** os campos mostram o valor comum; quando
  diferem, a lista mostra "(vários)" e o número fica vazio com "vários". Mudar vale para
  todos, numa transação só.
- **Classes diferentes:** a barra mostra só "N elementos" e, se houver anotações, o
  estilo delas.

| Seleção | Campos na barra |
|---|---|
| Parede | Tipo, Editar tipo, Espessura, linha de referência, Base, Topo (pavimento de cima, altura fixa, até a cobertura) e a altura ou o deslocamento do topo |
| Pilar | Tipo, b × h (ou Ø), Ângulo, Base, Topo |
| Viga | Tipo, b × h, linha de referência, Topo |
| Laje | Tipo, Espessura, Deslocamento do topo |
| Cobertura | Tipo, Inclinação, Beiral, Apoio |
| Porta, janela | Tipo, Largura, Altura, Base/Peitoril, Marco (alinhamento e deslocamento) |
| Ambiente | Nome, Pé‑direito |
| Objeto | Rotação (solto), Elevação |
| Anotações | os campos do tipo (texto: altura, ângulo, alinhamento; linha: tipo; hachura: padrão, ângulo, espaçamento; cota: marcador e casas) e o **estilo** (spec/ui 55 §2) |

Elementos de outro programa (pilar, viga, laje, cobertura importados) mostram o aviso
"edite pelo painel Propriedades".

## 3. Estilo nas ferramentas (spec/ui 55 §2.3)
As ferramentas Cota, Texto, Rótulo, Linha, Curva, Círculo, Arco, Cota de raio e de
ângulo, Nível, Norte e Marcador de alteração ganham na barra Opções o estilo das próximas
anotações: fonte, altura (no Texto, a altura própria dele), negrito (N), itálico (I), cor
do texto, cor da linha e espessura; a Cota também o marcador. Vale até mudar de novo; o
conta‑gotas não o muda.

## 4. Testes
- **OB01** parede selecionada: a barra aparece; linha de referência, Base, Topo e
  Altura editam a parede; sem seleção fica só a dica (UI31 atualizado).
- **OB02** duas paredes com bases diferentes: campo vazio com "vários"; digitar vale para
  as duas.
- **OB03** pilar: ângulo e b da seção.
- **OB04** cota: marcador, fonte e espessura pela barra.
- **OB05** estilo na ferramenta Texto (negrito) e na Cota (marcador, altura) vai para o
  elemento criado.

## 5. Pontos para o revisor
- (a) A lista do §2 tem o que você mais muda? Falta algum campo na barra?
- (b) Seleção de classes diferentes: só o estilo das anotações (proposta) ou também
  camada e situação na barra?
- (c) Objeto: além de rotação e elevação, as três primeiras medidas (como na criação)?

## 6. Fontes
- Uso comum em programas de CAD/BIM: a caixa de informações mostra os ajustes do elemento
  selecionado e permite mudá‑los (ajuda pública do Archicad, "Info Box"; sem cópia de
  textos ou layout).
- Código atual do BrasBim: `ui/toolbars.py` (`OptionsBar`), `ui/properties.py`.
