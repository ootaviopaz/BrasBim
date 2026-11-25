---
documento: Atalhos de teclado configuráveis
requisito: pedido do revisor (2026-11-24): "criar no menu Preferências alguma coisa de configuração de atalhos"
autor: Claude Code (sessão limpa, sem acesso a _restrito/)
data: 2026-11-24
status: implementada com as propostas; aguarda revisão (§6)
revisor: OTTO
---

# Atalhos de teclado configuráveis

## 1. Propósito
Hoje os atalhos são fixos no código (Ctrl+Z, Ctrl+K, Ctrl+Shift+F…) e as ferramentas não
têm atalho nenhum, só os apelidos da linha de comando (spec/ui 24 §7). O usuário passa a
escolher o atalho de qualquer item dos menus e de qualquer ferramenta.

## 2. Onde
Menu novo **Preferências**, entre Equipe e Ajuda, com o item **Atalhos de teclado**. O
menu fica para as próximas preferências do programa (as que não são do projeto).

## 3. A janela
- **Busca** no alto: filtra pelo nome do comando, pelo menu e pelo atalho ("ctrl+z"), sem
  diferenciar maiúsculas nem acentos.
- **Tabela**: Comando · Onde (caminho do menu, ou "Ferramenta · grupo") · Atalho. Os
  atalhos trocados pelo usuário aparecem em negrito.
- **Campo Atalho**: clicar e apertar as teclas grava o atalho do comando escolhido.
  **Sem atalho** tira; **Voltar ao padrão** devolve o do programa.
- **Atalho já usado**: passa para o comando novo e sai do antigo, com o aviso
  "Ctrl+K era de Paleta de comandos e agora é de Parede". Nada é gravado até o OK;
  Cancelar desfaz tudo.
- **Restaurar todos** volta todos ao padrão.

### 3.1 Teclas recusadas
Sem Ctrl, Alt (ou Cmd, no Mac), não podem ser atalho as teclas que as ferramentas usam:
Esc, Enter, Tab, espaço, setas, Home, Backspace, os números e os sinais das medidas
digitadas (`. , - + / * @ < >`). Também é recusada uma sequência de várias teclas
(Ctrl+K, Ctrl+L) e só modificador. Letras sozinhas são aceitas (ex.: W para Parede);
nesse caso, a letra deixa de ir para a linha de comando quando a planta tem o foco.

## 4. Gravação
- Nas preferências do usuário (`QSettings`, chave `atalhos/teclado`), só as diferenças do
  padrão: `{"tool:wall": ["W"], "menu:Editar/Paleta de comandos": []}` (lista vazia = sem
  atalho). As chaves dos comandos são as mesmas dos apelidos.
- Ao abrir o programa, o padrão recebe as diferenças. Um atalho dado a outro comando sai
  do que o tinha por padrão (dois comandos nunca ficam com o mesmo atalho).
- Não vai para o arquivo do projeto (é do usuário, não do projeto).

## 5. Testes
- **AT01** a lista tem os menus (inclusive Preferências) e as ferramentas, com o padrão.
- **AT02** atalho de ferramenta ativa a ferramenta; fica gravado.
- **AT03** trocar tira de quem tinha (com aviso); Voltar ao padrão e Restaurar todos.
- **AT04/AT05** teclas recusadas e aceitas.
- **AT06** busca por nome e por atalho; tecla recusada não muda nada.
- **AT07** o gravado vale ao abrir uma janela nova.

## 6. Pontos para o revisor
- (a) Menu **Preferências** próprio (proposta) ou um item dentro de Editar?
- (b) Levar para Preferências também o que hoje é do usuário e está espalhado:
  Editar > Apelidos da linha de comando, Editar > Modo de seleção, Arquivo >
  Salvamento automático?
- (c) Atalhos padrão para as ferramentas (hoje nenhuma tem)? Uma proposta seria por
  letra, como os apelidos (W parede, D porta…), mas isso tira as letras da linha de
  comando quando a planta tem o foco.
- (d) Exportar e importar a lista de atalhos (para levar a outro computador)?

## 7. Fontes
- Documentação do Qt 6: `QKeySequence` (texto portátil e nativo), `QKeySequenceEdit`,
  `QAction.setShortcuts`.
- Uso comum em programas de desenho: janela de atalhos com busca, troca de atalho já
  usado e volta ao padrão (comportamento geral, sem cópia de textos ou diálogos).
- Código atual do BrasBim: `ui/command_palette.py` (comandos dos menus e ferramentas),
  `ui/command_line.py` (apelidos e preferências gravadas só com as diferenças).
