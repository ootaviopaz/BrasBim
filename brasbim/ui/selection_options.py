# SPDX-License-Identifier: GPL-3.0-or-later
"""Barra Opções com a seleção (spec/ui 56): as mesmas características da criação, agora do
elemento selecionado, editáveis a qualquer momento; e o estilo das anotações na barra, nas
ferramentas e na seleção (spec/ui 55 §2.3).

As funções recebem a ``OptionsBar`` (``toolbars.py``) e usam as peças dela (``_label``,
``_combo``, ``_number``, ``_choices``). Cada mudança é uma transação do núcleo.
"""

from __future__ import annotations

from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QComboBox

from brasbim.core import pick_settings, type_variants
from brasbim.core.annotations import base as annotation_base
from brasbim.core.annotations import commands as ac
from brasbim.core.annotations import drafting
from brasbim.core.annotations import style as annotation_style
from brasbim.core.document import OpError
from brasbim.core.ops import Transaction
from brasbim.core.ops.history import combine
from brasbim.ui import theme
from brasbim.ui.tools import fmt

MIXED = "vários"
MARKERS = [("Traço a 45°", "tick"), ("Seta cheia", "arrow"), ("Seta aberta", "open_arrow"),
           ("Ponto", "dot"), ("Nenhum", "none")]
NOUNS = {"wall": ("Parede", "Paredes"), "column": ("Pilar", "Pilares"),
         "beam": ("Viga", "Vigas"), "slab": ("Laje", "Lajes"),
         "roof": ("Cobertura", "Coberturas"), "door": ("Porta", "Portas"),
         "window": ("Janela", "Janelas"), "object": ("Objeto", "Objetos"),
         "space": ("Ambiente", "Ambientes")}


def common(values):
    """O valor em comum, ou ``None`` quando diferem."""
    values = list(values)
    first = values[0] if values else None
    return first if all(v == first for v in values) else None


def mixed_combo(bar, items, current, commit, tip: str) -> QComboBox:
    """Lista da barra; valores diferentes na seleção mostram "(vários)", que não grava."""
    values = [item[1] for item in items]
    if current not in values:
        items = [(f"({MIXED})", _Mixed), *items]
        current = _Mixed

    def chosen(value):
        if value is not _Mixed:
            commit(value)

    return bar._combo(items, current, chosen, tip)


class _Mixed:  # marcador de "(vários)" na lista
    pass


# --- estilo das anotações (spec/ui 55 §2.3) -------------------------------------------------


def _swatch(color: str | None) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(QColor(color or theme.INK))
    return QIcon(pixmap)


def pen_table(window):
    """Tabela de penas em uso na janela (a mesma do desenho da planta)."""
    return window.plan.pens


def pen_combo(table, current, commit, tip: str, empty: str = "Da tabela") -> QComboBox:
    """Escolha da pena (spec/ui 57): número, amostra da cor e espessura, como na tabela.
    ``None`` = a pena da categoria; ``_Mixed`` mostra "(vários)"."""
    combo = QComboBox()
    combo.setToolTip(tip)
    combo.setMinimumContentsLength(10)
    if current is _Mixed:
        combo.addItem(f"({MIXED})", _Mixed)
    combo.addItem(empty, None)
    numbers = sorted(int(n) for n in table.table["pens"])
    for n in numbers:
        pen = table.number(n)
        note = table.table["pens"][str(n)].get("note") or ""
        text = f"{n} · {fmt(pen.weight)} mm" + (f" · {note}" if note else "")
        combo.addItem(_swatch(pen.color), text, n)
    combo.setCurrentIndex(max(0, combo.findData(current)))

    def chosen(i):
        value = combo.itemData(i)
        if value is not _Mixed:
            commit(value)

    combo.currentIndexChanged.connect(chosen)
    return combo


def pen_widgets(bar, window, current: dict, fields, commit) -> None:
    """Penas na barra: ``current`` campo → número (``_Mixed`` quando diferem)."""
    from brasbim.core import element_pens

    table = pen_table(window)
    bar.addSeparator()
    for key in fields:
        bar._label(f"Pena {element_pens.LABELS[key].lower()}")
        bar.addWidget(pen_combo(table, current.get(key), lambda v, k=key: commit(**{k: v}),
                                element_pens.TIPS[key]))


def _element_pens(bar, window, elements) -> None:
    """Penas próprias dos elementos selecionados (spec/ui 57)."""
    from brasbim.core import element_pens

    doc = window.session.doc
    fields = element_pens.fields_of(doc, elements[0])
    if not fields:
        return
    chosen = [element_pens.read(e) for e in elements]
    current = {k: common(c.get(k) for c in chosen) if len({c.get(k) for c in chosen}) == 1
               else _Mixed for k in fields}
    pen_widgets(bar, window, current, fields, lambda **f: window.session.run(
        lambda: element_pens.set_pens(doc, elements, **f)))


def tool_pens(bar, window, group: str) -> None:
    """Penas das próximas criações da ferramenta (spec/ui 57), na sessão."""
    from brasbim.core import element_pens

    fields = element_pens.GROUP_FIELDS.get(group)
    if not fields:
        return
    session = window.session
    current = dict(session.new_pens.get(group) or {})

    def commit(**f):
        new = {k: v for k, v in {**current, **f}.items() if v is not None}
        session.new_pens[group] = new
        bar.show_for(bar.tool)

    pen_widgets(bar, window, current, fields, commit)


FIRST_FONTS = ("Archivo", "Arial", "Times New Roman", "Courier New")


def font_combo(current: str | None, commit) -> QComboBox:
    """Lista de fontes: "Padrão", as de uso comum e as instaladas (spec/ui 55 §2.1).
    ``current`` ``_Mixed`` mostra "(vários)"; ``commit(None)`` volta à fonte padrão."""
    from PySide6.QtGui import QFontDatabase

    combo = QComboBox()
    combo.setToolTip("Fonte do texto (qualquer fonte instalada)")
    combo.setMaximumWidth(170)
    installed = sorted(set(QFontDatabase.families()))
    names = [*FIRST_FONTS, *[f for f in installed if f not in FIRST_FONTS]]
    if isinstance(current, str) and current not in names:
        names.insert(0, current)  # fonte de outro computador: continua escolhida
    if current is _Mixed:
        combo.addItem(f"({MIXED})", _Mixed)
    combo.addItem("Padrão", None)
    for name in names:
        combo.addItem(name, name)
    combo.setCurrentIndex(max(0, combo.findData(current)))

    def chosen(i):
        value = combo.itemData(i)
        if value is not _Mixed:
            commit(value)

    combo.currentIndexChanged.connect(chosen)
    return combo


def _toggle(bar, text: str, tip: str, on: bool | None, commit) -> None:
    action = QAction(text, bar)
    action.setCheckable(True)
    action.setChecked(bool(on))
    action.setToolTip(tip)
    action.toggled.connect(lambda v: commit(bool(v) or None))
    bar.addAction(action)


def style_widgets(bar, current: dict, commit, text: bool = True, line: bool = True,
                  size: bool = True) -> None:
    """Fonte, altura, negrito, itálico, cor do texto; cor e espessura da linha.
    ``current``: campo → valor (``_Mixed`` quando diferem); ``commit(**campos)``."""
    if text:
        bar.addSeparator()
        bar._label("Fonte")
        bar.addWidget(font_combo(current.get("font"), lambda v: commit(font=v)))
        if size:  # o texto tem a altura própria; aí a do estilo não aparece
            bar._label("Altura")
            sizes = [("do tipo", None)] + [(f"{fmt(v)} mm", v)
                                           for v in annotation_style.SIZES]
            value = current.get("size")
            if value not in (None, _Mixed) and value not in annotation_style.SIZES:
                sizes.append((f"{fmt(value)} mm", value))
            mixed_combo(bar, sizes, value, lambda v: commit(size=v),
                        "Altura do texto no papel (mm)")
        _toggle(bar, "N", "Negrito", current.get("bold") is True,
                lambda v: commit(bold=v))
        _toggle(bar, "I", "Itálico", current.get("italic") is True,
                lambda v: commit(italic=v))
        # Pena do texto (spec/ui 57): cor da tabela, como no resto do desenho.
        bar._label("Pena do texto")
        bar.addWidget(pen_combo(pen_table(bar.window_), current.get("text_pen"),
                                lambda v: commit(text_pen=v), "Pena do texto (cor)"))
    if line:
        bar.addSeparator()
        bar._label("Pena da linha")
        bar.addWidget(pen_combo(pen_table(bar.window_), current.get("pen"),
                                lambda v: commit(pen=v),
                                "Pena das linhas e marcadores (cor e espessura)"))


def tool_style(bar, tool, text: bool = True, line: bool = True, size: bool = True) -> None:
    """Estilo das próximas anotações da ferramenta (vale até mudar de novo)."""
    def commit(**fields):
        tool.style = annotation_style.clean({**(tool.style or {}), **fields}) or None
        bar.show_for(tool)

    style_widgets(bar, dict(tool.style or {}), commit, text, line, size)


def _selection_style(bar, window, elements, size: bool = True) -> None:
    doc = window.session.doc
    elements = [e for e in elements if annotation_style.styled(e)]
    if not elements:
        return
    current = {}
    for field in annotation_style.FIELDS:
        values = [(annotation_base.read_state(e).get("style") or {}).get(field)
                  for e in elements]
        current[field] = values[0] if all(v == values[0] for v in values) else _Mixed
    has_text = any(annotation_base.build(doc, e).texts for e in elements)

    def commit(**fields):
        window.session.run(lambda: annotation_style.edit_style(doc, elements, **fields))

    style_widgets(bar, current, commit, text=has_text, size=size)


# --- seleção (spec/ui 56) ----------------------------------------------------------------


def build(bar, window, elements) -> bool:
    """Monta a barra para a seleção; devolve se pôs algo."""
    doc = window.session.doc
    groups = {pick_settings.group_of(doc, e) for e in elements}
    if None in groups:
        groups.discard(None)
        if not groups:
            return False
    n = len(elements)
    if len(groups) > 1:
        notes = [e for e in elements if annotation_style.styled(e)]
        bar._label(f"{n} elementos")
        if notes:
            _selection_style(bar, window, notes)
        return True
    group = groups.pop()
    if group.startswith("annotation:"):
        _annotations(bar, window, elements, group.split(":", 1)[1])
        return True
    one, many = NOUNS.get(group, (group, group))
    builder = {"wall": _walls, "column": _columns, "beam": _beams, "slab": _slabs,
               "roof": _roofs, "door": _doors, "window": _doors, "space": _spaces,
               "object": _objects}.get(group)
    if builder is None:  # forma livre e outros: as medidas ficam no painel Propriedades
        return False
    bar._label(f"<b>{one if n == 1 else f'{many} ({n})'}</b>")
    builder(bar, window, elements)
    _element_pens(bar, window, elements)  # spec/ui 57
    return True


def _run(window, label: str, builds) -> None:
    doc = window.session.doc
    builds = list(builds)
    if len(builds) == 1:
        window.session.run(builds[0])
    else:
        window.session.run(lambda: combine(doc, label, builds))


def _type_combo(bar, window, ifc_class: str, types, states, edit, tip: str) -> None:
    current = common(s["type"] for s in states)
    origin = None
    if current:
        found = window.session.doc.find(current)
        if found is not None and type_variants.is_variant(found):
            origin = type_variants.origin_of(window.session.doc, found)
    current = origin.GlobalId if origin is not None else current
    bar._label("Tipo")
    mixed_combo(bar, [(t.Name, t.GlobalId) for t in types], current, lambda v: edit(type=v), tip)
    gid = current
    if gid:
        from brasbim.ui.toolbars import make_action

        action = make_action(bar, "edit_type", "Editar tipo", "abre o tipo na janela de tipos")
        action.triggered.connect(lambda: window.edit_type(ifc_class, gid))
        bar.addAction(action)


def _thickness(bar, window, elements, thicknesses) -> None:
    doc = window.session.doc
    bar._label("Espessura")
    bar._number(common(round(t, 6) for t in thicknesses),
                lambda v: window.session.run(lambda: type_variants.set_thickness(doc, elements, v)),
                "Espessura (m); mudar cria uma variante do tipo", placeholder=MIXED)


def _walls(bar, window, walls) -> None:
    from brasbim.core.walls import commands as cmd
    from brasbim.core.walls import rebuild, roof_top
    from brasbim.core.walls import types as wall_types
    from brasbim.core.walls.wall import read_state
    from brasbim.ui.toolbars import REF_LINES, WALL_TOPS

    doc = window.session.doc
    states = [read_state(doc, w) for w in walls]

    def edit(**changes):
        window.session.run(lambda: cmd.edit_walls(doc, walls, **changes))

    _type_combo(bar, window, "IfcWallType", bar._types("IfcWallType"), states, edit,
                "Tipo da parede selecionada")
    if all(s["type"] and not type_variants.is_profile(doc.get(s["type"])) for s in states):
        _thickness(bar, window, walls, [wall_types.thickness(doc.get(s["type"]))
                                        for s in states])
    bar.addSeparator()
    ref = common(s["ref_line"] for s in states)
    bar._choices(REF_LINES, ref, lambda v: edit(ref_line=v))
    bar.addSeparator()
    bar._label("Base")
    bar._number(common(s["base_offset"] for s in states), lambda v: edit(base_offset=v),
                "Deslocamento da base (m)", placeholder=MIXED)
    bar._label("Topo")
    mode = common(s["top_mode"] for s in states)

    def to_fixed(w):
        height = rebuild.height(doc, read_state(doc, w))
        return cmd.edit_wall(doc, w, top_mode="fixed", fixed_height=height, top_roofs=[])

    def to_storey(w):
        above = doc.storey_above(doc.get(read_state(doc, w)["storey"]))
        if above is None:
            raise OpError("não há pavimento acima da parede")
        return cmd.edit_wall(doc, w, top_mode="storey", top_storey=above.GlobalId,
                             top_offset=0.0, top_roofs=[])

    def to_roof(w):
        return Transaction("Topo até a cobertura", roof_top.to_roof_ops(doc, w))

    builders = {"fixed": to_fixed, "storey": to_storey, "roof": to_roof}
    mixed_combo(bar, WALL_TOPS, mode, lambda v: _run(
        window, f"Topo de {len(walls)} paredes",
        [lambda w=w: builders[v](w) for w in walls]), "Topo da parede selecionada")
    if mode == "fixed":
        bar._number(common(s["fixed_height"] for s in states), lambda v: edit(fixed_height=v),
                    "Altura da parede (m)", placeholder=MIXED)
    elif mode == "storey":
        bar._number(common(s["top_offset"] for s in states), lambda v: edit(top_offset=v),
                    "Deslocamento do topo (m)", placeholder=MIXED)


def _structure_edit(window, elements):
    from brasbim.core.structure import commands as sc

    doc = window.session.doc

    def edit(**changes):
        window.session.run(lambda: sc.edit_elements(doc, elements, **changes))
    return edit


def _top(bar, window, elements, states, fixed_key: str, fixed_tip: str, tops) -> None:
    from brasbim.core.structure import commands as sc

    doc = window.session.doc
    edit = _structure_edit(window, elements)
    bar._label("Topo")
    mode = common(s["top_mode"] for s in states)

    def set_mode(value):
        def build(e, s):
            if value == "fixed":
                module = sc.module_of(e)
                current = (module.height(doc, s) if fixed_key == "fixed_height"
                           else module.top_z(doc, s))
                return sc.edit_element(doc, e, top_mode="fixed", **{fixed_key: current})
            above = doc.storey_above(doc.get(s["storey"]))
            if above is None:
                raise OpError("não há pavimento acima")
            return sc.edit_element(doc, e, top_mode="storey", top_storey=above.GlobalId,
                                   top_offset=0.0)
        _run(window, "Topo", [lambda e=e, s=s: build(e, s)
                              for e, s in zip(elements, states, strict=True)])

    mixed_combo(bar, tops, mode, set_mode, "Topo do elemento selecionado")
    if mode == "fixed":
        bar._number(common(s[fixed_key] for s in states), lambda v: edit(**{fixed_key: v}),
                    fixed_tip, placeholder=MIXED)
    elif mode == "storey":
        bar._number(common(s["top_offset"] for s in states), lambda v: edit(top_offset=v),
                    "Deslocamento do topo (m)", placeholder=MIXED)


def _section(bar, window, elements, states) -> None:
    """b × h (ou Ø) da seção de pilar e viga: mudar acha ou cria o tipo da seção."""
    from brasbim.core.structure import commands as sc
    from brasbim.core.structure import profiles

    doc = window.session.doc
    sections = [sc.module_of(e).section(doc, s) for e, s in zip(elements, states, strict=True)]
    shape = common(sec["shape"] for sec in sections)

    def size(key):
        def commit(value):
            if value <= profiles.MIN_SIZE:
                window.session.message(f"a dimensão deve passar de {fmt(profiles.MIN_SIZE)} m",
                                       "recusa")
                return
            _run(window, "Seção", [lambda e=e, sec=sec: sc.edit_element(
                doc, e, section={**sec, key: value})
                for e, sec in zip(elements, sections, strict=True)])
        return commit

    if shape == "circle":
        bar._label("Ø")
        bar._number(common(sec["d"] for sec in sections), size("d"), "Diâmetro (m)",
                    placeholder=MIXED)
    elif shape == "rect":
        for key, label in (("b", "b"), ("h", "h")):
            bar._label(label)
            bar._number(common(sec[key] for sec in sections), size(key),
                        f"Seção: {label} (m)", placeholder=MIXED)


def _columns(bar, window, columns_) -> None:
    from brasbim.core.structure import columns
    from brasbim.ui.toolbars import TOPS

    doc = window.session.doc
    states = [columns.read_state(doc, c) for c in columns_]
    if any(s["foreign"] is not None for s in states):
        bar._label("de outro programa: edite pelo painel Propriedades")
        return
    edit = _structure_edit(window, columns_)
    _type_combo(bar, window, "IfcColumnType", bar._types("IfcColumnType"), states, edit,
                "Tipo do pilar selecionado")
    _section(bar, window, columns_, states)
    bar.addSeparator()
    bar._label("Ângulo")
    bar._number(common(s["angle"] for s in states), lambda v: edit(angle=v),
                "Ângulo do pilar (graus, anti-horário)", placeholder=MIXED)
    bar._label("Base")
    bar._number(common(s["base_offset"] for s in states), lambda v: edit(base_offset=v),
                "Deslocamento da base (m)", placeholder=MIXED)
    _top(bar, window, columns_, states, "fixed_height", "Altura do pilar (m)", TOPS)


def _beams(bar, window, beams_) -> None:
    from brasbim.core.structure import beams
    from brasbim.ui.toolbars import BEAM_TOPS, REF_LINES

    doc = window.session.doc
    states = [beams.read_state(doc, b) for b in beams_]
    if any(s["foreign"] is not None for s in states):
        bar._label("de outro programa: edite pelo painel Propriedades")
        return
    edit = _structure_edit(window, beams_)
    _type_combo(bar, window, "IfcBeamType", bar._types("IfcBeamType"), states, edit,
                "Tipo da viga selecionada")
    _section(bar, window, beams_, states)
    bar.addSeparator()
    bar._choices(REF_LINES, common(s["ref_line"] for s in states),
                 lambda v: edit(ref_line=v))
    bar.addSeparator()
    _top(bar, window, beams_, states, "top_elevation",
         "Cota do topo, a partir do pavimento (m)", BEAM_TOPS)


def _slabs(bar, window, slabs_) -> None:
    from brasbim.core.structure import slabs
    from brasbim.ui.toolbars import floor_types

    doc = window.session.doc
    states = [slabs.read_state(doc, s) for s in slabs_]
    if any(s["foreign"] is not None for s in states):
        bar._label("de outro programa: edite pelo painel Propriedades")
        return
    edit = _structure_edit(window, slabs_)
    _type_combo(bar, window, "IfcSlabType", floor_types(doc), states, edit,
                "Tipo da laje selecionada")
    if all(s["type"] for s in states):
        _thickness(bar, window, slabs_, [slabs.thickness(doc, s) for s in states])
    bar.addSeparator()
    bar._label("Deslocamento do topo")
    bar._number(common(s["top_offset"] for s in states), lambda v: edit(top_offset=v),
                "Cota da face de cima em relação ao pavimento (m)", placeholder=MIXED)


def _roofs(bar, window, roofs_) -> None:
    from brasbim.core.structure import roofs
    from brasbim.ui.toolbars import roof_types

    doc = window.session.doc
    states = [roofs.read_state(doc, r) for r in roofs_]
    if any(s["foreign"] is not None for s in states):
        bar._label("de outro programa: edite pelo painel Propriedades")
        return
    edit = _structure_edit(window, roofs_)
    _type_combo(bar, window, "IfcSlabType", roof_types(doc), states, edit,
                "Tipo da cobertura selecionada")
    bar.addSeparator()
    if common(s["shape"] for s in states) != "flat":
        bar._label("Inclinação (%)")
        bar._number(common(s["slope"] for s in states), lambda v: edit(slope=v),
                    "Inclinação das águas em %", placeholder=MIXED)
    bar._label("Beiral")
    bar._number(common(s["overhang"] for s in states), lambda v: edit(overhang=v),
                "Quanto a cobertura passa do contorno de apoio (m)", placeholder=MIXED)
    bar._label("Apoio")
    bar._number(common(s["base_height"] for s in states), lambda v: edit(base_height=v),
                "Cota da face de baixo sobre o contorno, a partir do pavimento (m); "
                "vazio: topo das paredes", placeholder="paredes", allow_empty=True)


def _doors(bar, window, door_list) -> None:
    from brasbim.core.fillings import commands as fc
    from brasbim.core.fillings import doors
    from brasbim.core.walls import openings
    from brasbim.ui.toolbars import ALIGNS

    doc = window.session.doc
    is_window = door_list[0].is_a("IfcWindow")
    type_class = "IfcWindowType" if is_window else "IfcDoorType"
    states = [doors.read_state(d) for d in door_list]
    spans = [openings.read_state(o) for o in (fc.opening_of(d) for d in door_list)
             if o is not None]

    def edit(**changes):
        window.session.run(lambda: fc.edit_doors(doc, door_list, **changes))

    _type_combo(bar, window, type_class, bar._types(type_class), states, edit,
                f"Tipo da {'janela' if is_window else 'porta'} selecionada")
    bar.addSeparator()
    if spans and len(spans) == len(door_list):
        for key, src, name in (("width", "width", "Largura"), ("height", "height", "Altura"),
                               ("base", "sill", "Peitoril" if is_window else "Base")):
            bar._label(name)
            bar._number(common(s[src] for s in spans), lambda v, k=key: edit(**{k: v}),
                        f"{name} do vão (m)", placeholder=MIXED)
    bar.addSeparator()
    bar._label("Marco")
    mixed_combo(bar, ALIGNS, common(s["align"] for s in states), lambda v: edit(align=v),
                "Alinhamento do marco na parede")
    bar._number(common(s["offset"] for s in states), lambda v: edit(offset=v),
                "Deslocamento do marco (m)", placeholder=MIXED)


def _spaces(bar, window, spaces_) -> None:
    from brasbim.core.annotations import spaces as space_data

    doc = window.session.doc
    states = [space_data.read_state(s) for s in spaces_]

    def edit(**changes):
        _run(window, "Editar ambientes", [lambda s=s: ac.edit_element(doc, s, **changes)
                                          for s in spaces_])

    bar._label("Nome")
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItems([space_data.DEFAULT_NAME, *space_data.NAMES])
    name = common(s["name"] for s in states)
    combo.setCurrentText(name or "")
    combo.lineEdit().setPlaceholderText(MIXED)
    combo.setToolTip("Nome do ambiente")
    combo.lineEdit().editingFinished.connect(
        lambda: combo.currentText().strip() and combo.currentText().strip() != name
        and edit(name=combo.currentText().strip()))
    combo.activated.connect(lambda _i: combo.currentText().strip() != name
                            and edit(name=combo.currentText().strip()))
    bar.addWidget(combo)
    bar._label("Pé-direito")
    bar._number(common(s["height"] for s in states), lambda v: edit(height=v),
                "Pé-direito (vazio = calculado até a laje de cima)", "calculado",
                allow_empty=True)


def _objects(bar, window, objs) -> None:
    from brasbim.core.objects import commands as oc
    from brasbim.core.objects import elements as objects

    doc = window.session.doc
    states = [objects.read_state(doc, o) for o in objs]

    def edit(**changes):
        window.session.run(lambda: oc.edit_objects(doc, [o.GlobalId for o in objs],
                                                   **changes))

    if all(s["host"] is None for s in states):
        bar._label("Rotação")
        bar._number(common(s["angle"] for s in states), lambda v: edit(angle=v),
                    "Rotação do objeto (graus, anti-horário)", placeholder=MIXED)
    elevation = common(s["values"].get("elevacao") for s in states)
    bar._label("Elevação")
    bar._number(elevation, lambda v: _run(window, "Elevação", [
        lambda o=o, s=s: oc.edit_object(doc, o, values={**s["values"], "elevacao": v})
        for o, s in zip(objs, states, strict=True)]),
        "Altura da base do objeto acima do piso (m)", placeholder=MIXED)


def _annotations(bar, window, elements, prefix: str) -> None:
    """Anotações do mesmo tipo: os campos do tipo e o estilo."""
    doc = window.session.doc
    kind = annotation_base.KINDS[prefix]
    n = len(elements)
    bar._label(f"<b>{kind.noun.capitalize()}{f' ({n})' if n > 1 else ''}</b>")
    states = [annotation_base.read_state(e) for e in elements]

    def edit(**changes):
        _run(window, f"Editar {kind.noun}", [lambda e=e: ac.edit_element(doc, e, **changes)
                                             for e in elements])

    if prefix == "text":
        bar._label("Altura")
        mixed_combo(bar, [(f"{fmt(v)} mm", v) for v in drafting.TEXT_SIZES],
                    common(s["size"] for s in states), lambda v: edit(size=v),
                    "Altura do texto no papel")
        bar._label("Ângulo")
        bar._number(common(s["angle"] for s in states), lambda v: edit(angle=v),
                    "Ângulo do texto (graus)", placeholder=MIXED)
        from brasbim.ui.toolbars import ALIGN_TEXT

        mixed_combo(bar, ALIGN_TEXT, common(s["align"] for s in states),
                    lambda v: edit(align=v), "Alinhamento do texto")
    elif prefix in ("line2d", "circle2d", "arc2d", "spline2d"):
        from brasbim.ui.toolbars import DASHES

        bar._label("Tipo")
        mixed_combo(bar, DASHES, common(s["dash"] for s in states), lambda v: edit(dash=v),
                    "Tipo de linha")
    elif prefix == "hatch":
        from brasbim.ui.toolbars import HATCHES

        bar._label("Padrão")
        mixed_combo(bar, HATCHES, common(s["pattern"] for s in states),
                    lambda v: edit(pattern=v), "Padrão da hachura")
        bar._label("Ângulo")
        bar._number(common(s["angle"] for s in states), lambda v: edit(angle=v),
                    "Ângulo das linhas (graus)", placeholder=MIXED)
        bar._label("Espaçamento")
        bar._number(common(s["spacing"] for s in states), lambda v: edit(spacing=v),
                    "Espaçamento das linhas, em mm de papel", placeholder=MIXED)
    elif prefix == "dimension":
        bar._label("Marcador")
        mixed_combo(bar, MARKERS, common(s.get("marker") or "tick" for s in states),
                    lambda v: edit(marker=None if v == "tick" else v), "Marcador da cota")
        bar._label("Casas")
        mixed_combo(bar, [("do projeto", None)] + [(str(i), i) for i in range(5)],
                    common(s.get("decimals") for s in states), lambda v: edit(decimals=v),
                    "Casas decimais da cota")
    _selection_style(bar, window, elements, size=prefix != "text")


def dimension_tool_widgets(bar, tool) -> None:
    """Marcador das próximas cotas (spec/ui 55 §2.3)."""
    bar._label("Marcador")
    bar._combo(MARKERS, tool.marker or "tick",
               lambda v: setattr(tool, "marker", None if v == "tick" else v),
               "Marcador das próximas cotas")

