# SPDX-License-Identifier: LGPL-3.0-or-later
"""Localizar e substituir (spec/ui 55 §3), no núcleo."""

import ifcopenshell.util.element as ue
import pytest
from estrutura import check_history, created, valid

from brasbim.core import find, intervention
from brasbim.core.annotations import base
from brasbim.core.annotations import commands as ac
from brasbim.core.document import OpError
from brasbim.core.walls import commands as cmd


def _type(model, name, thickness):
    tx = model.commit(cmd.create_wall_type(model.doc, name, [
        {"material": "Alvenaria", "thickness": thickness}]))
    return model.doc.get(tx.ops[-1].id)


def _crit(*rows, classes=(), scope="storey"):
    return {"classes": list(classes), "rows": list(rows), "scope": scope}


def test_ls01_criterios_e_ou_e_pavimentos(model):
    t20 = _type(model, "Alvenaria 20", 0.20)
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (5, 4))
    model.commit(cmd.edit_wall(model.doc, b, type=t20.GlobalId))
    up = created(model, cmd.create_wall(model.doc, t20, model.superior, (0, 0), (3, 0)))
    text = created(model, ac.create_annotation(model.doc, "text", model.terreo, at=[1, 1],
                                               text="Planta baixa"))
    got = find.find(model.doc, _crit(classes=["IfcWall"]), model.terreo)
    assert got == sorted([a.GlobalId, b.GlobalId])
    row = {"field": "type", "op": "contains", "value": "20"}
    assert find.find(model.doc, _crit(row, classes=["IfcWall"]), model.terreo) == [b.GlobalId]
    assert find.find(model.doc, _crit(row, scope="all"), model.terreo) == sorted(
        [b.GlobalId, up.GlobalId])
    ou = _crit(classes=["IfcWall", "annotation:text"])
    assert text.GlobalId in find.find(model.doc, ou, model.terreo)
    texto = {"field": "text", "op": "starts", "value": "PLANTA"}
    assert find.find(model.doc, _crit(texto), model.terreo) == [text.GlobalId]
    assert find.summary(model.doc, [b.GlobalId, up.GlobalId]) == "2 elementos, 2 pavimentos"


def test_ls02_propriedade_e_quantidade(model):
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (2, 4))
    model.commit(cmd.edit_wall(model.doc, a, common={"IsExternal": True}))
    ext = {"field": "property", "pset": "Pset_WallCommon", "prop": "IsExternal",
           "op": "is", "value": "sim"}
    assert find.find(model.doc, _crit(ext), model.terreo) == [a.GlobalId]
    qto = next(iter(ue.get_psets(a, qtos_only=True).values()))
    name = next(k for k in qto if k.endswith("Length"))
    between = {"field": "quantity", "prop": name, "op": "between", "value": "1;3"}
    assert find.find(model.doc, _crit(between), model.terreo) == [b.GlobalId]
    with pytest.raises(OpError):
        find.find(model.doc, _crit({"field": "xyz", "op": "is", "value": 1}), model.terreo)


def test_ls03_criterios_salvos(model, tmp_path):
    crit = _crit({"field": "type", "op": "contains", "value": "14"}, classes=["IfcWall"])
    model.commit(find.save_criteria(model.doc, "Paredes de 14", crit))
    assert find.saved(model.doc) == [{"name": "Paredes de 14", "criteria": crit}]
    model.reopen(tmp_path)
    assert find.saved(model.doc)[0]["name"] == "Paredes de 14"
    model.commit(find.delete_criteria(model.doc, "Paredes de 14"))
    assert find.saved(model.doc) == []


def test_ls04_substituir_texto(model):
    t = created(model, ac.create_annotation(model.doc, "text", model.terreo, at=[1, 1],
                                            text="SALA de estar\nsala"))
    dim = created(model, ac.create_dimension(model.doc, model.terreo, [(0, 0), (4, 0)]))
    model.commit(ac.edit_element(model.doc, dim, texts={"0": "<medida> SALA"}))
    gids = [t.GlobalId, dim.GlobalId]
    found = find.occurrences(model.doc, gids, "sala")
    assert {(g, k) for g, k, *_ in found} == {(t.GlobalId, "text"), (dim.GlobalId, "texts.0")}
    tx = model.commit(find.replace_text(model.doc, gids, "sala", "Estar", whole=True))
    assert len(tx.ops) == 2  # uma transação
    assert base.read_state(t)["text"] == "Estar de estar\nEstar"
    assert base.read_state(dim)["texts"] == {"0": "<medida> Estar"}
    model.history.undo()
    model.commit(find.replace_text(model.doc, gids, "SALA", "X", case=True))
    assert base.read_state(t)["text"] == "X de estar\nsala"
    with pytest.raises(OpError):
        find.replace_text(model.doc, gids, "inexistente", "Y")


def test_ls05_substituir_camada_situacao_tipo_propriedade(model):
    t20 = _type(model, "Alvenaria 20", 0.20)
    a = model.wall((0, 0), (5, 0))
    b = model.wall((0, 4), (5, 4))
    text = created(model, ac.create_annotation(model.doc, "text", model.terreo, at=[1, 1],
                                               text="X"))
    tx = model.commit(find.set_fields(model.doc, [a, b, text], type=t20.GlobalId,
                                      situation="A_DEMOLIR"))
    assert tx.skipped == 1  # o texto não tem tipo
    assert ue.get_type(a) == t20 and ue.get_type(b) == t20
    assert intervention.situation_of(model.doc, text) == "A_DEMOLIR"
    model.commit(find.set_fields(model.doc, [a], code="P-01", name="Parede norte"))
    assert ue.get_pset(a, "Pset_WallCommon")["Reference"] == "P-01" and a.Name == "Parede norte"
    model.commit(find.set_fields(model.doc, [a, b], property=("Obra_Dados", "Lote", "L3")))
    assert ue.get_pset(b, "Obra_Dados")["Lote"] == "L3"
    row = {"field": "property", "pset": "Obra_Dados", "prop": "Lote", "op": "is", "value": "l3"}
    assert find.find(model.doc, _crit(row), model.terreo) == sorted([a.GlobalId, b.GlobalId])
    check_history(model, lambda: model.commit(find.set_fields(
        model.doc, [a], property=("Obra_Dados", "Lote", "L4"))))
    with pytest.raises(OpError):
        model.commit(find.set_fields(model.doc, [a], property=("BrasBim_Anotacao", "x", 1)))
    valid(model.doc.ifc)
