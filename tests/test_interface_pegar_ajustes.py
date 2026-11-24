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


def test_aj07_com_selecionar_os_ajustes_vao_para_a_ferramenta(window):
    """Pegar com a ferramenta Selecionar já prepara a ferramenta Parede (spec/ui 55 §4.1)."""
    _two_walls(window)
    window.activate_tool("select")
    _click(window, (1.3, 0.0), Qt.AltModifier)
    assert window.toolbox.active.name == "select"  # a ferramenta não troca
    options = window.toolbox.tools["wall"].options
    assert options.top == "fixed" and options.fixed_height == pytest.approx(1.10)


def test_aj08_ctrl_alt_clique_na_selecao_aplica_em_todos(window):
    s = window.session
    a, b = _two_walls(window)
    wall_type = window.toolbox.tools["wall"].options.type
    s.run(lambda: cmd.create_wall(s.doc, wall_type, s.storey, (0, 8), (5, 8)))
    c = next(w for w in s.doc.ifc.by_type("IfcWall") if w not in (a, b))
    window.activate_tool("select")
    _click(window, (1.3, 0.0), Qt.AltModifier)
    s.select([b.GlobalId, c.GlobalId])
    _click(window, (1.3, 4.0), Qt.AltModifier | Qt.ControlModifier)
    assert all(read_wall(s.doc, w)["top_mode"] == "fixed" for w in (b, c))
    s.undo()  # uma transação para todos
    assert all(read_wall(s.doc, w)["top_mode"] != "fixed" for w in (b, c))


def test_aj09_alt_realca_e_nao_leva_o_foco_ao_menu(window):
    """No Windows, Alt sozinho levava o foco ao menu Arquivo e a planta parava de receber
    as teclas."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    a, _ = _two_walls(window)
    style = QApplication.style().name()
    QApplication.setStyle("windows")  # o estilo em que Alt navega pelo menu
    try:
        window.activate_tool("select")
        window.plan.setFocus()
        # cursor sobre a parede (sem tela, o mouse de teste não chega à vista)
        window.plan.mouse_pos = window.plan.to_screen((1.3, 0.0))
        window.plan.underMouse = lambda: True
        QTest.keyPress(window.plan, Qt.Key_Alt, Qt.AltModifier)
        assert window.plan.settings_target == a.GlobalId
        QTest.keyRelease(window.plan, Qt.Key_Alt, Qt.NoModifier)
        QApplication.processEvents()
        assert QApplication.focusWidget() is window.plan
        assert window.menuBar().activeAction() is None
        assert window.plan.settings_target is None
    finally:
        QApplication.setStyle(style)


def test_aj10_conta_gotas_no_3d(window):
    """Alt+clique e Ctrl+Alt+clique também na vista 3D (o elemento vem do clique no 3D)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    s = window.session
    a, b = _two_walls(window)
    view = window.view3d
    window.activate_tool("select")
    view.element_at = lambda pos: a.GlobalId  # sem placa de vídeo nos testes
    QTest.mouseClick(view, Qt.LeftButton, Qt.AltModifier, QPoint(50, 50))
    assert window.ctx.picked is not None and window.ctx.picked.source == a.GlobalId
    view.element_at = lambda pos: b.GlobalId
    QTest.mouseClick(view, Qt.LeftButton, Qt.AltModifier | Qt.ControlModifier, QPoint(50, 50))
    assert read_wall(s.doc, b)["top_mode"] == "fixed"
