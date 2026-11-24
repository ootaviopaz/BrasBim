# Roteiro de teste da versão 0.0.2

Teste no Windows, no programa de verdade, antes de lançar a 0.0.2. Cada item diz **o que
fazer** e **o que deve acontecer**. Marque `[x]` quando der certo. Quando der errado,
escreva embaixo do item o que aconteceu e, se puder, tire um print (ou use **Ajuda >
Registrar observação**, que grava o texto num arquivo e mostra onde, em Mensagens).

**Como abrir:** na pasta `BrasBim`, rode `.venv\Scripts\brasbim` (ou o instalador, se
montarmos um de teste). Comece com **Arquivo > Novo**.

**Tempo estimado:** de 1h30 a 2h. Dá para fazer em partes: os blocos são independentes.

---

## A. Conta‑gotas (revisto em 24/11)

Prepare: desenhe duas paredes. Selecione a primeira e mude, na barra Opções, o tipo, a
altura (topo fixo, ex.: 1,10) e a linha de referência.

- [ ] **A1. Cursor.** Com Selecionar ativa, pare o mouse sobre a primeira parede e
  segure **Alt**. O cursor vira um conta‑gotas e a parede fica realçada. Solte o Alt:
  o cursor volta ao normal e o realce some.
- [ ] **A2. Alt não abre o menu.** Com o mouse parado sobre a planta, aperte e solte o
  **Alt** sem clicar. O menu Arquivo **não** pode ficar destacado. Em seguida, digite um
  número ou aperte Esc: a planta ainda recebe a tecla.
- [ ] **A3. Pegar.** **Alt+clique** na primeira parede. A barra de estado mostra "Ajustes
  pegos: Parede · …". A seleção não muda.
- [ ] **A4. Aplicar.** **Ctrl+Alt+clique** (cursor de gota) na segunda parede: ela fica
  com o tipo, a altura e a linha de referência da primeira, sem sair do lugar.
  **Ctrl+Z** desfaz.
- [ ] **A5. Vale para a ferramenta.** Depois do A3, ative a ferramenta **Parede**, sem
  pegar de novo: a barra Opções já mostra o tipo e a altura pegos. Desenhe uma parede
  nova: ela sai igual.
- [ ] **A6. Vários de uma vez.** Desenhe mais duas paredes, selecione as duas e dê
  **Ctrl+Alt+clique** numa delas: as duas recebem os ajustes, e um Ctrl+Z desfaz as duas.
- [ ] **A7. Porta e janela.** Coloque duas portas de tipos ou larguras diferentes. Alt+clique
  numa, Ctrl+Alt+clique na outra: tipo, largura e altura passam, a posição não. Ative a
  ferramenta Porta: ela já está com o tipo pego.
- [ ] **A8. Pilar e viga.** Pilar de 20×40 e outro de 30×30: Alt+clique no de 30×30,
  ferramenta Pilar: a seção da barra Opções é 30×30.
- [ ] **A9. Cotas.** Uma cota com seta e fonte Arial, outra padrão: Alt+clique na primeira,
  Ctrl+Alt+clique na segunda: marcador e fonte passam; os pontos não.
- [ ] **A10. Uma classe não apaga a outra.** Pegue de uma parede, depois de uma cota.
  Ctrl+Alt+clique numa parede: recebe os ajustes **da parede**.
- [ ] **A11. No 3D.** Na vista 3D, Alt+clique numa parede e Ctrl+Alt+clique noutra: os
  ajustes passam, como na planta.
- [ ] **A12. Menu e mini‑barra.** Editar > Pegar ajustes (um selecionado) e Editar >
  Aplicar ajustes (vários selecionados) fazem o mesmo que os cliques.

## B. Atalhos de teclado (novo em 24/11)

- [ ] **B1.** O menu **Preferências** existe, entre Equipe e Ajuda, com **Atalhos de
  teclado**.
- [ ] **B2. Busca.** Digite "desfaz": aparece Desfazer (Ctrl+Z). Digite "ctrl+k": aparece a
  Paleta de comandos.
- [ ] **B3. Atalho de ferramenta.** Escolha **Parede**, clique no campo Atalho e aperte
  **Ctrl+Alt+W**. OK. Na planta, Ctrl+Alt+W ativa a ferramenta Parede.
- [ ] **B4. Atalho já usado.** Dê **Ctrl+K** à ferramenta Laje: aparece o aviso de que era da
  Paleta de comandos. OK: Ctrl+K passa a ativar a Laje e a Paleta fica sem atalho.
- [ ] **B5. Voltar.** Reabra, escolha Paleta de comandos e **Voltar ao padrão**: Ctrl+K volta
  para ela e sai da Laje. **Restaurar todos** limpa tudo.
- [ ] **B6. Recusa.** Tente dar **Esc** ou o número **5** a um comando: aparece o aviso em
  vermelho e nada muda.
- [ ] **B7. Fica gravado.** Feche o BrasBim e abra de novo: o atalho do B3 continua valendo.
- [ ] **B8. Cancelar.** Mude um atalho e clique **Cancelar**: nada muda.

## C. Estilo de cotas e textos, penas por elemento

- [ ] **C1.** Selecione uma cota: na barra Opções e no painel Propriedades, troque a fonte
  (uma instalada qualquer), a altura, negrito e a pena do texto. A cota muda na tela.
- [ ] **C2.** Selecione três cotas e troque a altura: as três mudam; os campos diferentes
  mostram "vários".
- [ ] **C3.** Clique duplo no número da cota e escreva `≈ <medida>`: o número continua
  acompanhando quando a parede muda de comprimento. Escreva `VER DETALHE` (sem
  `<medida>`): o texto fica sublinhado na tela e **não** sai sublinhado no PDF.
- [ ] **C4.** Troque o marcador da cota (seta cheia, aberta, ponto, nenhum).
- [ ] **C5. Mover o texto da cota.** Arraste a alça do número: só o texto se move; longe da
  linha aparece a linha de chamada. "Textos de volta ao lugar" desfaz.
- [ ] **C6. Penas do elemento.** Numa parede, escolha a pena do contorno e da hachura do
  corte: a planta muda. "Da tabela" volta.
- [ ] **C7. PDF.** Arquivo > Exportar PDF: fontes, penas e marcadores saem como na tela.

## D. Localizar e substituir (Ctrl+Shift+F)

- [ ] **D1.** Ache "Parede" com tipo "Alvenaria 14" no pavimento: o número achado bate e
  **Selecionar** seleciona.
- [ ] **D2.** Dois critérios (classe Porta **e** largura < 0,80): só as portas estreitas.
- [ ] **D3.** "Todos os pavimentos": acha nos outros pavimentos também.
- [ ] **D4.** Salve o critério com um nome, salve o projeto, feche e abra: o critério está lá.
- [ ] **D5. Substituir.** Troque um texto de anotação (ex.: "SALA" por "ESTAR"): mostra a
  lista antes; troca tudo; um Ctrl+Z desfaz tudo.
- [ ] **D6.** Substitua a camada ou a situação dos achados.

## E. Cópia com Ctrl e barra Opções com a seleção

- [ ] **E1.** Arraste uma parede e, no meio do arrasto, aperte **Ctrl**: aparece o + no
  cursor. Soltar deixa uma cópia; cada clique seguinte faz outra, em qualquer direção;
  **Esc** termina. O original fica no lugar.
- [ ] **E2.** Ctrl de novo, no meio do arrasto, volta a mover (sem cópia).
- [ ] **E3.** **Ctrl+D** com algo selecionado: pede o ponto de base e copia.
- [ ] **E4.** Selecione uma parede: a barra Opções mostra tipo, espessura, alturas e linha
  de referência dela; mudar ali muda a parede.

## F. Navegador e Assistente

- [ ] **F1.** **Ctrl+F** leva ao campo de busca do Navegador; "terreo" acha "Térreo"; Enter
  abre; Esc limpa.
- [ ] **F2. Assistente com foto.** Anexe a foto de um móvel com as medidas e peça o
  objeto: ele procura na biblioteca ou cria um novo e insere no projeto, dizendo quais
  medidas supôs. (Precisa da chave da IA configurada.)
- [ ] **F3. Cotas pelo Assistente.** Peça "cote as paredes": cada parede reta ganha a cota
  com as portas e janelas; um Ctrl+Z desfaz tudo.

## G. Forma livre

- [ ] **G1.** Arquivo > Importar forma livre: um OBJ, STL ou GLB entra na escala certa.
- [ ] **G2.** Move, gira, copia e estica pelas medidas no painel Propriedades.
- [ ] **G3. Corte e fachada.** Faça um corte e uma fachada passando pela peça e tire um
  print. **Era o defeito aberto de 12/11** ("não aparece bem"): diga o que está errado
  (sem contorno? sem hachura? só triângulos?).
- [ ] **G4.** Exportar IFC e abrir em outro programa (BIMvision, Archicad, Revit): a peça
  aparece.

## H. Arquivo e instalação

- [ ] **H1.** Salve, feche e abra o projeto com tudo isso: nada se perde (estilos, penas,
  textos trocados da cota, critérios salvos).
- [ ] **H2.** Abra um projeto feito na 0.0.1: abre sem erro.
- [ ] **H3.** (Com o instalador de teste) instala sem administrador, cria os atalhos e
  abre um `.ifc` com clique duplo.

---

**Ao terminar:** mande a lista com o que falhou (número do item + o que aconteceu + print).
Corrigido o que aparecer, o lançamento segue: juntar ao `main`, datar a 0.0.2 no
`CHANGELOG.md`, montar o instalador e criar a etiqueta `v0.0.2`.
