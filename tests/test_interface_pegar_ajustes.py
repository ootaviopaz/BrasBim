# SPDX-License-Identifier: LGPL-3.0-or-later
"""Conta-gotas na interface (spec/ui 55 §4.1): Alt+clique pega, Ctrl+Alt+clique aplica,
mini-barra e ferramenta."""

import pytest
from PySide6.QtCore import QPointF, Qt
from test_interface import _click

from brasbim.core.walls import commands as cmd
from brasbim.core.walls.wall import read_state as read_wall
from brasbim.ui.tools import selection_actions


@pytest.fixture(autouse=True)
def _planta_visivel(window):
    window.plan.origin = QPointF(150, 450)


def _two_walls(window):
    s = window.session
    wall_type = window.toolbox.tools["wall"].options.type
    s.run(lambda: cmd.create_wall(s.doc, wall_type, s.storey, (0, 0), (5, 0)))
    s.run(lambda: cmd.create_wall(s.doc, wall_type, s.storey, (0, 4), (5, 4)))
    a, b = sorted(s.doc.ifc.by_type("IfcWall"),
                  key=lambda w: read_wall(s.doc, w)["path"]["start"][1])
    s.run(lambda: cmd.edit_wall(s.doc, a, top_mode="fixed", fixed_height=1.10))
    return a, b


def test_aj05_alt_clique_pega_e_ctrl_alt_clique_aplica(window):
    s = window.session
    a, b = _two_walls(window)
    window.activate_tool("select")
    _click(window, (1.3, 0.0), Qt.AltModifier)
    assert window.ctx.picked is not None and window.ctx.picked.source == a.GlobalId
    assert not s.selection  # o Alt+clique não seleciona
    _click(window, (1.3, 4.0), Qt.AltModifier | Qt.ControlModifier)
    state = read_wall(s.doc, b)
    assert (state["top_mode"], state["fixed_height"]) == ("fixed", pytest.approx(1.10))
    s.undo()
    assert read_wall(s.doc, b)["top_mode"] != "fixed"


def test_aj06_mini_barra_e_ferramenta(window):
    s = window.session
    a, b = _two_walls(window)
    s.select([a.GlobalId])
    assert "pick_settings" in selection_actions(s.doc, s.selection)
    window.run_selection_action("pick_settings")
    s.select([b.GlobalId])
    window.run_selection_action("apply_settings")
    assert read_wall(s.doc, b)["top_mode"] == "fixed"
    # com a ferramenta Parede ativa, Alt+clique leva os ajustes para ela
    window.activate_tool("wall")
    _click(window, (1.3, 0.0), Qt.AltModifier)
    options = window.toolbox.active.options
    assert options.top == "fixed" and options.fixed_height == pytest.approx(1.10)
