# Novidades do BrasBim

Todas as mudanças que chegam ao usuário, versão por versão. Cada mudança entra aqui no
mesmo commit que a implementa, na versão **em desenvolvimento** (a primeira da lista).
Ao publicar, o texto da versão vira a nota do lançamento no GitHub (Releases).

Grupos: **Novo**, **Melhorias**, **Correções**, **Interno** (só para quem desenvolve).

## [0.0.2] — em desenvolvimento

Aberta em 2026‑11‑12. Tudo o que for feito a partir desta data entra aqui.

### Novo
- **Busca no Navegador.** Um campo no alto do Navegador filtra a seção aberta pelo nome
  enquanto você digita, sem diferenciar maiúsculas nem acentos ("terreo" acha "Térreo");
  com várias palavras, o item precisa ter todas. Nas árvores, o que casa aparece com o que
  está dentro, e os grupos com achados se abrem sozinhos (e voltam a fechar ao limpar). O
  título mostra quantos sobraram ("Pranchas (2 de 5)"). **Ctrl+F** leva ao campo, **Enter**
  abre o primeiro achado e **Esc** limpa. (spec/ui 53)
- **Assistente: anexar imagem.** O painel do Assistente aceita até 4 imagens por pedido
  (PNG, JPEG ou WebP): pelo botão Anexar imagem, colando com Ctrl+V ou arrastando o
  arquivo. As miniaturas aparecem acima do pedido, cada uma com um × para tirar. A foto é
  reduzida antes de ir e é enviada à IA junto com o pedido; não é gravada no projeto.
  (spec/ui 54)
- **Assistente: objeto novo a partir de uma foto.** Mande a foto de um móvel, aparelho ou
  louça com as medidas e peça o objeto: a IA procura na biblioteca e, se nada servir, cria
  um objeto paramétrico novo (largura, profundidade e altura como parâmetros), confere o
  resultado numa prévia em quatro vistas, corrige e insere no projeto. Ela diz quais
  medidas vieram de você e quais ela supôs. O objeto pode ser editado e salvo na
  biblioteca como qualquer outro. É um modelo simplificado, de caixas e cilindros, sem
  textura. (spec/ui 54)
- **Forma livre.** Elemento novo para peças únicas de geometria qualquer (uma poltrona
  de desenho autoral, uma escultura, uma luminária orgânica), guardadas em malha, sem
  tipo nem parâmetros. O objeto paramétrico continua sendo para o que se repete e muda
  de medida. Aparece na planta pela silhueta, no corte, na fachada, no 3D e nas tabelas
  de objetos; move, gira, espelha, copia e estica pelas medidas (painel Propriedades),
  com material por parte. No IFC sai como malha (`Tessellation`) na classe da categoria
  escolhida. (spec/elementos/forma-livre)
- **Assistente: forma livre a partir de uma descrição ou foto.** Para peças curvas,
  inclinadas ou esculpidas, a IA monta a peça com formas mais ricas que as do objeto
  (caixa de cantos arredondados, elipsoide, cone, tubo por caminho, seções ligadas,
  revolução e extrusão, giradas nos três eixos), confere na prévia e corrige. Ela diz se
  escolheu objeto ou forma livre, e por quê.
- **Importar forma livre de arquivo.** Arquivo > Importar forma livre lê OBJ, STL e GLB,
  com a unidade e o eixo para cima do arquivo. Malhas com mais de 20 000 triângulos são
  simplificadas ao entrar, com aviso.
- **Converter em forma livre.** Editar > Converter em forma livre junta os objetos e
  formas livres selecionados numa peça só.
- **Estilo de cotas e textos.** Toda cota, texto, rótulo, linha e símbolo pode ter fonte
  própria (qualquer fonte instalada), altura, negrito, itálico, cor do texto, cor e
  espessura da linha, na ficha Propriedades; com várias anotações selecionadas, a escolha
  vale para todas. Cor e espessura escolhidas passam por cima da pena; "Seguir a pena"
  volta ao padrão. (spec/ui 55)
- **Texto e marcador da cota.** Cada trecho da cota pode ter o texto trocado (na ficha ou
  com clique duplo no número): `<medida>` continua acompanhando o modelo
  ("≈ <medida> (var.)"); sem ele o texto fica fixo e aparece sublinhado na tela, para
  não esquecer. Prefixo, sufixo, casas decimais da cota e o marcador: traço a 45°, seta
  cheia, seta aberta, ponto ou nenhum. (spec/ui 55)
- **Localizar e substituir.** Editar > Localizar e substituir (**Ctrl+Shift+F**): acha
  elementos por classe e por critérios (tipo, nome, código, camada, situação, material,
  pavimento, texto, qualquer propriedade ou quantidade, com "é", "contém", "<", "entre"…)
  no pavimento ou em todos; seleciona, soma ou tira da seleção; critérios salvos com nome
  no projeto. A aba Substituir troca texto das anotações, nome, código, propriedade, tipo,
  camada, situação ou estilo nos achados ou na seleção, de uma vez (um Desfazer).
  (spec/ui 55)
- **Conta‑gotas: pegar e aplicar ajustes.** **Alt+clique** num elemento pega os ajustes
  dele (tipo, alturas, linha de referência, estilo, camada, situação; nunca a posição) e
  **Ctrl+Alt+clique** aplica em outro; também pelos botões Pegar/Aplicar ajustes da
  mini‑barra e do menu Editar, para vários selecionados de uma vez. Com uma ferramenta de
  criação ativa (Parede, Laje…), o Alt+clique leva os ajustes para ela. (spec/ui 55)
- **Cópia ao arrastar.** Ao arrastar a seleção, apertar **Ctrl** mostra um + no cursor:
  soltar deixa a cópia e cada clique seguinte faz mais uma, em qualquer direção, até Esc
  (Tab digita distância e ângulo; Cópias faz a série). **Ctrl+D** abre o Copiar sem
  arrastar. (spec/ui 55)

### Melhorias
- Ao fim de um pedido ao Assistente, os objetos (mobiliário, louças, eletrodomésticos)
  que ele criou ou mudou também ficam selecionados, como já acontecia com paredes e
  esquadrias.
- A prévia que o Assistente usa para conferir um objeto passou a respeitar a
  profundidade: peças de trás não aparecem mais por cima das da frente.
- Material **Couro** na biblioteca de cores.

## [0.0.1] — 2026‑11‑07

Primeira versão publicada ("versão de teste"), com instalador para Windows e macOS.
