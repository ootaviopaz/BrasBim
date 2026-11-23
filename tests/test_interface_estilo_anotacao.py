# SPDX-License-Identifier: LGPL-3.0-or-later
"""Estilo das anotações na interface (spec/ui 55 §2.3): ficha, várias de uma vez e o
desenho na planta."""

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QComboBox, QFontComboBox, QLineEdit

from brasbim.core.annotations import base, dimensions
from brasbim.core.annotations import commands as ac


@pytest.fixture(autouse=True)
def _planta_visivel(window):
    window.plan.origin = QPointF(150, 450)


def _dims(window, n=2):
    s = window.session
    for i in range(n):
        s.run(lambda i=i: ac.create_dimension(s.doc, s.storey, [(0, i), (5, i)], "fixed", 0.0,
                                              -0.6))
    return [e for e in s.doc.ifc.by_type("IfcAnnotation")
            if base.kind_of(e) is dimensions.DIMENSION]


def _rows(window, group_title):
    group = next(g for g in window.properties.groups if g.title == group_title)
    return dict(group.rows)


def test_ea05_varias_cotas_de_uma_vez(window):
    s = window.session
    dims = _dims(window)
    s.select([d.GlobalId for d in dims])
    window.properties._rebuild()
    rows = _rows(window, "Texto")
    assert isinstance(rows["Fonte"], QFontComboBox)
    altura = rows["Altura"]
    altura.setCurrentIndex(altura.findData(5.0))
    assert all(base.read_state(d)["style"] == {"size": 5.0} for d in dims)
    assert len(s.history.undo_stack[-1].ops) == 2  # uma transação para as duas
    window.properties._rebuild()
    espessura = _rows(window, "Linha")["Espessura"]
    espessura.setCurrentIndex(espessura.findData(0.5))
    assert all(base.read_state(d)["style"] == {"size": 5.0, "weight": 0.5} for d in dims)
    window.plan.grab()  # desenha com o estilo
    s.undo()
    assert all(base.read_state(d)["style"] == {"size": 5.0} for d in dims)


def test_ea05b_texto_do_trecho_pela_ficha(window):
    s = window.session
    (dim,) = _dims(window, 1)
    s.select([dim.GlobalId])
    window.properties._rebuild()
    rows = _rows(window, "Texto da cota")
    field = rows["Trecho 1 (5,00)"]
    assert isinstance(field, QLineEdit) and field.text() == "<medida>"
    field.setText("VER DETALHE")
    field.editingFinished.emit()
    assert base.read_state(dim)["texts"] == {"0": "VER DETALHE"}
    assert base.build(s.doc, dim).texts[0].fixed
    window.plan.grab()  # sublinhado na tela
    window.properties._rebuild()
    marker = _rows(window, "Marcador")["Marcador"]
    assert isinstance(marker, QComboBox)
    marker.setCurrentIndex(marker.findData("arrow"))
    assert base.read_state(dim)["marker"] == "arrow"
    window.plan.grab()
