# SPDX-License-Identifier: LGPL-3.0-or-later
"""Cotas em níveis do pavimento (spec/ui 59)."""

import pytest
from estrutura import column_type, created
from test_assistente import _call, ctx  # noqa: F401  (fixture do Assistente)

from brasbim.core.annotations import base, dimensions
from brasbim.core.annotations import commands as ac
from brasbim.core.annotations import dimension_levels as dl
from brasbim.core.fillings import commands as fc
from brasbim.core.structure import commands as sc
from brasbim.core.walls import commands as cmd
from brasbim.core.walls.wall import read_state as read_wall


def _house(model, column=True):
    """Retângulo 10 × 6 (paredes de 14 para dentro), duas janelas embaixo, um pilar de
    20 × 40 na parede de baixo (sai 13 cm para fora: um ressalto na fachada) e uma parede
    interna em x = 4."""
    model.commit(cmd.create_rectangle(model.doc, model.type14, model.terreo, (0, 0), (10, 6)))
    walls = model.doc.ifc.by_type("IfcWall")
    south = min(walls, key=lambda w: sum(read_wall(model.doc, w)["path"][k][1]
                                          for k in ("start", "end")))
    window_type = model.doc.get(model.commit(fc.create_window_type(model.doc, "J1")).ops[0].id)
    for at in (1.5, 6.0):
        model.commit(fc.create_window(model.doc, window_type, south, at))
    column = created(model, sc.create_column(model.doc, column_type(model), model.terreo,
                                             (5.0, 0.07))) if column else None
    model.wall((4.0, 0.0), (4.0, 6.0))
    return south, column


def _auto(model):
    out = {}
    for e in model.doc.ifc.by_type("IfcAnnotation"):
        state = base.read_state(e)
        auto = state.get("auto")
        if auto:
            key = (auto.get("side"), auto.get("level")) if "side" in auto else \
                (auto["room"], auto["axis"])
            out[key] = (e, state)
    return out


def _measures(model, state):
    return [round(v, 3) for v in dimensions.measures(model.doc, state)]


def _line(state, model):
    """Posição da linha de cota (y das horizontais, x das verticais)."""
    p0 = dimensions.points(model.doc, state)[0]
    _, n = dimensions.frame(state, [p0, p0])
    return p0[1] + state["offset"] * n[1] if state["angle"] == 0.0 else \
        p0[0] + state["offset"] * n[0]


def test_cn01_tres_linhas_por_lado_na_ordem(model):
    _house(model)
    model.commit(dl.create(model.doc, model.terreo)[0])
    found = _auto(model)
    bottom = {lv: found[("bottom", lv)][1] for lv in dl.LEVELS}
    # cantos, vãos e o ressalto do pilar (4,90 a 5,10)
    assert _measures(model, bottom["openings"]) == [2.8, 1.2, 0.9, 0.2, 2.2, 1.2, 1.5]
    assert _measures(model, bottom["total"]) == [10.0]
    assert sum(_measures(model, bottom["openings"])) == pytest.approx(10.0)
    structure = _measures(model, bottom["structure"])
    assert sum(structure) == pytest.approx(10.0) and 0.2 in structure  # face a face do pilar
    assert 0.14 in structure  # parede interna e as dos cantos, face a face
    # de dentro para fora: aberturas, estrutura, total; a 12 mm e depois 7 mm (1:50)
    lines = [_line(bottom[lv], model) for lv in dl.LEVELS]
    assert lines == pytest.approx([-0.13 - 0.6, -0.13 - 0.95, -0.13 - 1.3])  # do ressalto
    # todos os pontos presos ao modelo
    assert all(p.get("ref") for lv in dl.LEVELS for p in bottom[lv]["points"])
    # na fachada de cima não há vãos nem pilar: a linha de aberturas repetiria o total
    assert ("top", "openings") not in found and ("top", "total") in found


def test_cn02_so_alguns_niveis_e_lados(model):
    _house(model, column=False)
    model.commit(dl.create(model.doc, model.terreo, ["total", "openings"], ["left"])[0])
    found = _auto(model)
    assert set(found) == {("left", "total")}  # sem vãos à esquerda: só o total
    assert _measures(model, found[("left", "total")][1]) == [6.0]


def test_cn03_planta_em_l(model):
    model.wall((0, 0), (10, 0), ref_line="axis")
    model.wall((10, 0), (10, 4), ref_line="axis")
    model.wall((10, 4), (6, 4), ref_line="axis")
    model.wall((6, 4), (6, 8), ref_line="axis")
    model.wall((6, 8), (0, 8), ref_line="axis")
    model.wall((0, 8), (0, 0), ref_line="axis")
    model.commit(dl.create(model.doc, model.terreo, ["openings", "total"], ["top"])[0])
    found = _auto(model)
    # vista de cima: o trecho alto (x 0–6) e o recuado (x 6–10) entram na mesma linha
    detail = _measures(model, found[("top", "openings")][1])
    total = _measures(model, found[("top", "total")][1])
    assert len(detail) == 2 and sum(detail) == pytest.approx(total[0])
    assert total[0] == pytest.approx(10.14)


def test_cn04_associativa(model):
    _house(model)
    model.commit(dl.create(model.doc, model.terreo, ["openings", "total"], ["bottom"])[0])
    window = next(o for o in model.doc.ifc.by_type("IfcWindow"))
    model.commit(fc.edit_door(model.doc, window, width=1.5))
    found = _auto(model)
    assert sum(_measures(model, found[("bottom", "openings")][1])) == pytest.approx(10.0)
    assert 1.5 in _measures(model, found[("bottom", "openings")][1])


def test_cn05_refazer_nao_duplica_e_a_mexida_fica(model):
    _house(model)
    model.commit(dl.create(model.doc, model.terreo, sides=["bottom"])[0])
    first = _auto(model)
    edited = first[("bottom", "total")][0]
    model.commit(ac.edit_element(model.doc, edited, prefix="L="))
    tx, found = dl.create(model.doc, model.terreo, sides=["bottom"])
    model.commit(tx)
    again = _auto(model)
    assert set(again) == set(first)  # nada duplicado
    assert again[("bottom", "total")][0] == edited and found["kept"] == [edited.GlobalId]
    assert again[("bottom", "openings")][0] != first[("bottom", "openings")][0]  # refeita
    model.history.undo()  # um Desfazer volta as de antes
    assert {e.GlobalId for e, _ in _auto(model).values()} == \
        {e.GlobalId for e, _ in first.values()}


def test_cn06_comodos(model):
    _house(model)
    model.commit(ac.create_space(model.doc, model.terreo,
                                 [(0.14, 0.14), (4.0, 0.14), (4.0, 5.86), (0.14, 5.86)]))
    model.commit(dl.create(model.doc, model.terreo, ["rooms"])[0])
    found = _auto(model)
    (space,) = model.doc.ifc.by_type("IfcSpace")
    width = found[(space.GlobalId, "x")][1]
    depth = found[(space.GlobalId, "y")][1]
    assert _measures(model, width) == [3.86] and _measures(model, depth) == [5.72]
    assert _line(width, model) == pytest.approx(0.14 + 0.4)  # dentro, a 8 mm (1:50)


def test_cn07_assistente(ctx, model):  # noqa: F811
    _call(ctx, "layout_rooms", rooms=[
        {"name": "Sala", "x": 0, "y": 0, "width": 5, "depth": 4},
        {"name": "Cozinha", "x": 5, "y": 0, "width": 3, "depth": 4}])
    _call(ctx, "insert_window", at=[2, 0], type="J1")
    n = len(model.history.undo_stack)
    out, error = _call(ctx, "dimension_levels", levels=["openings", "structure", "total",
                                                         "rooms"])
    assert not error, out
    assert len(model.history.undo_stack) == n + 1  # um Desfazer
    found = _auto(model)
    assert ("bottom", "openings") in found and ("bottom", "total") in found
    assert sum(1 for k in found if k[1] in ("x", "y")) == 4  # 2 ambientes × 2
    again, error = _call(ctx, "dimension_levels")
    assert not error and again["refeitas"] >= 3
    _, error = _call(ctx, "dimension_levels", levels=["diagonal"])
    assert error


def test_cn08_janela_cotar_pavimento(window):
    s = window.session
    s.run(lambda: cmd.create_rectangle(s.doc, window.toolbox.tools["wall"].options.type,
                                       s.storey, (0, 0), (8, 5)))
    window.dimension_storey()
    dialog = window.dimension_dialog
    assert dialog.chosen_levels() == ["openings", "structure", "total"]
    assert dialog.chosen_sides() == ["bottom", "top", "left", "right"]
    for box in dialog.levels.values():
        box.setChecked(False)
    assert not dialog.ok_button.isEnabled()  # sem nível, não cota
    dialog.levels["rooms"].setChecked(True)
    assert dialog.ok_button.isEnabled() and not dialog.sides["top"].isEnabled()
    dialog.close()
    assert window.dimension_storey(["total"], ["bottom", "left"])
    dims = [e for e in s.doc.ifc.by_type("IfcAnnotation") if base.read_state(e).get("auto")]
    assert len(dims) == 2
    s.undo()
    assert not [e for e in s.doc.ifc.by_type("IfcAnnotation")
                if base.read_state(e).get("auto")]
