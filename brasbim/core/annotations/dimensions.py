# SPDX-License-Identifier: LGPL-3.0-or-later
"""Cotas lineares associativas (``IfcAnnotation`` ``DIMENSION``), spec/ui 13 §4.

Estado::

    {"storey": "<GlobalId>", "points": [{"at": [0, 0], "ref": {...} | None}, ...],
     "direction": "aligned" | "fixed", "angle": 0.0, "offset": -0.6}

``direction`` ``aligned``: paralela aos dois primeiros pontos; ``fixed``: no ``angle``
(0 = horizontal, 90 = vertical). ``offset``: afastamento da linha de cota em relação ao
primeiro ponto, perpendicular à direção (positivo para a esquerda dela).

Ponto preso (``ref``, §4.3): ``wall`` (``end`` start/end × ``face`` left/right/axis),
``opening`` (``edge`` × ``face``), ``column`` (``u``, ``v``: fração de b/2 e h/2 a partir
do centro da seção), ``beam`` (``end`` × ``face``) e ``vertex`` (``index`` no contorno de
laje ou ambiente). ``at`` guarda a última posição resolvida (refeita pela derivação): se
o elemento some, o ponto fica livre ali (aviso).
"""

from __future__ import annotations

import itertools
import logging
import math

from brasbim.core import geom2d, storeys, units
from brasbim.core.annotations import base, prims
from brasbim.core.annotations.prims import Fill, Prims, Stroke, Text
from brasbim.core.document import Document, OpError

log = logging.getLogger(__name__)

DIRECTIONS = ("aligned", "fixed")
TICK, GAP, OVER, TEXT, TEXT_GAP = 3.0, 2.0, 2.0, 2.5, 1.0  # mm de papel (§4.2)
WEIGHT = 0.13  # mm (§8)
AUTO_OFFSET = 12.0  # mm de papel: cota automática da parede (§4.5)


def fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


# --- pontos presos --------------------------------------------------------------------


def _wall_point(doc: Document, gid: str, end: str, face: str):
    from brasbim.core.walls import rebuild
    from brasbim.core.walls.wall import read_state

    wall = doc.find(gid)
    if wall is None or not wall.is_a("IfcWall"):
        return None
    state = read_state(doc, wall)
    band = rebuild.band(doc, state)
    if not isinstance(band.path, geom2d.LinePath):
        return None
    length = band.path.length
    if face == "axis":
        return band.path.start if end == "start" else band.path.end
    y = band.ymax if face == "left" else band.ymin
    try:
        pts = geom2d.polygon(rebuild.profile(doc, wall, band))
    except ValueError:
        pts = []
    on = [p for p in pts if abs(p[1] - y) < 1e-6]
    if on:
        x = min(p[0] for p in on) if end == "start" else max(p[0] for p in on)
    else:
        x = 0.0 if end == "start" else length
    return band.frame.to_global((x, y))


def _opening_point(doc: Document, gid: str, edge: str, face: str):
    from brasbim.core.walls import openings, rebuild
    from brasbim.core.walls.wall import read_state

    opening = doc.find(gid)
    if opening is None or not opening.is_a("IfcOpeningElement"):
        return None
    wall = openings.host(opening)
    if wall is None or not wall.is_a("IfcWall"):
        return None
    o = openings.read_state(opening)
    band = rebuild.band(doc, read_state(doc, wall))
    x = o["distance"] if edge == "start" else o["distance"] + o["width"]
    y = {"left": band.ymax, "right": band.ymin}.get(face, (band.ymin + band.ymax) / 2)
    return band.frame.to_global((x, y))


def _column_point(doc: Document, gid: str, u: float, v: float):
    from brasbim.core.structure import columns, profiles

    column = doc.find(gid)
    if column is None or not column.is_a("IfcColumn"):
        return None
    state = columns.read_state(doc, column)
    if state["foreign"] is not None:
        return None
    w, h = profiles.size(columns.section(doc, state))
    c = columns.center(doc, state)
    a = math.radians(state["angle"])
    x, y = u * w / 2, v * h / 2
    return (c[0] + math.cos(a) * x - math.sin(a) * y, c[1] + math.sin(a) * x + math.cos(a) * y)


def _beam_point(doc: Document, gid: str, end: str, face: str):
    from brasbim.core.structure import beams

    beam = doc.find(gid)
    if beam is None or not beam.is_a("IfcBeam"):
        return None
    state = beams.read_state(doc, beam)
    if state["foreign"] is not None:
        return None
    if face == "axis":
        return tuple(state["start"] if end == "start" else state["end"])
    ring = beams.outline(doc, state)  # direita: 0 → 1; esquerda: 3 → 2
    return {("start", "right"): ring[0], ("end", "right"): ring[1],
            ("end", "left"): ring[2], ("start", "left"): ring[3]}[(end, face)]


def _vertex_point(doc: Document, gid: str, index: int):
    from brasbim.core.annotations import spaces
    from brasbim.core.structure import slabs

    element = doc.find(gid)
    if element is None:
        return None
    if element.is_a("IfcSlab"):
        state = slabs.read_state(doc, element)
        outline = state["outline"] if state["foreign"] is None else None
    elif element.is_a("IfcSpace"):
        outline = spaces.read_state(element)["outline"]
    else:
        return None
    if not outline or not 0 <= index < len(outline):
        return None
    return tuple(outline[index])


def resolve(doc: Document, ref: dict):
    """Posição do ponto preso, ou ``None`` se o elemento não existe mais."""
    try:
        kind = ref["kind"]
        if kind == "wall":
            return _wall_point(doc, ref["gid"], ref["end"], ref["face"])
        if kind == "opening":
            return _opening_point(doc, ref["gid"], ref["edge"], ref["face"])
        if kind == "column":
            return _column_point(doc, ref["gid"], ref["u"], ref["v"])
        if kind == "beam":
            return _beam_point(doc, ref["gid"], ref["end"], ref["face"])
        if kind == "vertex":
            return _vertex_point(doc, ref["gid"], ref["index"])
    except (OpError, KeyError, ValueError, TypeError):
        return None
    return None


def candidates(doc: Document, storey) -> list[tuple[dict, tuple[float, float]]]:
    """Pontos que uma cota pode prender no pavimento: (referência, posição)."""
    import ifcopenshell.util.element

    from brasbim.core.structure import roofs
    from brasbim.core.walls import openings

    out = []
    for e in ifcopenshell.util.element.get_decomposition(storey):
        refs = []
        if roofs.is_part(e):
            continue
        if e.is_a("IfcWall"):
            refs = [{"kind": "wall", "gid": e.GlobalId, "end": end, "face": face}
                    for end in ("start", "end") for face in ("left", "right", "axis")]
            for o in openings.of_wall(e):
                refs += [{"kind": "opening", "gid": o.GlobalId, "edge": edge, "face": face}
                         for edge in ("start", "end") for face in ("left", "right")]
        elif e.is_a("IfcColumn"):
            refs = [{"kind": "column", "gid": e.GlobalId, "u": u, "v": v}
                    for u in (-1.0, 0.0, 1.0) for v in (-1.0, 0.0, 1.0)]
        elif e.is_a("IfcBeam"):
            refs = [{"kind": "beam", "gid": e.GlobalId, "end": end, "face": face}
                    for end in ("start", "end") for face in ("left", "right", "axis")]
        elif e.is_a("IfcSlab") or e.is_a("IfcSpace"):
            refs = [{"kind": "vertex", "gid": e.GlobalId, "index": i} for i in range(64)]
        for ref in refs:
            p = resolve(doc, ref)
            if p is not None:
                out.append((ref, (float(p[0]), float(p[1]))))
    return out


def ref_at(doc: Document, storey, p, tol: float) -> dict | None:
    """Referência do ponto de elemento mais perto de ``p`` (até ``tol``)."""
    near = [(math.dist(p, q), i, ref) for i, (ref, q) in enumerate(candidates(doc, storey))
            if math.dist(p, q) <= tol]
    return min(near, key=lambda n: (n[0], n[1]))[2] if near else None


# --- geometria -------------------------------------------------------------------------


def points(doc: Document, state: dict) -> list[tuple[float, float]]:
    out = []
    for item in state["points"]:
        p = resolve(doc, item["ref"]) if item.get("ref") else None
        out.append(tuple(p) if p is not None else tuple(item["at"]))
    return out


def frame(state: dict, pts) -> tuple[tuple, tuple]:
    """(direção, normal à esquerda) da linha de cota."""
    if state["direction"] == "aligned":
        dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]
        n = math.hypot(dx, dy)
        d = (dx / n, dy / n) if n > 1e-12 else (1.0, 0.0)
    else:
        a = math.radians(state["angle"])
        d = (math.cos(a), math.sin(a))
    return d, (-d[1], d[0])


def measures(doc: Document, state: dict) -> list[float]:
    """Medidas da cota, na ordem ao longo da linha."""
    pts = points(doc, state)
    d, _ = frame(state, pts)
    ts = sorted({round((p[0] - pts[0][0]) * d[0] + (p[1] - pts[0][1]) * d[1], 9)
                 for p in pts})
    return [b - a for a, b in itertools.pairwise(ts) if b - a > 1e-6]


def _build(doc: Document, storey, state: dict) -> Prims:
    k = storeys.paper(storey, 1.0)  # m por mm de papel
    pts = points(doc, state)
    d, n = frame(state, pts)
    p0 = pts[0]

    def at(t, s):
        return (p0[0] + d[0] * t + n[0] * s, p0[1] + d[1] * t + n[1] * s)

    ts = [(p[0] - p0[0]) * d[0] + (p[1] - p0[1]) * d[1] for p in pts]
    ss = [(p[0] - p0[0]) * n[0] + (p[1] - p0[1]) * n[1] for p in pts]
    off = state["offset"]
    out = Prims()
    out.strokes.append(Stroke((at(min(ts), off), at(max(ts), off)), False, WEIGHT))
    for t, s in zip(ts, ss, strict=True):
        if abs(off - s) > GAP * k:
            sign = 1.0 if off > s else -1.0
            out.strokes.append(Stroke((at(t, s + sign * GAP * k), at(t, off + sign * OVER * k)),
                                      False, WEIGHT))
    marks = sorted({round(t, 9) for t in ts})
    _markers(out, state, marks, at, off, d, n, k)
    shown = prims.readable(math.degrees(math.atan2(d[1], d[0])))
    for index, value, place, home in text_spots(doc, state, k):
        text, fixed = segment_text(doc, state, index, value)
        if not text:
            continue
        out.texts.append(Text(place, text, TEXT * k, shown, "center", "bottom", fixed=fixed))
        if math.dist(place, home) > TEXT * k:  # texto levado para longe: linha de chamada
            out.strokes.append(Stroke((home, place), False, WEIGHT))
    return out


def text_spots(doc: Document, state: dict, k: float):
    """(trecho, medida, lugar do texto, lugar de origem) de cada trecho da cota. O texto
    pode ter sido levado (``text_moves``: ``{trecho: [ao longo, para fora]}``, em metros
    no sistema da linha de cota; spec/ui 57 §4)."""
    pts = points(doc, state)
    d, n = frame(state, pts)
    p0 = pts[0]
    ts = sorted({round((p[0] - p0[0]) * d[0] + (p[1] - p0[1]) * d[1], 9) for p in pts})
    angle = math.degrees(math.atan2(d[1], d[0]))
    shown = prims.readable(angle)
    up = n if abs(((shown - angle) + 180.0) % 360.0 - 180.0) < 1.0 else (-n[0], -n[1])
    moves = state.get("text_moves") or {}
    off = state["offset"]
    out = []
    index = 0
    for a, b in itertools.pairwise(ts):
        if b - a <= 1e-6:
            continue
        t, s = (a + b) / 2, off
        home = (p0[0] + d[0] * t + n[0] * s + up[0] * TEXT_GAP * k,
                p0[1] + d[1] * t + n[1] * s + up[1] * TEXT_GAP * k)
        dt, ds = moves.get(str(index), (0.0, 0.0))
        place = (home[0] + d[0] * dt + n[0] * ds, home[1] + d[1] * dt + n[1] * ds)
        out.append((index, b - a, place, home))
        index += 1
    return out


def text_move(doc: Document, state: dict, index: int, p) -> list[float]:
    """Deslocamento ``[ao longo, para fora]`` que leva o texto do trecho ao ponto ``p``."""
    storey = doc.get(state["storey"])
    k = storeys.paper(storey, 1.0)
    pts = points(doc, state)
    d, n = frame(state, pts)
    home = next(h for i, _, _, h in text_spots(doc, state, k) if i == index)
    v = (p[0] - home[0], p[1] - home[1])
    return [v[0] * d[0] + v[1] * d[1], v[0] * n[0] + v[1] * n[1]]


# --- marcadores e texto (spec/ui 55 §2.1–§2.2) -------------------------------------------

MARKERS = ("tick", "arrow", "open_arrow", "dot", "none")
MEASURE = "<medida>"


def _markers(out: Prims, state: dict, marks, at, off, d, n, k) -> None:
    marker = state.get("marker") or "tick"
    size = float(state.get("marker_size") or TICK) * k
    if marker == "none":
        return
    if marker == "tick":
        tick = ((d[0] + n[0]) / math.sqrt(2) * size / 2, (d[1] + n[1]) / math.sqrt(2) * size / 2)
        for t in marks:
            c = at(t, off)
            out.strokes.append(Stroke(((c[0] - tick[0], c[1] - tick[1]),
                                       (c[0] + tick[0], c[1] + tick[1])), False, WEIGHT))
        return
    solid = {"pattern": "solid", "background": prims.INK, "angle": 0.0, "spacing": 1.0,
             "line_color": None, "source": "material", "marker": True}
    if marker == "dot":
        r = size / 4
        for t in marks:
            c = at(t, off)
            ring = tuple((c[0] + r * math.cos(i * math.pi / 6), c[1] + r * math.sin(i * math.pi / 6))
                         for i in range(12))
            out.fills.append(Fill((ring,), solid))
        return
    # Setas: em cada trecho, uma em cada ponta, apontando para a marca.
    half = size * math.tan(math.radians(15.0))
    for a, b in itertools.pairwise(marks):
        if b - a <= 1e-6:
            continue
        for tip_t, sign in ((a, 1.0), (b, -1.0)):
            tip = at(tip_t, off)
            back = at(tip_t + sign * size, off)
            wing1 = (back[0] + n[0] * half, back[1] + n[1] * half)
            wing2 = (back[0] - n[0] * half, back[1] - n[1] * half)
            if marker == "arrow":
                out.fills.append(Fill(((tip, wing1, wing2),), solid))
            else:
                out.strokes.append(Stroke((wing1, tip, wing2), False, WEIGHT))


def segment_text(doc: Document, state: dict, index: int, value: float) -> tuple[str, bool]:
    """Texto do trecho ``index`` da cota: o modelo trocado (``texts``) ou prefixo +
    medida + sufixo. Devolve também se o texto ficou fixo (sem ``<medida>``)."""
    measure = units.length(doc, "linear", value, decimals=state.get("decimals"))
    template = (state.get("texts") or {}).get(str(index))
    if template is None:
        template = f"{state.get('prefix') or ''}{MEASURE}{state.get('suffix') or ''}"
    return template.replace(MEASURE, measure), MEASURE not in template


def _validate(state: dict) -> None:
    if len(state["points"]) < 2:
        raise OpError("a cota precisa de pelo menos 2 pontos")
    if state["direction"] not in DIRECTIONS:
        raise OpError(f"direção de cota inválida: {state['direction']!r}")
    if state.get("marker") not in (None, *MARKERS):
        raise OpError(f"marcador de cota inválido: {state['marker']!r}")
    if state.get("marker_size") is not None and not 1.0 <= float(state["marker_size"]) <= 10.0:
        raise OpError("tamanho do marcador de 1 a 10 mm")
    decimals = state.get("decimals")
    if decimals is not None and (not isinstance(decimals, int)
                                 or not 0 <= decimals <= units.MAX_DECIMALS):
        raise OpError(f"casas decimais de 0 a {units.MAX_DECIMALS}")
    for key, value in (state.get("texts") or {}).items():
        if not str(key).isdigit() or not isinstance(value, str):
            raise OpError("texto de trecho da cota inválido")
    for key, value in (state.get("text_moves") or {}).items():
        if not str(key).isdigit() or not isinstance(value, (list, tuple)) or len(value) != 2:
            raise OpError("deslocamento do texto da cota inválido")


def _mapped(state, fn, turn, mirrored, moving) -> dict:
    """Pontos presos a elementos que se movem junto continuam presos; os outros ficam
    livres na posição levada."""
    out = []
    for item in state["points"]:
        q = fn(tuple(item["at"]))
        ref = item.get("ref")
        keep = ref if ref and ref.get("gid") in moving else None
        out.append({"at": [float(q[0]), float(q[1])], "ref": keep})
    changes = {"points": out, "angle": turn(state["angle"]) % 360.0}
    if mirrored:
        changes["offset"] = -state["offset"]
        if state.get("text_moves"):  # o texto levado fica do mesmo lado da linha
            changes["text_moves"] = {i: [dt, -ds] for i, (dt, ds) in
                                     state["text_moves"].items()}
    return changes


def _depends(state: dict) -> set[str]:
    return {item["ref"]["gid"] for item in state["points"] if item.get("ref")}


DIMENSION = base.Kind("dimension", "cota", "DIMENSION", None,
                      {"points": [], "direction": "aligned", "angle": 0.0, "offset": 0.0},
                      _build, _mapped, _depends, _validate,
                      optional=("marker", "marker_size", "texts", "prefix", "suffix",
                                "decimals", "text_moves"))
base.register_kind(DIMENSION)


def refresh(doc: Document, element) -> None:
    """Guarda a posição atual dos pontos presos (``at``) e avisa quando um elemento
    sumiu (spec/ui 13 §4.3)."""
    state = base.read_state(element)
    changed = False
    for item in state["points"]:
        ref = item.get("ref")
        if not ref:
            continue
        p = resolve(doc, ref)
        if p is None:
            if not item.get("lost"):
                log.warning("cota %s: o ponto preso perdeu o elemento e ficou livre",
                            element.GlobalId)
                item["lost"] = True
                changed = True
            continue
        p = [float(p[0]), float(p[1])]
        if item.get("lost") or any(abs(a - b) > 1e-9 for a, b in zip(p, item["at"],
                                                                       strict=True)):
            item["at"], changed = p, True
            item.pop("lost", None)
    if changed:
        base.set_cache(doc, element, state)
