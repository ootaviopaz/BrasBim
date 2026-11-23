# SPDX-License-Identifier: LGPL-3.0-or-later
"""Janela Localizar e substituir (spec/ui 55 §3)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from brasbim.core import find
from brasbim.core.annotations import base
from brasbim.core.annotations import commands as ac
from brasbim.core.walls import commands as cmd


@pytest.fixture(autouse=True)
def _fecha_a_janela(window):
    """A janela não modal aberta tiraria o foco dos testes seguintes."""
    yield
    dialog = getattr(window, "find_dialog", None)
    if dialog is not None:
        dialog.close()
        dialog.deleteLater()


def _model(window):
    s = window.session
    wall_type = window.toolbox.tools["wall"].options.type
    for y in (0, 4):
        s.run(lambda y=y: cmd.create_wall(s.doc, wall_type, s.storey, (0, y), (5, y)))
    s.run(lambda: ac.create_annotation(s.doc, "text", s.storey, at=[1, 1], text="SALA"))
    s.run(lambda: ac.create_annotation(s.doc, "text", s.storey, at=[1, 2], text="sala 2"))
    return s


def _check(dialog, key):
    for i in range(dialog.classes.count()):
        item = dialog.classes.item(i)
        if item.data(Qt.UserRole) == key:
            item.setCheckState(Qt.Checked)


def test_ls06_janela_localizar(window):
    s = _model(window)
    QTest.keyClick(window, Qt.Key_F, Qt.ControlModifier | Qt.ShiftModifier)
    dialog = window.find_dialog
    assert dialog.isVisible() and not dialog.isModal()
    _check(dialog, "IfcWall")
    dialog.select("replace")
    assert len(s.selection) == 2 and dialog.status.text() == "2 elementos"
    _check(dialog, "annotation:text")
    row = dialog.add_row()
    row.field.setCurrentIndex(row.field.findData("text"))
    row.op.setCurrentIndex(row.op.findData("contains"))
    row.value.setText("sala")
    dialog.select("add")
    assert len(s.selection) == 4
    dialog.select("remove")
    assert len(s.selection) == 2
    dialog.save_as("Textos de sala")
    assert find.saved(s.doc)[0]["criteria"]["rows"][0]["value"] == "sala"
    dialog.load(find.default_criteria())
    dialog.saved.setCurrentIndex(1)
    dialog._load_saved(1)
    assert len(dialog.found) == 2


def test_ls07_substituir_pela_janela(window):
    s = _model(window)
    window.open_find()
    dialog = window.find_dialog
    _check(dialog, "annotation:text")
    dialog.tabs.setCurrentIndex(1)
    dialog.find_text.setText("sala")
    dialog.new_text.setText("Estar")
    dialog.show_occurrences()
    assert dialog.preview.count() == 2
    dialog.replace()
    texts = sorted(base.read_state(e)["text"] for e in s.doc.ifc.by_type("IfcAnnotation"))
    assert texts == ["Estar", "Estar 2"]
    s.undo()  # uma transação só
    texts = sorted(base.read_state(e)["text"] for e in s.doc.ifc.by_type("IfcAnnotation"))
    assert texts == ["SALA", "sala 2"]
    dialog.what.setCurrentIndex(dialog.what.findData("style"))
    dialog.style_text_pen.setCurrentIndex(dialog.style_text_pen.findData(9))
    dialog.replace()
    assert all(base.read_state(e)["style"] == {"text_pen": 9}
               for e in s.doc.ifc.by_type("IfcAnnotation"))
