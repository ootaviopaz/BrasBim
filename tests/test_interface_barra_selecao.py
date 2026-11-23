# SPDX-License-Identifier: LGPL-3.0-or-later
"""Barra Opções com a seleção (spec/ui 56) e estilo das anotações nas ferramentas
(spec/ui 55 §2.3)."""

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QComboBox, QLineEdit
from test_interface import _click

from brasbim.core.annotations import base, dimensions, drafting
from brasbim.core.annotations import commands as ac
from brasbim.core.structure import columns
from brasbim.core.walls import commands as cmd
from brasbim.core.walls.wall import read_state as read_wall
from brasbim.ui.tools import Mods


@pytest.fixture(autouse=True)
def _planta_visivel(window):
    window.plan.origin = QPointF(150, 450)


def _widgets(bar):
    out = []
    for action in bar.actions():
        widget = getattr(action, "defaultWidget", lambda: None)() or bar.widgetForAction(action)
        if widget is not None:
            out.append(widget)
    return out


def _field(bar, tip):
    return next(w for w in _widgets(bar) if isinstance(w, (QLineEdit, QComboBox))
                and tip in w.toolTip())


def _action(bar, text):
    return next(a for a in bar.actions() if a.text() == text)


def _walls(window):
    s = window.session
    wall_type = window.toolbox.tools["wall"].options.type
    for y in (0, 4):
        s.run(lambda y=y: cmd.create_wall(s.doc, wall_type, s.storey, (0, y), (5, y)))
    return sorted(s.doc.ifc.by_type("IfcWall"),
                  key=lambda w: read_wall(s.doc, w)["path"]["start"][1])


def test_ob01_parede_selecionada_mostra_a_barra(window):
    s = window.session
    a, _b = _walls(window)
    window.activate_tool("select")
    bar = window.options_bar
    assert bar.isVisible() and bar.actions()  # a dica, sem seleção
    _click(window, (1.3, 0.0))
    assert s.selection == {a.GlobalId} and bar.isVisible()
    _action(bar, "Eixo").trigger()  # linha de referência
    assert read_wall(s.doc, a)["ref_line"] == "axis"
    base_field = _field(bar, "Deslocamento da base")
    base_field.setText("0,15")
    base_field.editingFinished.emit()
    assert read_wall(s.doc, a)["base_offset"] == pytest.approx(0.15)
    top = _field(bar, "Topo da parede")
    top.setCurrentIndex(top.findData("fixed"))
    assert read_wall(s.doc, a)["top_mode"] == "fixed"
    height = _field(window.options_bar, "Altura da parede")
    height.setText("1,10")
    height.editingFinished.emit()
    assert read_wall(s.doc, a)["fixed_height"] == pytest.approx(1.10)
    s.select([])
    assert not any(isinstance(w, QLineEdit) for w in _widgets(bar))


def test_ob02_varias_com_valores_diferentes(window):
    s = window.session
    a, b = _walls(window)
    s.run(lambda: cmd.edit_wall(s.doc, a, base_offset=0.2))
    window.activate_tool("select")
    s.select([a.GlobalId, b.GlobalId])
    bar = window.options_bar
    field = _field(bar, "Deslocamento da base")
    assert field.text() == "" and field.placeholderText() == "vários"
    field.setText("0")
    field.editingFinished.emit()
    assert [read_wall(s.doc, w)["base_offset"] for w in (a, b)] == [0.0, 0.0]
    assert len(s.history.undo_stack[-1].ops) >= 1


def test_ob03_pilar_secao_e_angulo(window):
    from brasbim.core.structure import commands as sc

    s = window.session
    tool = window.toolbox.tools["column"]
    s.run(lambda: sc.create_column(s.doc, tool.type, s.storey, (2, 2)))
    (column,) = s.doc.ifc.by_type("IfcColumn")
    window.activate_tool("select")
    s.select([column.GlobalId])
    bar = window.options_bar
    angle = _field(bar, "Ângulo do pilar")
    angle.setText("30")
    angle.editingFinished.emit()
    assert columns.read_state(s.doc, column)["angle"] == pytest.approx(30)
    b = _field(window.options_bar, "Seção: b")
    b.setText("0,25")
    b.editingFinished.emit()
    section = columns.section(s.doc, columns.read_state(s.doc, column))
    assert section["b"] == pytest.approx(0.25)


def test_ob04_cota_selecionada_marcador_e_estilo(window):
    s = window.session
    s.run(lambda: ac.create_dimension(s.doc, s.storey, [(0, 0), (5, 0)], "fixed", 0.0, -0.6))
    (dim,) = s.doc.ifc.by_type("IfcAnnotation")
    window.activate_tool("select")
    s.select([dim.GlobalId])
    bar = window.options_bar
    marker = _field(bar, "Marcador da cota")
    marker.setCurrentIndex(marker.findData("arrow"))
    assert base.read_state(dim)["marker"] == "arrow"
    font = _field(window.options_bar, "Fonte do texto")
    font.setCurrentIndex(font.findData("Arial"))
    assert base.read_state(dim)["style"]["font"] == "Arial"
    pen = _field(window.options_bar, "Pena das linhas")
    pen.setCurrentIndex(pen.findData(5))
    assert base.read_state(dim)["style"]["pen"] == 5


def test_ob05_estilo_na_ferramenta(window):
    s = window.session
    window.activate_tool("text")
    tool = window.toolbox.active
    bar = window.options_bar
    _action(bar, "N").trigger()  # negrito
    assert tool.style == {"bold": True}
    tool.ask = lambda current: "COZINHA"
    _click(window, (1, 1))
    (text,) = [e for e in s.doc.ifc.by_type("IfcAnnotation")
               if base.kind_of(e) is drafting.TEXT]
    assert base.read_state(text)["style"] == {"bold": True}
    window.activate_tool("dimension")
    dim_tool = window.toolbox.active
    marker = _field(window.options_bar, "Marcador das próximas cotas")
    marker.setCurrentIndex(marker.findData("dot"))
    size = _field(window.options_bar, "Altura do texto")
    size.setCurrentIndex(size.findData(3.5))
    assert dim_tool.marker == "dot" and dim_tool.style == {"size": 3.5}
    dim_tool.direction = "horizontal"
    for p in ((0.0, 3.0), (4.0, 3.0), (2.0, 2.2)):
        dim_tool.move(p, Mods(alt=True))
        dim_tool.press(p, Mods(alt=True))
    (dim,) = [e for e in s.doc.ifc.by_type("IfcAnnotation")
              if base.kind_of(e) is dimensions.DIMENSION]
    state = base.read_state(dim)
    assert state["marker"] == "dot" and state["style"] == {"size": 3.5}


def test_pe05_penas_na_barra(window):
    from brasbim.core import element_pens

    s = window.session
    a, _b = _walls(window)
    window.activate_tool("select")
    s.select([a.GlobalId])
    combo = _field(window.options_bar, "Pena do contorno")
    combo.setCurrentIndex(combo.findData(6))
    assert element_pens.read(a) == {"cut": 6}
    window.plan.grab()  # desenha com a pena
    window.activate_tool("wall")
    combo = _field(window.options_bar, "Pena das linhas em vista")
    combo.setCurrentIndex(combo.findData(11))
    assert s.new_pens == {"wall": {"view": 11}}
    tool = window.toolbox.active
    s.run(lambda: cmd.create_wall(s.doc, tool.options.type, s.storey, (0, 8), (4, 8)))
    new = next(w for w in s.doc.ifc.by_type("IfcWall") if w not in (a, _b))
    assert element_pens.read(new) == {"view": 11}


def test_tc02_alca_do_texto_da_cota(window):
    from brasbim.core.annotations import dimensions

    s = window.session
    s.run(lambda: ac.create_dimension(s.doc, s.storey, [(0, 0), (5, 0)], "fixed", 0.0, -0.6))
    (dim,) = s.doc.ifc.by_type("IfcAnnotation")
    window.activate_tool("select")
    s.select([dim.GlobalId])
    tool = window.toolbox.active
    handle = next(q for w, which, q, _ in tool._all_handles() if which == "dim_text:0")
    line = base.build(s.doc, dim).strokes[0].points
    tool.press(handle, Mods())
    tool.move((handle[0] + 1.0, handle[1] - 1.2), Mods())
    tool.release((handle[0] + 1.0, handle[1] - 1.2), Mods())
    state = base.read_state(dim)
    assert state["text_moves"]["0"] == pytest.approx([1.0, -1.2], abs=1e-6)
    assert base.build(s.doc, dim).strokes[0].points == line
    assert state["offset"] == pytest.approx(-0.6)
    assert dimensions.DIMENSION.optional  # (campo opcional da cota)
