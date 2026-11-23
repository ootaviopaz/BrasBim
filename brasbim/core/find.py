# SPDX-License-Identifier: LGPL-3.0-or-later
"""Localizar e substituir (spec/ui 55 §3), sem Qt.

Critérios::

    {"classes": ["IfcWall", "annotation:dimension"],   # OU entre as classes ([] = todas)
     "rows": [{"field": "type", "op": "contains", "value": "Alvenaria"},
              {"field": "property", "pset": "Pset_WallCommon", "prop": "IsExternal",
               "op": "is", "value": "sim"}],              # E entre as linhas
     "scope": "storey" | "all", "include_hidden": False}

Critérios salvos: Pset ``BrasBim_Criterios`` do ``IfcProject`` (JSON ``{"saved": [{"name":
..., "criteria": {...}}]}``), operação ``criteria.edit``.
"""

from __future__ import annotations

import copy
import json
import re

import ifcopenshell.util.element as ue

from brasbim.core import display_layers, intervention, props
from brasbim.core.document import Document, OpError
from brasbim.core.ops.base import Op, check_before, invert_swap, register

PSET = "BrasBim_Criterios"

# (chave, rótulo, "text" | "number")
FIELDS = (
    ("type", "Tipo", "text"),
    ("name", "Nome", "text"),
    ("code", "Código", "text"),
    ("layer", "Camada", "text"),
    ("situation", "Situação", "text"),
    ("material", "Material", "text"),
    ("storey", "Pavimento", "text"),
    ("text", "Texto da anotação", "text"),
    ("property", "Propriedade", "text"),
    ("quantity", "Quantidade", "number"),
)
FIELD_KINDS = {k: kind for k, _, kind in FIELDS}
TEXT_OPS = (("is", "é"), ("is_not", "não é"), ("contains", "contém"),
            ("not_contains", "não contém"), ("starts", "começa com"))
NUMBER_OPS = (("eq", "="), ("ne", "≠"), ("lt", "<"), ("le", "≤"), ("gt", ">"), ("ge", "≥"),
              ("between", "entre"))
VALUE_OPS = (("has", "tem valor"), ("has_not", "não tem valor"))
OPS = {k for k, _ in (*TEXT_OPS, *NUMBER_OPS, *VALUE_OPS)}

# Classe mostrada → rótulo (anotações e objetos à parte da classe IFC).
CLASS_LABELS = {
    "IfcWall": "Parede", "IfcDoor": "Porta", "IfcWindow": "Janela", "IfcSlab": "Laje",
    "IfcColumn": "Pilar", "IfcBeam": "Viga", "IfcRoof": "Cobertura", "object": "Objeto",
    "IfcSpace": "Ambiente", "IfcStair": "Escada", "IfcRailing": "Guarda-corpo",
    "IfcCovering": "Forro e piso", "IfcGeographicElement": "Terreno",
    "annotation:dimension": "Cota", "annotation:radius_dim": "Cota de raio",
    "annotation:angle_dim": "Cota de ângulo", "annotation:level_mark": "Cota de nível",
    "annotation:text": "Texto", "annotation:label": "Rótulo",
    "annotation:line2d": "Linha", "annotation:circle2d": "Círculo",
    "annotation:arc2d": "Arco", "annotation:spline2d": "Curva",
    "annotation:hatch": "Hachura", "annotation:revision": "Marcador de alteração",
    "annotation:north": "Norte", "annotation:reference2d": "Desenho importado",
}


def default_criteria() -> dict:
    return {"classes": [], "rows": [], "scope": "storey", "include_hidden": False}


def class_key(element) -> str:
    from brasbim.core.annotations import base
    from brasbim.core.objects import elements as objects

    kind = base.kind_of(element)
    if kind is not None:
        return f"annotation:{kind.prefix}"
    if objects.is_object(element):
        return "object"
    return element.is_a()


def class_label(key: str) -> str:
    label = CLASS_LABELS.get(key)
    return f"{label} ({key})" if label and key.startswith("Ifc") else (label or key)


# --- valores -----------------------------------------------------------------------------


def _layer_names(doc: Document) -> dict:
    found = doc.__dict__.get("_find_layer_names")
    if found is None:
        found = {v: text for text, v in display_layers.choices(doc)}
        doc.__dict__["_find_layer_names"] = found
    return found


def _code(element) -> str | None:
    for name, values in (ue.get_psets(element) or {}).items():
        if name.startswith("Pset_") and name.endswith("Common") and values.get("Reference"):
            return str(values["Reference"])
    return getattr(element, "Tag", None) or None


def annotation_text(doc: Document, element) -> str | None:
    """Texto que a anotação mostra (o digitado; na cota, os números/trechos)."""
    from brasbim.core.annotations import base

    kind = base.kind_of(element)
    if kind is None:
        return None
    state = base.read_state(element)
    if kind.prefix in ("text", "label") and state.get("text"):
        return state["text"]
    if kind.prefix == "revision":
        return " ".join(x for x in (state.get("number"), state.get("note")) if x)
    texts = [t.text for t in base.build(doc, element).texts]
    return "\n".join(texts) if texts else None


def value(doc: Document, element, row: dict):
    """Valor do campo da linha para o elemento (``None``: não tem)."""
    field = row["field"]
    if field == "type":
        t = ue.get_type(element)
        return t.Name if t is not None else None
    if field == "name":
        if element.is_a("IfcSpace"):
            return element.LongName or element.Name
        return element.Name
    if field == "code":
        return _code(element)
    if field == "layer":
        layer = display_layers.layer_of(doc, element)
        return _layer_names(doc).get(layer) if layer else None
    if field == "situation":
        if not intervention.situable(display_layers.owner(element)):
            return None
        code = intervention.situation_of(doc, element)
        return next((label for c, label, _ in intervention.SITUATIONS if c == code), code)
    if field == "material":
        found = ue.get_materials(element)
        return found[0].Name if found else None
    if field == "storey":
        container = ue.get_container(element)
        return container.Name if container is not None else None
    if field == "text":
        return annotation_text(doc, element)
    if field == "property":
        values = ue.get_pset(element, row.get("pset") or "", should_inherit=True) or {}
        return values.get(row.get("prop") or "")
    if field == "quantity":
        for values in (ue.get_psets(element, qtos_only=True) or {}).values():
            if row.get("prop") in values:
                return values[row["prop"]]
        return None
    raise OpError(f"campo desconhecido: {field!r}")


def _number(x):
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip().replace(",", "."))
    except ValueError:
        return None


def _text(x) -> str:
    if isinstance(x, bool):
        return "sim" if x else "não"
    if isinstance(x, float):
        return f"{x:g}".replace(".", ",")
    return str(x)


def test(op: str, found, wanted) -> bool:
    """A condição ``op`` vale para o valor ``found`` e o ``wanted`` da linha."""
    if op == "has":
        return found not in (None, "")
    if op == "has_not":
        return found in (None, "")
    if found is None:
        return op in ("is_not", "not_contains", "ne")
    if op in ("eq", "ne", "lt", "le", "gt", "ge", "between"):
        a = _number(found)
        if op == "between":
            lo, hi = (_number(v) for v in (wanted if isinstance(wanted, (list, tuple))
                                            else str(wanted).split(";")))
            return a is not None and lo is not None and hi is not None and lo <= a <= hi
        b = _number(wanted)
        if a is None or b is None:
            return op == "ne"
        return {"eq": abs(a - b) < 1e-9, "ne": abs(a - b) >= 1e-9, "lt": a < b,
                "le": a <= b + 1e-9, "gt": a > b, "ge": a >= b - 1e-9}[op]
    have, want = _text(found).casefold(), _text(wanted).casefold().strip()
    if op == "is":
        return have == want
    if op == "is_not":
        return have != want
    if op == "contains":
        return want in have
    if op == "not_contains":
        return want not in have
    if op == "starts":
        return have.startswith(want)
    raise OpError(f"condição desconhecida: {op!r}")


def validate(criteria: dict) -> None:
    for row in criteria.get("rows", []):
        if row.get("field") not in FIELD_KINDS:
            raise OpError(f"campo desconhecido: {row.get('field')!r}")
        if row.get("op") not in OPS:
            raise OpError(f"condição desconhecida: {row.get('op')!r}")
        if row["field"] in ("property", "quantity") and not row.get("prop"):
            raise OpError("diga qual propriedade")
    if criteria.get("scope", "storey") not in ("storey", "all"):
        raise OpError("onde procurar: pavimento ou todos")


def candidates(doc: Document, storeys_) -> list:
    out = []
    for storey in storeys_:
        for e in ue.get_decomposition(storey):
            if e.is_a("IfcOpeningElement") or not (
                    e.is_a("IfcElement") or e.is_a("IfcAnnotation") or e.is_a("IfcSpace")):
                continue
            if display_layers.owner(e) is not e:  # peças (águas da cobertura…)
                continue
            out.append(e)
    return out


def find(doc: Document, criteria: dict, storey=None) -> list[str]:
    """GlobalIds dos elementos que atendem aos critérios."""
    validate(criteria)
    doc.__dict__.pop("_find_layer_names", None)
    if criteria.get("scope") == "all" or storey is None:
        storeys_ = doc.ifc.by_type("IfcBuildingStorey")
    else:
        storeys_ = [storey]
    hidden = set() if criteria.get("include_hidden") else (
        display_layers.hidden_ids(doc) | display_layers.locked_ids(doc))
    classes = set(criteria.get("classes") or ())
    out = []
    for e in candidates(doc, storeys_):
        if e.GlobalId in hidden:
            continue
        if classes and class_key(e) not in classes:
            continue
        if all(test(row["op"], value(doc, e, row), row.get("value"))
               for row in criteria.get("rows", [])):
            out.append(e.GlobalId)
    return sorted(out)


def summary(doc: Document, gids) -> str:
    n = len(gids)
    storeys_ = {getattr(ue.get_container(doc.get(g)), "GlobalId", None) for g in gids}
    noun = "elemento" if n == 1 else "elementos"
    if len(storeys_) > 1:
        return f"{n} {noun}, {len(storeys_)} pavimentos"
    return f"{n} {noun}"


def known_properties(doc: Document) -> list[tuple[str, str]]:
    """(Pset, propriedade) que existem no projeto, para a lista do campo Propriedade."""
    found = set()
    for pset in doc.ifc.by_type("IfcPropertySet"):
        if (pset.Name or "").startswith("BrasBim_"):
            continue
        for prop in pset.HasProperties or ():
            found.add((pset.Name, prop.Name))
    return sorted(found)


# --- critérios salvos --------------------------------------------------------------------


def _project(doc: Document):
    return doc.ifc.by_type("IfcProject")[0]


def saved(doc: Document) -> list[dict]:
    values = ue.get_pset(_project(doc), PSET, should_inherit=False) or {}
    try:
        return json.loads(values.get("Config") or "{}").get("saved", [])
    except ValueError:
        return []


def _apply_saved(doc: Document, op: Op) -> set[str]:
    project = doc.get(op.id)
    check_before(op, {"saved": saved(doc)})
    new = (op.after or {}).get("saved") or []
    if new:
        props.write_pset(doc, project, PSET, {"Config": doc.ifc.createIfcText(
            json.dumps({"saved": new}, ensure_ascii=False, sort_keys=True))})
    else:
        props.remove_pset(doc, project, PSET)
    return {op.id}


register("criteria.edit", _apply_saved, invert_swap)


def save_criteria(doc: Document, name: str, criteria: dict):
    """Transação "Salvar critérios" (troca o de mesmo nome)."""
    from brasbim.core.ops import Transaction

    name = (name or "").strip()
    if not name:
        raise OpError("dê um nome aos critérios")
    validate(criteria)
    current = saved(doc)
    new = [s for s in current if s["name"] != name] + [
        {"name": name, "criteria": copy.deepcopy(criteria)}]
    new.sort(key=lambda s: s["name"].casefold())
    return Transaction("Salvar critérios", [Op("criteria.edit", _project(doc).GlobalId,
                                               before={"saved": current},
                                               after={"saved": new})])


def delete_criteria(doc: Document, name: str):
    from brasbim.core.ops import Transaction

    current = saved(doc)
    new = [s for s in current if s["name"] != name]
    return Transaction("Excluir critérios", [Op("criteria.edit", _project(doc).GlobalId,
                                                before={"saved": current},
                                                after={"saved": new})] if new != current
                       else [])


# --- substituir (§3.2) ---------------------------------------------------------------------


def _pattern(find_text: str, case: bool, whole: bool):
    if not find_text:
        raise OpError("diga o que procurar")
    body = re.escape(find_text)
    if whole:
        body = rf"(?<!\w){body}(?!\w)"
    return re.compile(body, 0 if case else re.IGNORECASE)


def text_targets(doc: Document, element) -> dict:
    """Textos editáveis do elemento: campo → texto (§3.2)."""
    from brasbim.core.annotations import base

    kind = base.kind_of(element)
    if kind is not None:
        state = base.read_state(element)
        out = {}
        if kind.prefix == "text" or (kind.prefix == "label" and state.get("text")):
            out["text"] = state["text"]
        elif kind.prefix == "revision":
            out["note"] = state.get("note") or ""
        elif kind.prefix == "dimension":
            for i, t in (state.get("texts") or {}).items():
                out[f"texts.{i}"] = t
            for key in ("prefix", "suffix"):
                if state.get(key):
                    out[key] = state[key]
        return out
    return {}


def occurrences(doc: Document, gids, find_text: str, case=False, whole=False,
                where=("text",)) -> list[tuple[str, str, str, str]]:
    """Onde o texto aparece: (GlobalId, campo, antes, depois‑com‑marca)."""
    pattern = _pattern(find_text, case, whole)
    out = []
    for g in gids:
        e = doc.find(g)
        if e is None:
            continue
        fields = {}
        if "text" in where:
            fields.update(text_targets(doc, e))
        if "name" in where and value(doc, e, {"field": "name"}):
            fields["name"] = value(doc, e, {"field": "name"})
        if "code" in where and _code(e):
            fields["code"] = _code(e)
        for key, text in fields.items():
            if pattern.search(text or ""):
                out.append((g, key, text, pattern.sub(lambda m: f"[{m.group(0)}]", text)))
    return out


def replace_text(doc: Document, gids, find_text: str, new_text: str, case=False,
                 whole=False, where=("text",)):
    """Transação "Substituir texto": troca em todos os campos achados, de uma vez."""
    from brasbim.core.ops.history import combine

    pattern = _pattern(find_text, case, whole)
    builders = []
    by_element: dict[str, dict] = {}
    for g, key, before, _ in occurrences(doc, gids, find_text, case, whole, where):
        by_element.setdefault(g, {})[key] = pattern.sub(lambda m: new_text, before)
    for g, changes in by_element.items():
        builders.append(lambda g=g, c=changes: _text_tx(doc, doc.get(g), c))
    if not builders:
        raise OpError(f"“{find_text}” não aparece nos elementos")
    return combine(doc, f"Substituir “{find_text}”", builders)


def _text_tx(doc: Document, element, changes: dict):
    from brasbim.core.annotations import base
    from brasbim.core.annotations import commands as ac

    if base.kind_of(element) is not None:
        state = base.read_state(element)
        edit = {}
        texts = dict(state.get("texts") or {})
        for key, v in changes.items():
            if key.startswith("texts."):
                texts[key.split(".", 1)[1]] = v
                edit["texts"] = texts
            else:
                edit[key] = v
        return ac.edit_element(doc, element, **edit)
    edit = {}
    if "name" in changes:
        edit["name"] = changes["name"]
    if "code" in changes:
        edit["code"] = changes["code"]
    return set_fields(doc, [element], **edit)


def _class_edit(doc: Document, element, **changes):
    """Edição pela classe do elemento (nome, código, Pset_*Common)."""
    from brasbim.core import pick_settings
    from brasbim.core.annotations import commands as ac
    from brasbim.core.fillings import commands as fc
    from brasbim.core.objects import commands as oc
    from brasbim.core.structure import commands as sc
    from brasbim.core.walls import commands as cmd

    group = pick_settings.group_of(doc, element)
    if group == "wall":
        return cmd.edit_wall(doc, element, **changes)
    if group in ("column", "beam", "slab", "roof"):
        return sc.edit_element(doc, element, **changes)
    if group in ("door", "window"):
        return fc.edit_door(doc, element, **changes)
    if group == "object":
        return oc.edit_object(doc, element, **changes)
    if group == "space":
        return ac.edit_element(doc, element, **changes)
    raise OpError(f"{class_label(class_key(element))}: este campo não pode ser trocado aqui")


def _common_of(doc: Document, element) -> dict | None:
    from brasbim.core import pick_settings

    group = pick_settings.group_of(doc, element)
    if group == "wall":
        from brasbim.core.walls.wall import read_state

        return read_state(doc, element)["common"]
    if group in ("column", "beam", "slab", "roof"):
        from brasbim.core.structure import commands as sc

        return sc.read_state(doc, element)["common"]
    if group in ("door", "window"):
        from brasbim.core.fillings import doors

        return doors.read_state(element)["common"]
    return None


def set_fields(doc: Document, elements, **fields):
    """Transação "Substituir": ``name``, ``code``, ``layer``, ``situation``, ``type``,
    ``property`` (``(pset, prop, valor)``) e ``style`` (campos do estilo de anotação)."""
    from brasbim.core.annotations import style as annotation_style
    from brasbim.core.objects import commands as oc
    from brasbim.core.ops.history import combine

    elements = [display_layers.owner(e) for e in elements]
    builders = []
    skipped = 0
    for e in elements:
        if "layer" in fields and display_layers.layerable(e):
            builders.append(lambda e=e: display_layers.assign(doc, [e.GlobalId],
                                                              fields["layer"]))
        if "situation" in fields and intervention.situable(e):
            builders.append(lambda e=e: intervention.set_situation(doc, [e.GlobalId],
                                                                   fields["situation"]))
        if "style" in fields and annotation_style.styled(e):
            builders.append(lambda e=e: annotation_style.edit_style(doc, [e],
                                                                    **fields["style"]))
        if "type" in fields:
            new_type = doc.get(fields["type"])
            current = ue.get_type(e)
            if current is None or current.is_a() != new_type.is_a():
                skipped += 1
            elif current != new_type:
                gid = new_type.GlobalId
                if class_key(e) == "object":
                    builders.append(lambda e=e, g=gid: oc.edit_object(doc, e, type=g))
                else:
                    builders.append(lambda e=e, g=gid: _class_edit(doc, e, type=g))
        if "name" in fields:
            key = "name"
            builders.append(lambda e=e, k=key: _class_edit(doc, e, **{k: fields["name"]}))
        if "code" in fields:
            common = _common_of(doc, e)
            if common is None:
                skipped += 1
            else:
                builders.append(lambda e=e, c=common: _class_edit(
                    doc, e, common={**c, "Reference": fields["code"]}))
        if "property" in fields:
            pset, prop, new = fields["property"]
            builders.append(lambda e=e, p=pset, q=prop, v=new: _property_tx(doc, e, p, q, v))
    if not builders:
        raise OpError("nenhum elemento pode receber essa troca")
    tx = combine(doc, "Substituir", builders)
    tx.skipped = skipped
    return tx


# --- propriedade genérica (Psets que não são do BrasBim) ------------------------------------


def _ifc_value(doc: Document, v):
    if isinstance(v, bool):
        return doc.ifc.createIfcBoolean(v)
    if isinstance(v, (int, float)):
        return doc.ifc.createIfcReal(float(v))
    return doc.ifc.createIfcLabel(str(v))


def _property_tx(doc: Document, element, pset: str, prop: str, new):
    from brasbim.core.ops import Transaction

    if pset.startswith("BrasBim_"):
        raise OpError("as propriedades internas do BrasBim não se trocam aqui")
    common = _common_of(doc, element)
    if pset.startswith("Pset_") and pset.endswith("Common") and common is not None:
        return _class_edit(doc, element, common={**common, prop: new})
    old = (ue.get_pset(element, pset, should_inherit=False) or {}).get(prop)
    if old == new:
        return Transaction("Trocar propriedade", [])
    return Transaction("Trocar propriedade", [Op(
        "pset.set", element.GlobalId, before={"pset": pset, "prop": prop, "value": old},
        after={"pset": pset, "prop": prop, "value": new})])


def _apply_property(doc: Document, op: Op) -> set[str]:
    element = doc.get(op.id)
    after = op.after or {}
    pset, prop = after["pset"], after["prop"]
    current = (ue.get_pset(element, pset, should_inherit=False) or {}).get(prop)
    if op.before is not None and current != op.before.get("value"):
        raise OpError("pset.set: o valor atual não é o esperado")
    values = {k: v for k, v in (ue.get_pset(element, pset, should_inherit=False) or {}).items()
              if k != "id"}
    if after["value"] is None:
        values.pop(prop, None)
    else:
        values[prop] = after["value"]
    props.remove_pset(doc, element, pset)
    if values:
        props.write_pset(doc, element, pset, {k: _ifc_value(doc, v) for k, v in values.items()})
    doc.changed.add(element.GlobalId)
    return {op.id}


register("pset.set", _apply_property, invert_swap)
