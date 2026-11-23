# SPDX-License-Identifier: LGPL-3.0-or-later
"""Penas de cada elemento (spec/ui 57), sem Qt.

Um elemento pode escolher, por cima da pena da categoria (spec/ui 27), o **número da pena**
da tabela para:

- ``cut``  — contorno do que o plano de corte atravessa (Contorno);
- ``fill`` — hachura/preenchimento do corte (Hachura);
- ``view`` — linhas em vista e acima do plano (Vista).

Porta, janela e objeto só têm ``cut`` (as linhas do símbolo). Sem escolha vale a tabela.
Fica no Pset ``BrasBim_PenasElemento`` (``Contorno``, ``Hachura``, ``Vista``, inteiros).
Operação ``element_pens.set`` (before/after: ``{"pens": {...}}``).
"""

from __future__ import annotations

import ifcopenshell.util.element as ue

from brasbim.core import display_layers, props
from brasbim.core.document import Document, OpError
from brasbim.core.ops.base import Op, check_before, invert_swap, register

PSET = "BrasBim_PenasElemento"
FIELDS = ("cut", "fill", "view")
PROPS = {"cut": "Contorno", "fill": "Hachura", "view": "Vista"}
LABELS = {"cut": "Contorno", "fill": "Hachura", "view": "Vista"}
TIPS = {"cut": "Pena do contorno do corte (linhas cortadas)",
        "fill": "Pena da hachura do corte",
        "view": "Pena das linhas em vista e acima do plano de corte"}
# Grupo (``pick_settings.group_of``) → penas que ele tem.
GROUP_FIELDS = {"wall": FIELDS, "column": FIELDS, "beam": FIELDS, "slab": FIELDS,
                "roof": FIELDS, "door": ("cut",), "window": ("cut",), "object": ("cut",)}
# Ferramenta de criação (``display_layers.created``) → grupo.
KIND_GROUPS = {"wall": "wall", "column": "column", "beam": "beam", "slab": "slab",
               "roof": "roof", "door": "door", "window": "window"}


def fields_of(doc: Document, element) -> tuple:
    from brasbim.core import pick_settings

    return GROUP_FIELDS.get(pick_settings.group_of(doc, element), ())


def read(element) -> dict:
    """``{"cut": 5, ...}`` só com as penas escolhidas."""
    values = ue.get_pset(element, PSET, should_inherit=False) or {}
    return {k: int(values[p]) for k, p in PROPS.items() if values.get(p) is not None}


def validate(pens: dict) -> None:
    from brasbim.core.pens import MAX_PENS

    for key, value in pens.items():
        if key not in FIELDS:
            raise OpError(f"pena desconhecida: {key!r}")
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_PENS:
            raise OpError(f"número de pena de 1 a {MAX_PENS}")


def _apply(doc: Document, op: Op) -> set[str]:
    element = doc.get(op.id)
    check_before(op, {"pens": read(element)})
    new = dict((op.after or {}).get("pens") or {})
    validate(new)
    if new:
        props.write_pset(doc, element, PSET, {
            PROPS[k]: doc.ifc.createIfcInteger(int(v)) for k, v in sorted(new.items())})
    else:
        props.remove_pset(doc, element, PSET)
    doc.changed.add(element.GlobalId)
    return {op.id}


register("element_pens.set", _apply, invert_swap)


def _op(gid: str, before: dict, after: dict) -> Op:
    return Op("element_pens.set", gid, before={"pens": dict(before)}, after={"pens": dict(after)})


def set_pens(doc: Document, elements, **fields):
    """Transação "Penas": os ``fields`` (``None`` volta à tabela) em cada elemento, só nas
    penas que ele tem."""
    from brasbim.core.ops import Transaction

    validate({k: v for k, v in fields.items() if v is not None})
    ops = []
    for element in elements:
        element = display_layers.owner(element)
        allowed = fields_of(doc, element)
        current = read(element)
        new = dict(current)
        for key, value in fields.items():
            if key not in allowed:
                continue
            if value is None:
                new.pop(key, None)
            else:
                new[key] = int(value)
        if new != current:
            ops.append(_op(element.GlobalId, current, new))
    return Transaction("Penas do elemento" if len(ops) <= 1 else "Penas dos elementos", ops)


def inherit(doc: Document, tx, sources):
    """As cópias (copiar, espelhar com cópia, dividir) levam as penas do original."""
    from brasbim.core.ops import Transaction

    ops = [_op(gid, {}, pens) for _, gid, pens in display_layers.copies(
        doc, tx, sources, read) if pens]
    return Transaction(tx.label, tx.ops + ops) if ops else tx


def stamp_created(doc: Document, tx, new_pens: dict):
    """Penas das próximas criações (barra Opções da ferramenta): ``new_pens`` é grupo →
    penas; acrescenta a ``tx`` as dos elementos criados."""
    from brasbim.core.ops import Transaction

    if not new_pens:
        return tx
    done = {op.id for op in tx.ops if op.op == "element_pens.set"}
    ops = []
    for kind, gid, origin in display_layers.created(tx, doc):
        group = KIND_GROUPS.get(kind) or ("object" if _is_object_op(tx, gid) else None)
        pens = {k: v for k, v in (new_pens.get(group) or {}).items()
                if k in GROUP_FIELDS.get(group, ())}
        if pens and origin is None and gid not in done:
            ops.append(_op(gid, {}, pens))
    return Transaction(tx.label, tx.ops + ops) if ops else tx


def _is_object_op(tx, gid: str) -> bool:
    return any(op.op == "object.create" and op.id == gid for op in tx.ops)


def plan_pens(doc: Document) -> dict[str, dict]:
    """Dono → penas escolhidas, para o desenho da planta."""
    out = {}
    for pset in doc.ifc.by_type("IfcPropertySet"):
        if pset.Name != PSET:
            continue
        for rel in pset.DefinesOccurrence or ():
            for element in rel.RelatedObjects or ():
                found = read(element)
                if found:
                    out[element.GlobalId] = found
    return out
