# SPDX-License-Identifier: LGPL-3.0-or-later
"""Estilo das anotações e texto da cota (spec/ui 55 §2), no núcleo."""

import ifcopenshell.util.element as ue
import pytest
from estrutura import created, valid

from brasbim.core.annotations import base, dimensions
from brasbim.core.annotations import commands as ac
from brasbim.core.document import OpError
from brasbim.core.walls import commands as cmd


def _rep_items(element):
    rep = next(r for r in element.Representation.Representations
               if r.RepresentationIdentifier == "Annotation")
    return rep.Items


def _dim(model, points=((0, 0), (5, 0))):
    return created(model, ac.create_dimension(model.doc, model.terreo, list(points),
                                              "fixed", 0.0, -0.6))


def test_ea01_estilo_da_cota_no_ifc(model):
    dim = _dim(model)
    style = {"font": "Arial", "size": 3.5, "bold": True, "italic": True,
             "text_color": "#C0392B", "line_color": "#1F5FC4", "weight": 0.35}
    model.commit(ac.edit_element(model.doc, dim, style=style))
    state = base.read_state(dim)
    assert state["style"] == style
    built = base.build(model.doc, dim)
    (text,) = built.texts
    assert (text.font, text.bold, text.italic, text.color) == ("Arial", True, True, "#C0392B")
    assert text.height == pytest.approx(3.5 * 0.05)  # 1:50
    assert all(s.color == "#1F5FC4" and s.weight == 0.35 and not s.pen for s in built.strokes)
    (literal,) = [i for i in _rep_items(dim) if i.is_a("IfcTextLiteralWithExtent")]
    (text_style,) = literal.StyledByItem[0].Styles
    font = text_style.TextFontStyle
    assert font.FontFamily[0] == "Arial" and font.FontStyle == "italic"
    assert font.FontWeight == "bold"
    colour = text_style.TextCharacterAppearance.Colour
    assert (round(colour.Red * 255), round(colour.Green * 255)) == (0xC0, 0x39)
    curves = [i for i in _rep_items(dim) if i.is_a("IfcGeometricCurveSet")]
    curve_style = curves[0].StyledByItem[0].Styles[0]
    assert round(curve_style.CurveColour.Blue * 255) == 0xC4
    assert curve_style.CurveWidth.wrappedValue == pytest.approx(0.00035)
    valid(model.doc.ifc)
    model.history.undo()
    assert "style" not in base.read_state(dim)
    (text,) = base.build(model.doc, dim).texts
    assert text.font is None and text.color is None


def test_ea01b_estilo_invalido(model):
    dim = _dim(model)
    for bad in ({"text_color": "vermelho"}, {"size": 0.1}, {"weight": 9.0}, {"xyz": 1}):
        with pytest.raises(OpError):
            model.commit(ac.edit_element(model.doc, dim, style=bad))


def test_ea01c_texto_e_linha_com_estilo(model):
    text = created(model, ac.create_annotation(model.doc, "text", model.terreo, at=[1, 1],
                                               text="SALA", size=2.5))
    model.commit(ac.edit_element(model.doc, text, style={"font": "Times New Roman",
                                                        "text_color": "#1E8449"}))
    (t,) = base.build(model.doc, text).texts
    assert t.font == "Times New Roman" and t.color == "#1E8449"
    line = created(model, ac.create_annotation(model.doc, "line2d", model.terreo,
                                               points=[[0, 0], [4, 0]], weight=0.25,
                                               dash="dashed"))
    model.commit(ac.edit_element(model.doc, line, style={"line_color": "#D68910"}))
    (s,) = base.build(model.doc, line).strokes
    assert s.color == "#D68910" and s.dash == "dashed" and s.pen


@pytest.mark.parametrize("marker", ["arrow", "open_arrow", "dot", "none", "tick"])
def test_ea02_marcadores(model, marker):
    dim = _dim(model, ((0, 0), (2, 0), (5, 0)))
    model.commit(ac.edit_element(model.doc, dim, marker=marker, marker_size=4.0))
    built = base.build(model.doc, dim)
    if marker == "arrow":
        assert len(built.fills) == 4  # 2 trechos × 2 pontas
        assert any(i.is_a("IfcAnnotationFillArea") for i in _rep_items(dim))
    elif marker == "dot":
        assert len(built.fills) == 3
    else:
        assert not built.fills
    # linha de cota + 3 chamadas + marcadores de traço
    extra = {"tick": 3, "open_arrow": 4, "none": 0}.get(marker, 0)
    assert len(built.strokes) == 4 + extra
    valid(model.doc.ifc)


def test_ea03_texto_trocado_acompanha_a_medida(model):
    wall = model.wall((0, 0), (5, 0), ref_line="axis")
    refs = [{"kind": "wall", "gid": wall.GlobalId, "end": e, "face": "axis"}
            for e in ("start", "end")]
    items = [(dimensions.resolve(model.doc, r), r) for r in refs]
    dim = created(model, ac.create_dimension(model.doc, model.terreo, items, offset=-0.6))
    model.commit(ac.edit_element(model.doc, dim, texts={"0": "≈ <medida> (var.)"}))
    (t,) = base.build(model.doc, dim).texts
    assert t.text == "≈ 5,00 (var.)" and not t.fixed
    model.commit(cmd.move_wall_end(model.doc, wall, "end", (6, 0)))
    assert base.build(model.doc, dim).texts[0].text == "≈ 6,00 (var.)"
    model.commit(ac.edit_element(model.doc, dim, texts={"0": "VER DETALHE"}))
    (t,) = base.build(model.doc, dim).texts
    assert t.text == "VER DETALHE" and t.fixed
    (literal,) = [i for i in _rep_items(dim) if i.is_a("IfcTextLiteralWithExtent")]
    assert literal.Literal == "VER DETALHE"
    model.commit(ac.edit_element(model.doc, dim, texts=None))  # voltar à medida
    assert base.build(model.doc, dim).texts[0].text == "6,00"
    assert "texts" not in base.read_state(dim)


def test_ea04_prefixo_sufixo_e_casas(model):
    dim = _dim(model, ((0, 0), (1.2345, 0), (3, 0)))
    model.commit(ac.edit_element(model.doc, dim, prefix="L=", suffix=" m", decimals=3))
    assert [t.text for t in base.build(model.doc, dim).texts] == ["L=1,234 m", "L=1,766 m"]
    model.commit(ac.edit_element(model.doc, dim, texts={"1": "<medida>"}))
    assert [t.text for t in base.build(model.doc, dim).texts] == ["L=1,234 m", "1,766"]
    with pytest.raises(OpError):
        model.commit(ac.edit_element(model.doc, dim, decimals=7))
    assert ue.get_pset(dim, base.PSET)["Tipo"] == "dimension"
