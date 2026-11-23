# SPDX-License-Identifier: LGPL-3.0-or-later
"""Estilo das anotações (spec/ui 55 §2.1): fonte, altura, negrito, itálico e cor do texto;
cor e espessura das linhas. Sem Qt.

O estilo fica no estado da anotação, chave ``style``, só com os campos escolhidos::

    {"font": "Arial", "size": 3.0, "bold": True, "italic": False,
     "text_color": "#C0392B", "line_color": "#1F5FC4", "weight": 0.25}

Sem a chave (ou campo ``None``), vale o desenho de antes: a fonte da interface, a altura
do tipo e a pena da categoria (spec/ui 27). Cor e espessura escolhidas passam por cima da
pena.
"""

from __future__ import annotations

import dataclasses
import re

from brasbim.core.annotations.prims import Fill, Prims
from brasbim.core.document import OpError

KEY = "style"
TEXT_FIELDS = ("font", "size", "bold", "italic", "text_pen", "text_color")
LINE_FIELDS = ("pen", "line_color", "weight")
# Pena da tabela (spec/ui 57): ``pen`` nas linhas e ``text_pen`` no texto. A cor e a
# espessura soltas (``*_color``, ``weight``) ficam só para arquivos de antes; escolher a
# pena as tira.
PEN_FIELDS = ("pen", "text_pen")
REPLACES = {"pen": ("line_color", "weight"), "text_pen": ("text_color",)}
FIELDS = TEXT_FIELDS + LINE_FIELDS
SIZES = (1.5, 2.0, 2.5, 3.0, 3.5, 5.0, 7.0)  # mm de papel (lista; aceita digitado)
SIZE_RANGE = (0.5, 50.0)
WEIGHT_RANGE = (0.05, 2.0)
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


# Anotações sem texto nem traço próprio para estilizar.
UNSTYLED = {"hatch", "reference2d"}


def styled(element) -> bool:
    from brasbim.core.annotations import base

    kind = base.kind_of(element)
    return kind is not None and kind.prefix not in UNSTYLED


def edit_style(doc, elements, **fields):
    """Transação "Estilo da anotação": os ``fields`` (``None`` volta ao padrão) em todas
    as ``elements``, cada uma com o resto do seu estilo."""
    from brasbim.core.annotations import base
    from brasbim.core.annotations import commands as ac
    from brasbim.core.ops import Transaction

    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise OpError(f"campo de estilo desconhecido: {sorted(unknown)}")
    validate(fields)
    fields = dict(fields)
    for pen_field, old in REPLACES.items():  # a pena escolhida tira a cor solta
        if fields.get(pen_field) is not None:
            fields.update(dict.fromkeys(old))
    ops = []
    for element in elements:
        if not styled(element):
            continue
        current = dict(base.read_state(element).get(KEY) or {})
        new = clean({**current, **fields})
        if new != clean(current):
            ops += ac.edit_element(doc, element, style=new or None).ops
    noun = "Estilo da anotação" if len(elements) == 1 else "Estilo das anotações"
    return Transaction(noun, ops)


def common(elements, field: str):
    """Valor do campo de estilo em comum (``None``: diferem ou nenhum tem)."""
    from brasbim.core.annotations import base

    values = {(base.read_state(e).get(KEY) or {}).get(field) for e in elements}
    return values.pop() if len(values) == 1 else None


def clean(style: dict | None) -> dict:
    """Só os campos com valor (os ``None`` saem)."""
    return {k: v for k, v in (style or {}).items() if k in FIELDS and v is not None}


def validate(style: dict | None) -> None:
    if style is None:
        return
    if not isinstance(style, dict):
        raise OpError("estilo de anotação inválido")
    for key, value in style.items():
        if key not in FIELDS:
            raise OpError(f"campo de estilo desconhecido: {key!r}")
        if value is None:
            continue
        if key == "font" and (not isinstance(value, str) or not value.strip()):
            raise OpError("nome de fonte vazio")
        if key == "size" and not SIZE_RANGE[0] <= float(value) <= SIZE_RANGE[1]:
            raise OpError(f"altura do texto de {SIZE_RANGE[0]:g} a {SIZE_RANGE[1]:g} mm")
        if key == "weight" and not WEIGHT_RANGE[0] <= float(value) <= WEIGHT_RANGE[1]:
            raise OpError(f"espessura de {WEIGHT_RANGE[0]:g} a {WEIGHT_RANGE[1]:g} mm")
        if key in ("text_color", "line_color") and not (
                isinstance(value, str) and _COLOR.match(value)):
            raise OpError(f"cor inválida: {value!r} (use #RRGGBB)")
        if key in ("bold", "italic") and not isinstance(value, bool):
            raise OpError(f"{key} é sim ou não")
        if key in PEN_FIELDS:
            from brasbim.core.pens import MAX_PENS

            if not isinstance(value, int) or isinstance(value, bool) \
                    or not 1 <= value <= MAX_PENS:
                raise OpError(f"número de pena de 1 a {MAX_PENS}")


def apply(built: Prims, style: dict | None, k: float) -> Prims:
    """Primitivas com o estilo; ``k``: metros de modelo por mm de papel."""
    style = clean(style)
    if not style:
        return built
    out = Prims(bulk=built.bulk)
    text = {}
    if "font" in style:
        text["font"] = style["font"]
    if "bold" in style:
        text["bold"] = bool(style["bold"])
    if "italic" in style:
        text["italic"] = bool(style["italic"])
    if "text_color" in style:
        text["color"] = style["text_color"]
    if "text_pen" in style:  # spec/ui 57
        text["pen_no"] = int(style["text_pen"])
    for t in built.texts:
        changes = dict(text)
        if "size" in style:
            changes["height"] = float(style["size"]) * k
        out.texts.append(dataclasses.replace(t, **changes))
    line = {}
    if "line_color" in style:
        line["color"] = style["line_color"]
    if "weight" in style:
        line["weight"], line["pen"] = float(style["weight"]), False
    if "pen" in style:  # spec/ui 57
        line["pen_no"] = int(style["pen"])
    out.strokes = [dataclasses.replace(s, **line) for s in built.strokes]
    for f in built.fills:
        fill = f.fill
        if "line_color" in style and fill.get("marker"):  # setas e pontos da cota
            fill = {**fill, "background": style["line_color"]}
        if "pen" in style and fill.get("marker"):
            fill = {**fill, "pen_no": int(style["pen"])}
        out.fills.append(Fill(f.rings, fill))
    return out
