# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pegar e aplicar ajustes (conta‑gotas, spec/ui 55 §4), no núcleo."""

import pytest
from estrutura import created, valid

from brasbim.core import intervention, pick_settings
from brasbim.core.annotations import base
from brasbim.core.annotations import commands as ac
from brasbim.core.document import OpError
from brasbim.core.fillings import commands as fc
from brasbim.core.fillings import doors
from brasbim.core.walls import commands as cmd
from brasbim.core.walls import openings
from brasbim.core.walls.wall import read_state as read_wall


def _type(model, name, thickness):
    tx = model.commit(cmd.create_wall_type(model.doc, name, [
        {"material": "Alvenaria", "thickness": thickness}]))
    return model.doc.get(tx.ops[-1].id)


def test_aj01_parede_para_parede(model):
    t20 = _type(model, "Alvenaria 20", 0.20)
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (3, 6))
    model.commit(cmd.edit_wall(model.doc, a, type=t20.GlobalId, ref_line="axis",
                               top_mode="fixed", fixed_height=1.10, base_offset=0.15))
    path_b = read_wall(model.doc, b)["path"]
    settings = pick_settings.pick(model.doc, a)
    assert settings.group == "wall" and settings.label == "Parede · Alvenaria 20"
    model.commit(pick_settings.apply(model.doc, settings, [b]))
    state = read_wall(model.doc, b)
    assert state["type"] == t20.GlobalId and state["ref_line"] == "axis"
    assert (state["top_mode"], state["fixed_height"], state["base_offset"]) == (
        "fixed", pytest.approx(1.10), pytest.approx(0.15))
    assert state["path"] == path_b  # a posição não passa
    valid(model.doc.ifc)
    model.history.undo()
    assert read_wall(model.doc, b)["type"] == model.type14.GlobalId


def test_aj02_porta_para_porta_e_anotacao(model):
    wall = model.wall((0, 0), (8, 0), ref_line="axis")
    model.commit(fc.create_door_type(model.doc, "P1", defaults={"width": 0.8}))
    model.commit(fc.create_door_type(model.doc, "P2", defaults={"width": 0.9}))
    p1, p2 = sorted(model.doc.ifc.by_type("IfcDoorType"), key=lambda t: t.Name)
    d1 = created(model, fc.create_door(model.doc, p1, wall, 1.0))
    d2 = created(model, fc.create_door(model.doc, p2, wall, 5.0))
    model.commit(fc.edit_door(model.doc, d1, width=0.7, height=2.0))
    model.commit(pick_settings.apply(model.doc, pick_settings.pick(model.doc, d1), [d2]))
    assert doors.read_state(d2)["type"] == p1.GlobalId
    o2 = openings.read_state(fc.opening_of(d2))
    assert (o2["width"], o2["height"], o2["distance"]) == (pytest.approx(0.7),
                                                         pytest.approx(2.0),
                                                         pytest.approx(5.0))
    # anotação → anotação: estilo e marcador; os pontos não
    d_a = created(model, ac.create_dimension(model.doc, model.terreo, [(0, 1), (2, 1)]))
    d_b = created(model, ac.create_dimension(model.doc, model.terreo, [(0, 3), (5, 3)]))
    model.commit(ac.edit_element(model.doc, d_a, marker="arrow",
                                 style={"font": "Arial", "text_color": "#C0392B"}))
    text = created(model, ac.create_annotation(model.doc, "text", model.terreo, at=[1, 1],
                                               text="SALA"))
    model.commit(pick_settings.apply(model.doc, pick_settings.pick(model.doc, d_a),
                                     [d_b, text]))
    state_b = base.read_state(d_b)
    assert state_b["marker"] == "arrow" and state_b["style"]["font"] == "Arial"
    assert state_b["points"][1]["at"] == [5.0, 3.0]
    state_t = base.read_state(text)
    assert state_t["style"] == {"font": "Arial", "text_color": "#C0392B"}
    assert state_t["text"] == "SALA" and "marker" not in state_t


def test_aj03_classes_diferentes_e_varios(model):
    wall = model.wall((0, 0), (5, 0))
    model.commit(intervention.set_situation(model.doc, [wall.GlobalId], "A_DEMOLIR"))
    others = [model.wall((0, y), (4, y)) for y in (3, 6)]
    text = created(model, ac.create_annotation(model.doc, "text", model.terreo, at=[9, 9],
                                               text="X"))
    tx = model.commit(pick_settings.apply(model.doc, pick_settings.pick(model.doc, wall),
                                          [*others, text]))
    assert len({op.id for op in tx.ops}) >= 3  # uma transação para todos
    assert all(intervention.situation_of(model.doc, e) == "A_DEMOLIR" for e in [*others, text])
    model.history.undo()
    assert intervention.situation_of(model.doc, text) != "A_DEMOLIR"
    with pytest.raises(OpError):
        pick_settings.apply(model.doc, pick_settings.pick(model.doc, wall), [wall])


def test_aj04_ajustes_da_ferramenta():
    settings = pick_settings.Settings("wall", "Parede", "x", None,
                                      {"type": "T", "ref_line": "axis", "top_mode": "fixed",
                                       "fixed_height": 1.2})
    assert pick_settings.tool_changes(settings) == {"type": "T", "ref_line": "axis",
                                                    "fixed_height": 1.2, "top": "fixed"}


def test_aj07_cada_alvo_recebe_os_ajustes_da_sua_classe(model):
    """Como os ajustes de cada ferramenta: pegar de uma parede e depois de uma cota não
    apaga os da parede; aplicar nos dois leva a cada um os da classe dele."""
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (5, 4))
    model.commit(cmd.edit_wall(model.doc, a, ref_line="axis", top_mode="fixed",
                               fixed_height=1.10))
    d_a = created(model, ac.create_dimension(model.doc, model.terreo, [(0, 1), (2, 1)]))
    d_b = created(model, ac.create_dimension(model.doc, model.terreo, [(0, 3), (5, 3)]))
    model.commit(ac.edit_element(model.doc, d_a, marker="dot"))
    from_wall = pick_settings.pick(model.doc, a)
    from_dim = pick_settings.pick(model.doc, d_a)
    by_group = {from_wall.group: from_wall, from_dim.group: from_dim}
    model.commit(pick_settings.apply(model.doc, from_dim, [b, d_b], by_group))
    state = read_wall(model.doc, b)
    assert (state["ref_line"], state["top_mode"]) == ("axis", "fixed")
    assert base.read_state(d_b)["marker"] == "dot"
    # a origem de cada classe fica de fora sem recusar o resto
    model.commit(pick_settings.apply(model.doc, from_dim, [a, d_a, b], by_group))


def test_aj08_ferramentas_que_recebem_os_ajustes():
    assert pick_settings.tools_for("wall") == ("wall", "arc", "rectangle")
    assert pick_settings.tools_for("annotation:dimension") == ("dimension",)
    column = pick_settings.Settings("column", "Pilar", "x", None,
                                    {"type": "T", "angle": 30.0, "top_mode": "fixed",
                                     "fixed_height": 2.5})
    assert pick_settings.tool_changes(column) == {"angle": 30.0, "fixed_height": 2.5,
                                                  "top": "fixed"}
    door = pick_settings.Settings("door", "Porta", "x", None,
                                  {"type": "P", "width": 0.7, "height": 2.0, "base": 1.1,
                                   "opens_to": "left"})
    assert pick_settings.tool_changes(door) == {"type": "P", "width": 0.7, "height": 2.0,
                                                "base": 1.1}
