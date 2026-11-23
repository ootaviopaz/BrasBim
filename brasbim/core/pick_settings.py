# SPDX-License-Identifier: LGPL-3.0-or-later
"""Pegar e aplicar ajustes (conta‑gotas, spec/ui 55 §4), sem Qt.

``pick`` lê de um elemento o que **não** é posição nem forma desenhada (tipo, alturas,
linha de referência, estilo…), mais a camada e a situação. ``apply`` leva esses ajustes a
outros elementos numa transação: os da mesma classe recebem tudo; os de outra classe, só a
camada e a situação (e o estilo, entre anotações).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import ifcopenshell.util.element

from brasbim.core import display_layers, intervention
from brasbim.core.document import Document, OpError

# Campos de cada classe que passam (§4.2).
WALL_KEYS = ("type", "ref_line", "flip_layers", "base_offset", "top_mode", "top_storey",
             "top_offset", "fixed_height", "common", "top_shape", "top_profile", "tilt")
COLUMN_KEYS = ("type", "cardinal", "angle", "base_offset", "top_mode", "top_storey",
               "top_offset", "fixed_height", "common")
BEAM_KEYS = ("type", "ref_line", "top_mode", "top_storey", "top_offset", "top_elevation",
             "common")
SLAB_KEYS = ("type", "top_offset", "common")
ROOF_KEYS = ("type", "slope", "overhang", "base_height", "common")
DOOR_KEYS = ("type", "opens_to", "align", "offset", "common")
OPENING_KEYS = {"width": "width", "height": "height", "sill": "base"}
SPACE_KEYS = ("name", "height", "area_class", "area_reason")
# Anotação → anotação do mesmo tipo: campos que não são posição nem o texto digitado.
ANNOTATION_KEYS = {
    "text": ("size", "align"),
    "line2d": ("weight", "dash"),
    "circle2d": ("weight", "dash"),
    "arc2d": ("weight", "dash"),
    "spline2d": ("weight", "dash"),
    "hatch": ("pattern", "color", "angle", "spacing"),
    "dimension": ("marker", "marker_size", "prefix", "suffix", "decimals"),
    "radius_dim": ("diameter",),
    "label": ("field",),
}
# Campos que dependem do pavimento (só passam no mesmo pavimento).
STOREY_BOUND = ("top_storey",)
NOUNS = {"wall": "Parede", "column": "Pilar", "beam": "Viga", "slab": "Laje",
         "roof": "Cobertura", "door": "Porta", "window": "Janela", "object": "Objeto",
         "space": "Ambiente"}


@dataclass
class Settings:
    group: str  # "wall", "door", "annotation:dimension"…
    label: str
    source: str  # GlobalId de onde veio
    storey: str | None
    values: dict = field(default_factory=dict)
    style: dict | None = None  # estilo da anotação (spec/ui 55 §2.1)
    layer: str | None = None
    situation: str | None = None
    object_type: str | None = None  # tipo do objeto de onde veio
    length_params: tuple = ()  # parâmetros de tamanho do objeto (não passam a outro tipo)


def _storey_of(element) -> str | None:
    container = ifcopenshell.util.element.get_container(element)
    return container.GlobalId if container is not None else None


def group_of(doc: Document, element) -> str | None:
    """Grupo do elemento (o que pode receber os ajustes de outro do mesmo grupo)."""
    from brasbim.core.annotations import base
    from brasbim.core.objects import elements as objects
    from brasbim.core.structure import commands as sc
    from brasbim.core.structure import skylights

    if element is None:
        return None
    if element.is_a("IfcWall"):
        return "wall"
    if (element.is_a("IfcDoor") or element.is_a("IfcWindow")) \
            and not skylights.is_skylight(element):
        return "door" if element.is_a("IfcDoor") else "window"
    if element.is_a("IfcSpace"):
        return "space"
    if base.kind_of(element) is not None:
        return f"annotation:{base.kind_of(element).prefix}"
    if objects.is_object(element):
        return "object"
    if sc.is_structure(element):
        return {"IfcColumn": "column", "IfcBeam": "beam", "IfcSlab": "slab",
                "IfcRoof": "roof"}.get(element.is_a())
    return None


def _pick_values(doc: Document, element, group: str) -> dict:
    from brasbim.core.annotations import base, spaces
    from brasbim.core.fillings import commands as fc
    from brasbim.core.fillings import doors
    from brasbim.core.structure import beams, columns, roofs, slabs
    from brasbim.core.walls import openings
    from brasbim.core.walls.wall import read_state as read_wall

    if group == "wall":
        state = read_wall(doc, element)
        values = {k: state[k] for k in WALL_KEYS if k in state}
        if values.get("top_mode") == "roof":  # preso à cobertura: é do próprio elemento
            for key in ("top_mode", "top_storey", "top_offset"):
                values.pop(key, None)
        return values
    module, keys = {"column": (columns, COLUMN_KEYS), "beam": (beams, BEAM_KEYS),
                    "slab": (slabs, SLAB_KEYS), "roof": (roofs, ROOF_KEYS)}.get(
        group, (None, None))
    if module is not None:
        state = module.read_state(doc, element)
        if state.get("foreign") is not None:
            raise OpError("elemento de outra origem: os ajustes dele não podem ser pegos")
        values = {k: state[k] for k in keys if k in state}
        if values.get("top_mode") == "roof":
            for key in ("top_mode", "top_storey", "top_offset"):
                values.pop(key, None)
        return values
    if group in ("door", "window"):
        state = doors.read_state(element)
        if state["foreign"] is not None:
            raise OpError("esquadria de outra origem: os ajustes dela não podem ser pegos")
        values = {k: state[k] for k in DOOR_KEYS}
        opening = fc.opening_of(element)
        if opening is not None:
            o = openings.read_state(opening)
            values.update({dest: o[src] for src, dest in OPENING_KEYS.items()})
        return values
    if group == "space":
        state = spaces.read_state(element)
        return {k: state[k] for k in SPACE_KEYS if k in state}
    if group == "object":
        from brasbim.core.objects import elements as objects

        state = objects.read_state(doc, element)
        return {"type": state["type"], "values": copy.deepcopy(state["values"])}
    if group.startswith("annotation:"):
        state = base.read_state(element)
        keys = ANNOTATION_KEYS.get(group.split(":", 1)[1], ())
        return {k: copy.deepcopy(state[k]) for k in keys if k in state}
    return {}


def pick(doc: Document, element) -> Settings:
    """Ajustes do elemento (Alt+clique, spec/ui 55 §4.1)."""
    from brasbim.core.annotations import base

    element = display_layers.owner(element)
    group = group_of(doc, element)
    if group is None:
        raise OpError("este elemento não tem ajustes para pegar")
    values = _pick_values(doc, element, group)
    style = None
    if group.startswith("annotation:"):
        style = copy.deepcopy(base.read_state(element).get("style"))
        noun = base.kind_of(element).noun.capitalize()
    else:
        noun = NOUNS.get(group, group)
    type_name = None
    if values.get("type"):
        found = doc.find(values["type"])
        type_name = found.Name if found is not None else None
    settings = Settings(group, f"{noun} · {type_name}" if type_name else noun,
                        element.GlobalId, _storey_of(element), values, style,
                        display_layers.layer_of(doc, element),
                        intervention.situation_of(doc, element)
                        if intervention.situable(element) else None)
    if group == "object":
        settings.object_type = values["type"]
        settings.length_params = _length_params(doc, values["type"])
    return settings


def _length_params(doc: Document, type_gid) -> tuple:
    from brasbim.core.objects import types as ot

    element_type = doc.find(type_gid) if type_gid else None
    if element_type is None:
        return ()
    definition = ot.read(element_type)["definition"]
    return tuple(p["name"] for p in definition.get("params", []) if p.get("kind") == "length")


# --- aplicar ---------------------------------------------------------------------------


def _class_changes(doc: Document, settings: Settings, target) -> dict:
    """O que muda na ``target`` da mesma classe (só os campos que diferem)."""
    values = copy.deepcopy(settings.values)
    if _storey_of(target) != settings.storey:
        for key in STOREY_BOUND:
            values.pop(key, None)
    if settings.group == "object":
        from brasbim.core.objects import elements as objects

        state = objects.read_state(doc, target)
        if state["type"] != settings.object_type:  # outro tipo: o tamanho fica (§4.2)
            keep = {k: v for k, v in state["values"].items() if k in settings.length_params}
            values["values"] = {**values["values"], **keep}
    return values


def _class_tx(doc: Document, settings: Settings, target):
    from brasbim.core.annotations import commands as ac
    from brasbim.core.fillings import commands as fc
    from brasbim.core.objects import commands as oc
    from brasbim.core.structure import commands as sc
    from brasbim.core.walls import commands as cmd

    changes = _class_changes(doc, settings, target)
    group = settings.group
    if group == "wall":
        return cmd.edit_wall(doc, target, **changes)
    if group in ("column", "beam", "slab", "roof"):
        return sc.edit_element(doc, target, **changes)
    if group in ("door", "window"):
        return fc.edit_door(doc, target, **changes)
    if group == "object":
        return oc.edit_object(doc, target, **changes)
    if group == "space" or group.startswith("annotation:"):
        return ac.edit_element(doc, target, **changes)
    return None


def apply(doc: Document, settings: Settings, targets) -> object:
    """Transação "Aplicar ajustes" nos ``targets`` (Ctrl+Alt+clique ou a mini‑barra)."""
    from brasbim.core.annotations import style as annotation_style
    from brasbim.core.ops.history import combine

    targets = [display_layers.owner(t) for t in targets]
    targets = [t for t in {t.GlobalId: t for t in targets}.values()
               if t.GlobalId != settings.source]
    if not targets:
        raise OpError("nada para receber os ajustes")
    builders = []
    for target in targets:
        group = group_of(doc, target)
        if group == settings.group and settings.values:
            builders.append(lambda t=target: _class_tx(doc, settings, t))
        if group and group.startswith("annotation:") \
                and settings.group.startswith("annotation:") \
                and annotation_style.styled(target):
            style = settings.style or {}
            reset = {k: style.get(k) for k in annotation_style.FIELDS}
            builders.append(lambda t=target, r=reset: annotation_style.edit_style(doc, [t], **r))
        if display_layers.layerable(target) and \
                display_layers.layer_of(doc, target) != settings.layer and \
                display_layers.read_config(doc) is not None:
            builders.append(lambda t=target: display_layers.assign(doc, [t.GlobalId],
                                                                   settings.layer))
        if settings.situation is not None and intervention.situable(target) and \
                intervention.situation_of(doc, target) != settings.situation:
            builders.append(lambda t=target: intervention.set_situation(
                doc, [t.GlobalId], settings.situation))
    label = "Aplicar ajustes" if len(targets) == 1 else f"Aplicar ajustes em {len(targets)}"
    if not builders:
        from brasbim.core.ops import Transaction

        return Transaction(label, [])
    return combine(doc, label, builders)


# --- ajustes da ferramenta (Alt+clique com ferramenta de criação, §4.1) ---------------------

# grupo → {atributo das opções da ferramenta: campo dos ajustes}
TOOL_FIELDS = {
    "wall": {"type": "type", "ref_line": "ref_line", "fixed_height": "fixed_height"},
    "column": {"type": "type", "top_offset": "top_offset"},
    "beam": {"type": "type", "ref_line": "ref_line", "top_offset": "top_offset"},
    "slab": {"type": "type", "top_offset": "top_offset"},
    "roof": {"type": "type", "slope": "slope", "overhang": "overhang",
             "base_height": "base_height"},
    "space": {"name": "name", "height": "height"},
    "door": {"type": "type"},
    "window": {"type": "type"},
    "annotation:text": {"size": "size", "align": "align"},
    "annotation:line2d": {"weight": "weight", "dash": "dash"},
    "annotation:circle2d": {"weight": "weight", "dash": "dash"},
    "annotation:arc2d": {"weight": "weight", "dash": "dash"},
    "annotation:spline2d": {"weight": "weight", "dash": "dash"},
    "annotation:hatch": {"pattern": "pattern", "color": "color", "angle": "angle",
                         "spacing": "spacing"},
}


def tool_changes(settings: Settings) -> dict:
    """Atributos das opções da ferramenta que os ajustes mudam."""
    out = {}
    for attr, key in TOOL_FIELDS.get(settings.group, {}).items():
        if key in settings.values:
            out[attr] = copy.deepcopy(settings.values[key])
    if settings.group == "wall":
        mode = settings.values.get("top_mode")
        if mode in ("storey", "fixed"):
            out["top"] = mode
    return out
