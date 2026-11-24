---
documento: Abrir IFC 2x3 e IFC 4 (conversão para o 4.3 ao abrir)
requisito: relato do revisor (2026‑11‑24): ao abrir um IFC2X3 de outro programa, a planta deu erro ("too many values to unpack") e o programa ficou repetindo o erro
autor: Claude Code (sessão limpa, sem acesso a _restrito/)
data: 2026-11-24
status: correção implementada (erro relatado); revisão do comportamento pelo revisor
revisor: OTTO
---

# Abrir IFC de outro esquema

## 1. Problema
O BrasBim é IFC 4.3 nativo, mas Arquivo > Abrir abria um IFC 2x3 (ou 4) como estava. O
núcleo e as ferramentas procuram classes que o 2x3 não tem (`IfcGeographicElement`,
`IfcDoorType`, `IfcRelInterferesElements`…) e caíam com erro. A planta também supunha que
o contorno de uma viga tem sempre 4 vértices, o que não vale para vigas de outro
programa.

## 2. Comportamento
- **Abrir** um IFC 2x3 ou IFC 4 converte o modelo para o **4.3** em memória (2x3 → 4 → 4.3,
  o caminho inverso do Exportar IFC, spec/ui 47), com `ifcopenshell.util.schema.Migrator`.
  Classes que o 4.3 retirou viram as equivalentes: `IfcDoorStyle` → `IfcDoorType`
  (`DOOR`), `IfcWindowStyle` → `IfcWindowType` (`WINDOW`), `…StandardCase` e
  `…ElementedCase` → a classe base.
- Arquivo grande leva minutos: aparece uma janela "Convertendo o arquivo para o IFC 4.3…"
  com o andamento.
- Depois de aberto, um aviso diz o esquema de origem. O projeto fica **sem nome e
  modificado**: Salvar pede um nome, para não gravar 4.3 por cima do arquivo original.
  Para entregar em 2x3 ou 4, Exportar IFC.
- Se a conversão falhar (classe sem equivalente), o Abrir recusa com a mensagem e o
  projeto aberto continua como estava.
- Tipos de pilar e viga de outro programa (sem a seção do BrasBim) não são usados como
  tipo de partida das ferramentas Pilar e Viga.
- Etiqueta de viga cujo contorno na planta não tem 4 vértices: usa o menor retângulo que
  envolve o contorno.
- Selecionar um elemento de outro programa (parede sem as camadas ou o eixo do BrasBim):
  a barra Opções mostra "Características no painel Propriedades", em vez de dar erro.
- **Unidades**: arquivo em mm, cm ou pés tem as medidas de comprimento passadas para
  metros (`ifcopenshell.util.unit.convert_file_length_units`), a unidade do modelo do
  BrasBim; o aviso diz a origem ("IFC2X3, em milímetros"). Vale também para IFC 4.3.

## 3. Peças de outro programa na planta e no 3D (relato do revisor, 2026‑11‑24)
"Na importação faltaram várias paredes, escadas, objetos": a planta só desenhava o que
tem os dados do BrasBim, e o 3D só uma lista fixa de classes.
- **Peça de outro programa**: elemento com corpo (`Representation`) sem Pset
  `BrasBim_*` (fora `BrasBim_Intervencao` e `BrasBim_PenasElemento`, que o BrasBim põe em
  qualquer elemento), nem ele nem o conjunto de que faz parte. Aberturas, elementos
  virtuais e anotações ficam de fora.
- **Planta**: o que o desenho paramétrico não desenhou aparece pela malha do corpo,
  como no corte (spec/ui 14 §4): a interseção com o plano de corte com fundo e contorno
  grosso; as quinas abaixo do plano, projetadas, em linha fina, sem o que fica sob as
  partes cortadas; o que está todo acima do plano não aparece. A peça de um conjunto
  (lance de escada, montante de fachada‑cortina) responde pelo conjunto.
- **3D**: todas as peças de outro programa, de qualquer classe.
- **Desempenho**: logo depois de abrir, a geometria de todas as peças é feita de uma
  vez, em paralelo, com a janela de andamento ("Preparando a geometria…"); a planta e o
  3D usam essa mesma reserva, refeita só para o elemento que muda (posição ou corpo). Na
  tela, as linhas em vista vão num traço só, sem as que estão fora da tela.
- **Limites**: sem hachura de material no corte (só fundo e contorno), linhas em vista
  sem remoção das escondidas umas pelas outras (só sob as partes cortadas), e o
  elemento não vira paramétrico.

## 4. Testes
- **AO01** IFC 2x3 e IFC 4 com `IfcDoorStyle` e estilo de superfície do 2x3: abre em 4.3,
  porta com `IfcDoorType` `DOOR`, planta montada.
- **AO02** arquivo 4.3 abre sem conversão.
- **AO03** sessão: sem nome, modificado, aviso com o esquema, andamento chamado, original
  intacto.
- **AO04** etiqueta de viga com contorno de 6 vértices.
- **AO05** selecionar parede de outro programa: a barra Opções não quebra.
- **AO06** planta: parede de outro programa cortada (contorno, fundo), mesa em vista,
  montante acima do plano de fora, lance de escada respondendo pela escada.
- **AO07** parede do BrasBim não vira malha.
- **AO08** 3D: mesa, montante e peças genéricas (em lote).
- **AO09** arquivo em mm abre em metros.

## 5. Fontes
- IfcOpenShell, `ifcopenshell.util.schema.Migrator` (documentação e código abertos,
  LGPL‑3.0).
- IfcOpenShell, `ifcopenshell.util.unit.convert_file_length_units` e
  `ifcopenshell.geom.iterator` (triangulação em paralelo).
- buildingSMART, IFC 4.3: `IfcDoorType`, `IfcWindowType` (substitutos de `IfcDoorStyle` e
  `IfcWindowStyle`, retirados no 4.3).
