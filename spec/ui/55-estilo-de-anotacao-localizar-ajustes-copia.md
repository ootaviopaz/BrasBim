---
documento: Estilo das anotações, Localizar e substituir, Pegar e aplicar ajustes, Cópia ao arrastar
requisito: pedido do revisor (2026-11-23); RF-DOC-03 (anotação); plano de barras (2026-10-29) Fase 2 itens 1 e 2
autor: Claude Code (sessão limpa, sem acesso a _restrito/)
data: 2026-11-23
status: aprovada com as propostas (respostas do revisor em 2026-11-23, §7)
revisor: OTTO
---

# Estilo das anotações, Localizar e substituir, Pegar e aplicar ajustes, Cópia ao arrastar

## 1. Propósito
Pedido do revisor em 2026‑11‑23, em quatro itens:

1. "textos, números e símbolos de cotas têm que ter a permissão de serem alterados:
   tamanho, fonte, cor, linha, inclusive o texto";
2. "um localizar com filtro, e um substituir também";
3. "o conta‑gotas, que funciona como um copiador de propriedades: aplica as
   características de algo selecionado em outro";
4. "criar semelhante: ao selecionar uma parede e apertar o Ctrl aparece um + no cursor,
   criando quantas cópias o usuário quiser, para a direção que ele quiser".

O comportamento vem do uso comum em programas de CAD/BIM, descrito em fontes públicas
(§8). Nomes, textos e ícones são do BrasBim.

## 2. Estilo das anotações

### 2.1 O que muda
Toda anotação com texto ou com linha (cota linear, de raio e de ângulo, cota de nível,
texto, etiqueta, nuvem de revisão, linha, círculo, arco, curva) ganha um **estilo** próprio,
opcional. Sem estilo, ela é desenhada como hoje (tamanhos da spec/ui 13, pena da categoria,
spec/ui 27).

| Campo | Vale para | Valores | Padrão (sem estilo) |
|---|---|---|---|
| `font` | texto | nome da família (as fontes instaladas; a lista mostra primeiro Archivo, Arial, Times New Roman, Courier New) | a da interface (Archivo) |
| `size` | texto | altura no papel, mm (lista 1,5 · 2 · 2,5 · 3 · 3,5 · 5 · 7 ou digitado, 0,5 a 50) | o do tipo (cota 2,5) |
| `bold`, `italic` | texto | sim/não | não |
| `text_color` | texto | cor `#RRGGBB` | a da pena da categoria |
| `line_color` | linhas | cor `#RRGGBB` | a da pena da categoria |
| `weight` | linhas | espessura em mm (lista da spec/ui 13 §8) | a da pena da categoria |
| `marker` | cota linear | `tick` (traço a 45°), `arrow` (seta cheia), `open_arrow` (seta aberta), `dot` (ponto), `none` | `tick` |
| `marker_size` | cota linear | mm de papel (1 a 10) | 3 |
| `decimals` | cotas | 0 a 4 | o das unidades do projeto (spec/ui 44) |

Uma cor ou espessura escolhida aqui **passa por cima da pena** (como o tipo de linha por
elemento, spec/ui 51). "Seguir a pena" volta ao padrão. Imprimir em preto (tabela de penas)
continua valendo para tudo.

### 2.2 Texto da cota
Cada medida de uma cota (cada trecho da cadeia) pode ter o texto trocado:

- `texts`: `{índice do trecho: modelo}`. O modelo é um texto livre em que `<medida>` é
  trocado pelo valor medido, que continua associativo. Exemplos: `<medida>` (padrão),
  `<medida> (var.)`, `≈ <medida>`, `VER DETALHE` (sem a medida).
- `prefix` e `suffix` para a cota toda (ex.: prefixo `L=`), aplicados a todos os trechos
  que não têm modelo próprio.
- A ficha mostra a medida real ao lado de cada texto trocado e o botão **Voltar à
  medida** (trecho ou cota toda). O texto trocado sem `<medida>` aparece na planta
  sublinhado em tracejado fino só na tela (não sai no PDF), para o usuário não esquecer
  que aquele número não acompanha mais o modelo.

### 2.3 Onde se escolhe
- **Ficha da anotação** (painel de propriedades): seção **Texto** (fonte, altura, negrito,
  itálico, cor) e **Linha** (cor, espessura, marcador). Com várias anotações selecionadas,
  os campos em comum mostram "vários" e uma escolha vale para todas, numa transação.
- **Barra Opções** das ferramentas Cota, Texto e Etiqueta: o mesmo estilo, que vale para
  as próximas criadas (ajustes da ferramenta).
- **Clique duplo num número da cota**: edita o texto daquele trecho no lugar (como o
  clique duplo no texto, spec/ui 13 §6).

### 2.4 IFC
- Estado no Pset `BrasBim_Anotacao` (`Parametros`, JSON), chave `style` (só os campos
  escolhidos) e, na cota, `texts`, `prefix`, `suffix`.
- Geometria derivada: `IfcTextStyle` com `IfcTextStyleFontModel` (`FontFamily` = a fonte
  e `sans-serif`, `FontStyle` `italic`/`normal`, `FontWeight` `bold`/`normal`, `FontSize`)
  e `IfcTextStyleForDefinedFont` com a cor; `IfcCurveStyle` com cor e espessura; os
  marcadores como traços (`tick`, `open_arrow`) ou `IfcAnnotationFillArea` (`arrow`,
  `dot`). O texto gravado no `IfcTextLiteralWithExtent` é o texto mostrado.
- Operação: a `<prefixo>.edit` que já existe (campos alterados).

## 3. Localizar e substituir

### 3.1 Localizar
Janela não modal **Localizar**, no menu Editar e no atalho Ctrl+Shift+F (o Ctrl+F é da busca no Navegador, spec/ui 53).

- **Critérios**: linhas "campo · condição · valor", ligadas por **E**. O campo Classe
  aceita várias classes, ligadas por **OU**.
- **Campos**: Classe (Parede, Porta, Janela, Laje, Pilar, Viga, Cobertura, Objeto,
  Ambiente, Cota, Texto… com a classe IFC entre parênteses), Tipo, Nome, Código
  (`Reference`), Camada, Situação, Material, Pavimento, Texto da anotação e **Propriedade**
  (qualquer `Pset.Propriedade` do elemento ou do tipo, digitada ou escolhida da lista do
  que existe no projeto) e as **Quantidades** (comprimento, área, volume, altura).
- **Condições**: é, não é, contém, não contém, começa com, (números) =, ≠, <, ≤, >, ≥,
  entre, e "tem/não tem valor".
- **Onde**: pavimento atual (padrão) ou todos os pavimentos. Elementos ocultos ou
  travados pelas camadas ficam de fora, com uma marca para incluí‑los.
- **Botões**: **Selecionar** (troca a seleção), **Somar à seleção** e **Tirar da
  seleção**. A janela mostra quantos foram achados ("12 elementos, 3 pavimentos").
- **Pegar da seleção**: preenche os critérios com os valores do elemento selecionado
  (classe, tipo, camada), para refinar a partir dele.
- **Critérios salvos**: com nome, no projeto (Pset `BrasBim_Criterios` do `IfcProject`,
  operação `criteria.edit`). A lista aparece no topo da janela. Servirão depois para as
  regras de aparência (plano de barras, Fase 5).
- O "Selecionar semelhantes" (spec/ui 23 §7) continua como atalho do botão direito.

### 3.2 Substituir
Segunda aba da mesma janela. Age sobre **os elementos achados** ou **a seleção atual**
(escolha), numa transação só (um Desfazer):

| O que | Como |
|---|---|
| **Texto** das anotações (texto, etiqueta digitada, texto trocado de cota, nota da nuvem) | procurar / trocar por; opções "maiúsculas e minúsculas" e "palavra inteira"; mostra a lista de ocorrências antes de trocar |
| **Nome** e **Código** dos elementos | o mesmo procurar / trocar |
| **Valor de propriedade** (`Pset.Propriedade`) | troca o valor por outro, ou procurar/trocar dentro do texto |
| **Tipo** | troca pelo tipo escolhido, só entre elementos da mesma classe (usa o "Substituir tipo" que já existe) |
| **Camada**, **Situação** | escolhe a nova |
| **Estilo de anotação** | os campos do §2.1 |

Elemento travado ou de outra pessoa (projeto compartilhado, spec/ui 33) fica de fora, com
aviso de quantos ficaram.

## 4. Pegar e aplicar ajustes (conta‑gotas)

### 4.1 Gestos
- **Pegar**: **Alt+clique** num elemento com a ferramenta Selecionar ou com a ferramenta
  da mesma classe ativa. O cursor mostra um conta‑gotas enquanto Alt está apertado sobre
  um elemento. O que foi pego aparece na barra de estado ("Ajustes pegos: Parede ·
  Alvenaria 14").
- **Aplicar**: **Ctrl+Alt+clique** num elemento (cursor com uma gota), ou o botão
  **Aplicar ajustes** na mini‑barra da seleção, que aplica a todos os selecionados de uma
  vez. Cada aplicação é uma transação.
- Com uma **ferramenta de criação** ativa (Parede, Laje, Cota…), pegar com Alt+clique leva
  os ajustes do elemento para a ferramenta: os próximos saem iguais.
- Botões **Pegar ajustes** e **Aplicar ajustes** também no menu Editar e no botão direito,
  para quem não usa os atalhos.

### 4.2 O que passa
Só o que **não** é posição nem forma desenhada (pontos, comprimento, contorno, onde está):

| De → para | Passa |
|---|---|
| Parede → parede | tipo (camadas), altura e modo de topo/base, afastamentos, linha de referência, inclinação, tipo de linha, camada, situação |
| Laje, cobertura, forro, piso → mesma classe | tipo, espessura, cotas relativas, inclinação (cobertura), camada, situação |
| Pilar, viga → mesma classe | perfil/seção, alturas, material, ângulo (pilar), camada, situação |
| Porta, janela → mesma classe | tipo, largura e altura do vão, peitoril, lado de abertura, camada, situação |
| Objeto → objeto | tipo e os parâmetros de mesmo nome que não sejam de tamanho, se for de outro tipo (de mesmo tipo, todos os parâmetros) |
| Ambiente → ambiente | nome, uso, acabamentos, camada, situação |
| Anotação → anotação | o estilo do §2.1 em comum (texto → cota passa fonte, altura, cor) |
| Qualquer → qualquer outra classe | camada, situação, tipo de linha, propriedades de `Pset_*Common` de mesmo nome |

Textos digitados (nome do ambiente, texto da anotação) **não** passam, salvo no caso de
ambiente → ambiente, em que o nome passa (é o caso de uso).

## 5. Cópia ao arrastar (criar semelhante)
- Com a ferramenta Selecionar, ao **arrastar** a seleção (ou com a alça de mover),
  **apertar Ctrl** liga o modo cópia: aparece um **+** junto ao cursor. Apertar Ctrl de novo
  desliga (volta a mover).
- No modo cópia, **cada clique deixa uma cópia** no ponto, sempre medida a partir do
  ponto de base do arrasto: o usuário vai clicando para quantas direções quiser. **Esc**
  ou **botão direito** termina. Ao soltar o botão do arrasto já sai a primeira cópia.
- Tab abre o quadro de medidas (distância e ângulo) como no Copiar; o campo **Cópias**
  (ou `x5`) faz a série com o mesmo passo naquela direção (spec/ui 30 §9).
- Os atratores, a trava do Shift e as linhas‑guia valem como no Mover.
- Funciona na planta e no 3D (no 3D, só no plano do pavimento, como o arrasto de hoje).
- Cada cópia é uma transação própria (Desfazer tira a última).
- **Atalho sem arrastar**: com a seleção feita, **Ctrl+D** abre o mesmo modo cópia
  (pede o ponto de base).

## 6. Testes
- **EA01** estilo de uma cota: fonte, altura, negrito, cor e espessura gravados no Pset e
  no IFC (`IfcTextStyleFontModel`, `IfcCurveStyle` com a cor); Desfazer volta.
- **EA02** marcador seta e ponto: traços/preenchimentos certos no IFC.
- **EA03** texto trocado de um trecho com `<medida>`: acompanha quando a parede muda;
  sem `<medida>` fica fixo; Voltar à medida.
- **EA04** prefixo e sufixo; casas decimais.
- **EA05** interface: ficha com várias cotas ("vários"), escolha vale para todas.
- **LS01** critérios E/OU, condições de texto e número, todos os pavimentos.
- **LS02** propriedade de Pset e do tipo; quantidade com "entre".
- **LS03** somar/tirar da seleção; ocultos de fora; critérios salvos no IFC e lidos.
- **LS04** substituir texto (maiúsculas, palavra inteira) em texto e cota; uma transação.
- **LS05** substituir camada, situação, tipo e propriedade; travado fica de fora.
- **AJ01** pegar de uma parede e aplicar em outra: tipo, altura, linha de referência
  passam; pontos não.
- **AJ02** porta → porta, objeto → objeto (parâmetros de mesmo nome), anotação → anotação.
- **AJ03** classes diferentes: só camada, situação e comuns; aplicar a vários de uma vez.
- **AJ04** pegar com a ferramenta Parede ativa muda os ajustes da ferramenta.
- **CA01** arrastar + Ctrl: + no cursor, soltar cria a cópia, o original fica.
- **CA02** vários cliques, várias cópias em direções diferentes; Esc termina; Desfazer
  tira a última.
- **CA03** Ctrl de novo volta a mover; Tab com distância e Cópias.

## 7. Pontos para o revisor
**Respostas (2026‑11‑23):** (a) cor e espessura livres, por cima da pena; (b) qualquer
fonte instalada; (g) Alt+clique pega e Ctrl+Alt+clique aplica; (i) cada clique uma cópia
até Esc. Os demais pontos ficam como propostos.

- (a) **Cor e espessura** das anotações: escolha livre por anotação passando por cima da
  pena (proposta), ou escolher **uma pena** da tabela (cor e espessura juntas, como o
  resto do desenho)?
- (b) **Fontes**: qualquer fonte instalada (proposta; quem abrir o arquivo noutra máquina
  sem a fonte vê a padrão) ou só uma lista fixa que vem com o BrasBim?
- (c) Os marcadores do §2.1 bastam (traço, seta cheia, seta aberta, ponto, nenhum)?
- (d) Estilo **salvo com nome** (ex.: "Cota 1:50", "Cota 1:100") para reaplicar: agora ou
  depois (proposta: depois, o conta‑gotas resolve a maior parte)?
- (e) Substituir: a lista do §3.2 serve? Falta algo?
- (f) Atalho do Localizar: Ctrl+Shift+F (o Ctrl+F já é da busca no Navegador)?
- (g) **Conta‑gotas: Alt+clique pega e Ctrl+Alt+clique aplica** (proposta)? Hoje Alt
  segurado desliga os atratores ao desenhar; com Selecionar ativa não há conflito, mas
  com ferramenta de criação ativa o Alt+clique passaria a pegar ajustes em vez de
  clicar sem atração.
- (h) A tabela do §4.2 está certa? Algo que **não** deveria passar?
- (i) Cópia ao arrastar: **cada clique uma cópia até Esc** (proposta, como o pedido), ou
  Ctrl = uma cópia e Ctrl+Alt = várias?
- (j) Ctrl+D como atalho do modo cópia sem arrastar (proposta)?

## 7a. Implementação (2026‑11‑23)
- **§2** `core/annotations/style.py` (campos, `apply`, `edit_style`), `prims.Text`/`Stroke`
  com fonte, itálico, cor e espessura final; `base.build_state` aplica o estilo em toda
  anotação; cota: `marker`, `marker_size`, `texts`, `prefix`, `suffix`, `decimals`
  (`dimensions.segment_text`, `_markers`). Ficha: seções Texto, Linha, Texto da cota e
  Marcador (`properties._annotation_style`, `_dimension_text`); clique duplo no número
  (`SelectTool._edit_dimension_text`). Testes EA01–EA05.
- **§3** `core/find.py` (critérios, `find`, critérios salvos `criteria.edit`,
  `replace_text`, `set_fields`, propriedade genérica `pset.set`), janela
  `ui/find_dialog.py` (Editar > Localizar e substituir, Ctrl+Shift+F). Testes LS01–LS07.
- **§4** `core/pick_settings.py` (`pick`, `apply`, `tool_changes`); Alt+clique /
  Ctrl+Alt+clique na planta (`measure_box.settings_click`, cursores dos ícones
  `pick_settings` e `apply_settings`), Editar > Pegar/Aplicar ajustes e mini‑barra.
  Testes AJ01–AJ06.
- **§5** `SelectTool.key("ctrl")` liga o modo cópia; ao soltar, a 1ª cópia e o Copiar
  segue com o ponto de base (`Tool.handoff`/`take`); cursor com + (`Qt.DragCopyCursor`);
  Ctrl+D no menu Copiar. Testes CA01–CA04.

**Revisão do conta‑gotas (2026‑11‑24, pedido do revisor: "não tem funcionado bem"):**
comparado com a ajuda pública do Archicad (Parameter Transfer, §8), em que os ajustes pegos
viram os ajustes padrão da ferramenta do elemento e a seringa leva ao alvo os ajustes da
classe dele, com o elemento sob o cursor realçado:
- Pegar leva os ajustes a **todas as ferramentas que criam aquela classe**, esteja ou não
  uma delas ativa (`pick_settings.tools_for`; `main_window.load_tool_settings`), inclusive
  Porta e Janela (tipo, vão, peitoril, alinhamento), Pilar e Viga (seção do tipo, ângulo,
  topo) e o estilo das anotações (`Tool.style`). A ferramenta ativa não troca.
- **Ajustes por classe**: a janela guarda os últimos pegos de cada grupo
  (`ctx.picked_by_group`); `apply(..., by_group)` dá a cada alvo os da classe dele e, sem
  eles, os últimos pegos (só camada, situação e o comum).
- **Ctrl+Alt+clique num elemento da seleção** aplica em todos os selecionados (uma
  transação).
- **Realce**: com Alt ou Ctrl+Alt e a ferramenta parada, o elemento sob o cursor fica
  realçado (`ToolInput.settings_target`), na planta e no 3D.
- **3D**: Alt+clique e Ctrl+Alt+clique também na vista 3D (`View3D.settings_clicked`).
- **Correção**: no Windows, Alt sozinho (apertar e soltar) levava o foco ao menu Arquivo;
  a vista agora fica com o Alt (`ToolInput.settings_key`).
- Testes AJ07–AJ08 (núcleo) e AJ07–AJ10 (interface).
- Fontes novas: https://help.graphisoft.com/AC/19/INT/AC19Help/02_Interaction/02_Interaction-118.htm ·
  https://help.graphisoft.com/MEP/30/INT/Topics/030_Interaction/030_Interaction-98.html
  (comportamento de uso, sem cópia de textos ou diálogos).

**Estilo na barra Opções (2026‑11‑23, 2ª rodada):** feito para as ferramentas de anotação
e para a seleção (spec/ui 56 §3). **Fica para depois:** o conta‑gotas levando o estilo
para a ferramenta de anotação; conta‑gotas e cópia com Ctrl na vista 3D;
`Pset_*Common` de mesmo nome entre classes diferentes (§4.2, última linha); cor e fonte
no DXF exportado; lista das quantidades existentes no campo Quantidade.

## 8. Fontes
- Ajuda pública do Archicad (comportamento de uso, sem cópia de textos ou diálogos):
  Dimension Text Settings (texto personalizado antes/depois do valor automático, que
  continua associativo; voltar ao valor medido), Text Style (fonte, altura, cor da pena),
  Find and Select Elements (critérios ligados por "e", tipos por "ou", pegar critérios de
  um elemento), Search and Replace Text.
  https://help.graphisoft.com/AC/22/INT/_AC22_Help/140_UserInterfaceToolSettings/140_UserInterfaceToolSettings-26.htm ·
  https://help.graphisoft.com/AC/22/INT/_AC22_Help/030_Interaction/030_Interaction-35.htm
- Comunidade Graphisoft (relatos de usuários): conta‑gotas e seringa (pegar ajustes de um
  elemento e injetar noutro da mesma classe; parâmetros de mesmo nome passam),
  https://community.graphisoft.com/t5/Modeling/The-Eye-Dropper-and-Syringe/ta-p/303393 ;
  arrastar uma cópia com Ctrl (+ junto ao cursor) e várias cópias,
  https://community.graphisoft.com/t5/Modeling/Drag-multiple-copies/td-p/61527
- IFC 4.3 (buildingSMART): `IfcTextStyle`, `IfcTextStyleFontModel`,
  `IfcTextStyleForDefinedFont`, `IfcCurveStyle`, `IfcTextLiteralWithExtent`,
  `IfcAnnotationFillArea`.
- ABNT NBR 10126 (cotagem em desenho técnico: linhas de cota, limites — traço oblíquo,
  seta, ponto) e NBR 8403, citadas pelo nome.
- Código atual do BrasBim: `core/annotations/*`, `core/select_similar.py`,
  `core/pens.py`, `ui/tools.py` (`SelectTool`, `CopyTool`).
