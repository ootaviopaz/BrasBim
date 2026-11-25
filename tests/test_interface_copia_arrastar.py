# SPDX-License-Identifier: LGPL-3.0-or-later
"""Cópia ao arrastar com Ctrl (spec/ui 55 §5)."""

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from brasbim.core.walls import commands as cmd
from brasbim.ui.tools import Mods


@pytest.fixture(autouse=True)
def _planta_visivel(window):
    window.plan.origin = QPointF(150, 450)


def _wall(window):
    s = window.session
    s.run(lambda: cmd.create_wall(s.doc, window.toolbox.tools["wall"].options.type, s.storey,
                                  (0, 0), (4, 0)))
    (wall,) = s.doc.ifc.by_type("IfcWall")
    s.select([wall.GlobalId])
    return wall


def _drag_start(window, a=(1.3, 0.0), b=(1.3, 3.0)):
    window.activate_tool("select")
    tool = window.toolbox.active
    tool.press(a, Mods())
    tool.move(b, Mods())
    assert tool.drag["kind"] == "move" and tool.drag["active"]
    return tool


def _walls(window):
    return window.session.doc.ifc.by_type("IfcWall")


def test_ca01_ctrl_no_arrasto_faz_copia(window):
    _wall(window)
    tool = _drag_start(window)
    QTest.keyClick(window.plan, Qt.Key_Control)  # o + aparece
    assert tool.copying() and "Cópia" in tool.hint()
    assert window.plan.cursor().shape() == Qt.DragCopyCursor
    tool.release((1.3, 3.0), Mods())
    window.plan.after_tool_input()
    assert len(_walls(window)) == 2  # o original fica
    copy = window.toolbox.active
    assert copy.name == "copy" and copy.copying()
    assert copy.points == [pytest.approx((1.3, 0.0))]


def test_ca02_varios_cliques_em_direcoes_diferentes(window):
    s = window.session
    _wall(window)
    tool = _drag_start(window)
    tool.key("ctrl")
    tool.release((1.3, 3.0), Mods())
    window.plan.after_tool_input()
    copy = window.toolbox.active
    for p in ((2.0, -3.0), (8.0, 0.0)):
        copy.move(p, Mods(alt=True))
        copy.press(p, Mods(alt=True))
    assert len(_walls(window)) == 4
    ys = sorted(round(w.ObjectPlacement.RelativePlacement.Location.Coordinates[1], 6)
                for w in _walls(window))
    assert ys == [-3.0, 0.0, 0.0, 3.0]
    s.undo()  # Desfazer tira a última
    assert len(_walls(window)) == 3
    QTest.keyClick(window.plan, Qt.Key_Escape)
    assert window.toolbox.active.name == "select"


def test_ca03_ctrl_de_novo_volta_a_mover(window):
    wall = _wall(window)
    tool = _drag_start(window)
    tool.key("ctrl")
    tool.key("ctrl")
    assert not tool.copying()
    tool.release((1.3, 3.0), Mods())
    window.plan.after_tool_input()
    assert list(_walls(window)) == [wall]
    assert window.toolbox.active.name == "select"


def test_ca04_ctrl_d_abre_o_copiar(window):
    _wall(window)
    window.activate_tool("select")
    QTest.keyClick(window, Qt.Key_D, Qt.ControlModifier)
    assert window.toolbox.active.name == "copy"
