# SPDX-License-Identifier: LGPL-3.0-or-later
"""Penas de cada elemento e das anotações (spec/ui 57)."""

import ifcopenshell.util.element as ue
import pytest
from estrutura import check_history, created, valid

from brasbim.core import element_pens, pick_settings, plan, transform
from brasbim.core.annotations import base
from brasbim.core.annotations import commands as ac
from brasbim.core.annotations import style as annotation_style
from brasbim.core.document import OpError
from brasbim.core.walls import commands as cmd


def test_pe01_penas_da_parede_no_ifc_e_na_planta(model):
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (5, 4))
    check_history(model, lambda: model.commit(element_pens.set_pens(
        model.doc, [a], cut=6, fill=9, view=11)))
    assert element_pens.read(a) == {"cut": 6, "fill": 9, "view": 11}
    assert ue.get_pset(a, element_pens.PSET)["Contorno"] == 6
    drawn = plan.storey_plan(model.doc, model.terreo)
    assert drawn.element_pens == {a.GlobalId: {"cut": 6, "fill": 9, "view": 11}}
    assert {e.pen_no for e in drawn.edges} == {6, None}  # a outra parede segue a tabela
    assert {r.pen_no for r in drawn.regions} >= {9}
    model.commit(element_pens.set_pens(model.doc, [a, b], cut=None))
    assert element_pens.read(a) == {"fill": 9, "view": 11} and element_pens.read(b) == {}
    with pytest.raises(OpError):
        element_pens.set_pens(model.doc, [a], cut=999)
    valid(model.doc.ifc)


def test_pe02_copia_e_conta_gotas_levam_as_penas(model):
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (5, 4))
    model.commit(element_pens.set_pens(model.doc, [a], cut=5))
    tx = model.commit(transform.copy_elements(model.doc, [a], (0, 8)))
    copy = model.doc.get(next(op.id for op in tx.ops if op.op == "wall.create"))
    assert element_pens.read(copy) == {"cut": 5}
    model.commit(pick_settings.apply(model.doc, pick_settings.pick(model.doc, a), [b]))
    assert element_pens.read(b) == {"cut": 5}


def test_pe03_proximas_criacoes(model):
    tx = cmd.create_wall(model.doc, model.type14, model.terreo, (0, 0), (3, 0))
    tx = element_pens.stamp_created(model.doc, tx, {"wall": {"cut": 4, "view": 2}})
    model.commit(tx)
    wall = model.doc.get(tx.ops[0].id)
    assert element_pens.read(wall) == {"cut": 4, "view": 2}


def test_pe04_pena_da_anotacao(model):
    dim = created(model, ac.create_dimension(model.doc, model.terreo, [(0, 0), (5, 0)]))
    model.commit(ac.edit_element(model.doc, dim, marker="arrow",
                                 style={"line_color": "#C0392B", "weight": 0.35}))
    model.commit(annotation_style.edit_style(model.doc, [dim], pen=11, text_pen=9))
    state = base.read_state(dim)
    assert state["style"] == {"pen": 11, "text_pen": 9}  # a pena tira a cor solta
    built = base.build(model.doc, dim)
    assert {s.pen_no for s in built.strokes} == {11}
    assert built.texts[0].pen_no == 9 and all(f.fill["pen_no"] == 11 for f in built.fills)
    rep = next(r for r in dim.Representation.Representations
               if r.RepresentationIdentifier == "Annotation")
    curve = next(i for i in rep.Items if i.is_a("IfcGeometricCurveSet"))
    colour = curve.StyledByItem[0].Styles[0].CurveColour  # azul da pena 11
    assert round(colour.Blue * 255) == 0xC4
    with pytest.raises(OpError):
        annotation_style.edit_style(model.doc, [dim], pen=0)
    valid(model.doc.ifc)


def test_tc01_mover_so_o_texto_da_cota(model):
    from brasbim.core import storeys
    from brasbim.core.annotations import dimensions

    dim = created(model, ac.create_dimension(model.doc, model.terreo,
                                             [(0, 0), (2, 0), (5, 0)], "fixed", 0.0, -0.6))
    before = base.build(model.doc, dim)
    line = before.strokes[0].points
    state = base.read_state(dim)
    target = (1.0, -1.5)  # o primeiro número vai para baixo e para a esquerda
    move = dimensions.text_move(model.doc, state, 0, target)
    model.commit(ac.edit_element(model.doc, dim, text_moves={"0": move}))
    after = base.build(model.doc, dim)
    assert after.strokes[0].points == line  # a linha de cota não sai do lugar
    assert after.texts[0].at == pytest.approx(target)
    assert after.texts[1].at == pytest.approx(before.texts[1].at)  # o outro texto fica
    assert len(after.strokes) == len(before.strokes) + 1  # chamada até o texto longe
    k = storeys.paper(model.terreo, 1.0)
    spots = dimensions.text_spots(model.doc, base.read_state(dim), k)
    assert spots[0][2] == pytest.approx(target)
    from brasbim.core import transform

    model.commit(transform.mirror_elements(model.doc, [dim], (0, 0), (1, 0)))
    assert base.read_state(dim)["text_moves"]["0"][1] == pytest.approx(-move[1])
    model.history.undo()
    model.commit(ac.edit_element(model.doc, dim, text_moves=None))
    assert base.build(model.doc, dim).texts[0].at == pytest.approx(before.texts[0].at)
