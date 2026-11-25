# SPDX-License-Identifier: LGPL-3.0-or-later
"""Cotas em níveis do pavimento (spec/ui 59), sem Qt.

Para cada lado da planta, linhas de cota paralelas, de dentro para fora: **aberturas**
(cantos da fachada e bordas dos vãos), **estrutura** (cantos, faces dos pilares e das
paredes internas que chegam à fachada) e **total** (ponta a ponta). Opcionalmente, as
cotas internas dos **cômodos** (largura e profundidade, face a face).

As cotas são as de sempre (``dimension``), associativas, com a marca ``auto`` no estado
(``{"side": "bottom", "level": "openings"}`` ou ``{"room": gid, "axis": "x"}``), para
refazer sem duplicar. Uma cota automática que o usuário mexeu (texto, estilo, posição do
número) fica, e aquela linha não é refeita.

Limites: só a parte ortogonal da planta (fachadas nos eixos x e y) e paredes retas.
"""

from __future__ import annotations

import math

import ifcopenshell.util.element
import shapely
from shapely.geometry import LineString, Polygon

from brasbim.core import geom2d, storeys
from brasbim.core.annotations import base, dimensions
from brasbim.core.document import Document, OpError

LEVELS = ("openings", "structure", "total")  # de dentro para fora
ROOMS = "rooms"
SIDES = ("bottom", "top", "left", "right")
# lado → (normal para fora, ângulo da linha de cota)
_SIDE = {"bottom": ((0.0, -1.0), 0.0), "top": ((0.0, 1.0), 0.0),
         "left": ((-1.0, 0.0), 90.0), "right": ((1.0, 0.0), 90.0)}
FIRST_MM, STEP_MM, ROOM_MM = 12.0, 7.0, 8.0  # mm de papel (§2, §3)
NEAR = 0.45  # m: pilar ou parede interna "na fachada" (até esta distância da face externa)
_EPS = 1e-4
# Campos que mostram que o usuário mexeu na cota automática (ela fica).
_EDITED = ("texts", "text_moves", "prefix", "suffix", "style", "marker", "decimals")


def _walls(doc: Document, storey) -> list:
    from brasbim.core.walls.wall import read_state as read_wall

    out = []
    for element in ifcopenshell.util.element.get_decomposition(storey):
        if element.is_a("IfcWall"):
            try:
                out.append((element, read_wall(doc, element)))
            except OpError:
                continue
    return out


def _columns(doc: Document, storey) -> list:
    from brasbim.core.structure import columns

    out = []
    for element in ifcopenshell.util.element.get_decomposition(storey):
        if element.is_a("IfcColumn"):
            try:
                state = columns.read_state(doc, element)
            except OpError:
                continue
            if state.get("foreign") is None:
                out.append((element, state))
    return out


def _wall_polygon(doc: Document, wall, state):
    from brasbim.core.walls import rebuild

    band = rebuild.band(doc, state)
    if not isinstance(band.path, geom2d.LinePath):
        return None, band
    try:
        local = geom2d.polygon(rebuild.profile(doc, wall, band))
    except (OpError, ValueError):
        return None, band
    ring = [band.frame.to_global(p) for p in local]
    polygon = Polygon(ring)
    return (polygon if polygon.is_valid else polygon.buffer(0)), band


def _outline(doc: Document, storey):
    """Contorno externo do pavimento (paredes retas e pilares juntos), ou None."""
    from brasbim.core.structure import columns

    parts = []
    for wall, state in _walls(doc, storey):
        polygon, _ = _wall_polygon(doc, wall, state)
        if polygon is not None and not polygon.is_empty:
            parts.append(polygon)
    if not parts:
        return None
    for _, state in _columns(doc, storey):
        parts.append(Polygon(columns.outline(doc, state)))
    union = shapely.union_all([p.buffer(1e-6) for p in parts]).buffer(-1e-6)
    if union.geom_type == "MultiPolygon":
        union = max(union.geoms, key=lambda g: g.area)
    if union.is_empty:
        return None
    return shapely.geometry.polygon.orient(Polygon(union.exterior), 1.0)


def _side_edges(outline, outward) -> list[tuple]:
    """Arestas do contorno cuja normal para fora é ``outward`` (fachada daquele lado)."""
    pts = list(outline.exterior.coords)[:-1]
    out = []
    for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        normal = (dy / length, -dx / length)  # anti-horário: a direita é fora
        if normal[0] * outward[0] + normal[1] * outward[1] <= 0.999:
            continue
        # só o que se vê de fora daquele lado: a lateral de um pilar saliente noutra
        # fachada também "olha" para cá, mas fica escondida atrás do resto
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        start = (mid[0] + outward[0] * 1e-4, mid[1] + outward[1] * 1e-4)
        ray = LineString([start, (mid[0] + outward[0] * 1e4, mid[1] + outward[1] * 1e4)])
        if not ray.intersects(outline):
            out.append((a, b))
    return out


def _along(p, angle: float) -> float:
    return p[0] if angle == 0.0 else p[1]


def _out(p, outward) -> float:
    return p[0] * outward[0] + p[1] * outward[1]


def _near_edges(p, edges, reach: float) -> bool:
    return any(_segment_distance(p, a, b) <= reach for a, b in edges)


def _segment_distance(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / max(dx * dx + dy * dy, 1e-12)
    t = min(max(t, 0.0), 1.0)
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _candidates(doc: Document, storey) -> list[tuple]:
    """(ponto, referência, papel) de onde as cotas podem se prender."""
    from brasbim.core.walls import openings

    out = []
    for wall, _ in _walls(doc, storey):
        for end in ("start", "end"):
            for face in ("left", "right", "axis"):
                ref = {"kind": "wall", "gid": wall.GlobalId, "end": end, "face": face}
                p = dimensions.resolve(doc, ref)
                if p is not None:
                    out.append((tuple(p), ref, "wall"))
        for opening in openings.of_wall(wall):
            for edge in ("start", "end"):
                for face in ("left", "right"):
                    ref = {"kind": "opening", "gid": opening.GlobalId, "edge": edge,
                           "face": face}
                    p = dimensions.resolve(doc, ref)
                    if p is not None:
                        out.append((tuple(p), ref, "opening"))
    for column, _ in _columns(doc, storey):
        for u in (-1.0, 1.0):
            for v in (-1.0, 1.0):
                ref = {"kind": "column", "gid": column.GlobalId, "u": u, "v": v}
                p = dimensions.resolve(doc, ref)
                if p is not None:
                    out.append((tuple(p), ref, "column"))
    return out


def _merge(values) -> list[float]:
    out = []
    for v in sorted(values):
        if not out or v - out[-1] > _EPS:
            out.append(v)
    return out


def _side_levels(doc: Document, storey, outline, side: str, cands) -> dict:
    """{nível: medidas ao longo do lado} e a face externa daquele lado."""
    outward, angle = _SIDE[side]
    edges = _side_edges(outline, outward)
    if not edges:
        return {}
    corners = _merge(_along(p, angle) for e in edges for p in e)
    ring = list(outline.exterior.coords)
    total = [min(_along(p, angle) for p in ring), max(_along(p, angle) for p in ring)]
    # aberturas: as das paredes cuja face está numa aresta deste lado
    opening_marks = []
    for p, ref, role in cands:
        if role == "opening" and _near_edges(p, edges, _EPS * 10):
            opening_marks.append(_along(p, angle))
    # estrutura: faces dos pilares e das paredes internas que chegam a este lado
    structure_marks = []
    for p, ref, role in cands:
        if role == "column" and _near_edges(p, edges, NEAR):
            structure_marks.append(_along(p, angle))
    for wall, state in _walls(doc, storey):
        path = geom2d.path_from_dict(state["path"])
        if not isinstance(path, geom2d.LinePath):
            continue
        d = (path.end[0] - path.start[0], path.end[1] - path.start[1])
        length = math.hypot(*d)
        if length < 1e-6 or abs(_out(d, outward)) / length < 0.99:
            continue  # só as paredes perpendiculares a esta fachada
        if not any(_near_edges(q, edges, NEAR) for q in (path.start, path.end)):
            continue
        if all(_near_edges(q, edges, _EPS * 10) for q in (path.start, path.end)):
            continue
        for p, ref, role in cands:
            if role == "wall" and ref["gid"] == wall.GlobalId and ref["face"] != "axis" \
                    and _near_edges(p, edges, NEAR):
                structure_marks.append(_along(p, angle))
    return {
        "openings": _merge(corners + opening_marks),
        "structure": _merge(corners + structure_marks),
        "total": _merge(total),
        "_face": max(_out(p, outward) for p in ring),
    }


def _same(a: list[float], b: list[float]) -> bool:
    return len(a) == len(b) and all(abs(x - y) <= _EPS for x, y in zip(a, b, strict=True))


def _point_for(value: float, angle: float, outward, cands, face: float):
    """(ponto, referência) que mede ``value``: a candidata mais para fora; sem nenhuma,
    um ponto solto na face."""
    best = None
    for p, ref, _ in cands:
        if abs(_along(p, angle) - value) <= _EPS:
            score = _out(p, outward)
            if best is None or score > best[0] + 1e-9:
                best = (score, p, ref)
    if best is not None:
        return best[1], dict(best[2])
    p = (value, face * outward[1]) if angle == 0.0 else (face * outward[0], value)
    return p, None


def _line_offset(state_angle: float, p0, line_point) -> float:
    a = math.radians(state_angle)
    n = (-math.sin(a), math.cos(a))
    return (line_point[0] - p0[0]) * n[0] + (line_point[1] - p0[1]) * n[1]


def _side_dimensions(doc: Document, storey, outline, side: str, levels, cands) -> list:
    """[(nível, dados da cota)] de um lado, na ordem de dentro para fora."""
    found = _side_levels(doc, storey, outline, side, cands)
    if not found:
        return []
    outward, angle = _SIDE[side]
    face = found["_face"]
    chosen = [lv for lv in LEVELS if lv in levels and len(found[lv]) >= 2]
    # linha que repete outra mais de fora não sai (§2): o total fica, o detalhe sai
    kept = [lv for i, lv in enumerate(chosen)
            if not any(_same(found[lv], found[later]) for later in chosen[i + 1:])]
    out = []
    for i, level in enumerate(kept):
        distance = storeys.paper(storey, FIRST_MM + STEP_MM * i)
        items = [_point_for(v, angle, outward, cands, face) for v in found[level]]
        p0 = items[0][0]
        line = (face + distance) * outward[0], (face + distance) * outward[1]
        line_point = (p0[0], line[1]) if angle == 0.0 else (line[0], p0[1])
        out.append((level, {
            "points": _raw(items), "direction": "fixed", "angle": angle,
            "offset": _line_offset(angle, p0, line_point),
            "auto": {"side": side, "level": level}}))
    return out


def _raw(items) -> list:
    """Pontos para ``create_dimension``: presos (ponto, referência) ou soltos."""
    return [(p, ref) if ref else p for p, ref in items]


def _room_dimensions(doc: Document, storey) -> tuple[list, list]:
    """Largura e profundidade de cada ambiente retangular (face a face, §3)."""
    from brasbim.core.annotations import spaces

    out, skipped = [], []
    distance = storeys.paper(storey, ROOM_MM)
    for space in ifcopenshell.util.element.get_decomposition(storey):
        if not space.is_a("IfcSpace"):
            continue
        outline = spaces.read_state(space).get("outline") or []
        xs = sorted({round(p[0], 6) for p in outline})
        ys = sorted({round(p[1], 6) for p in outline})
        if len(outline) != 4 or len(xs) != 2 or len(ys) != 2:
            skipped.append({"ambiente": space.GlobalId, "motivo": "não é retangular"})
            continue
        index = {(round(p[0], 6), round(p[1], 6)): i for i, p in enumerate(outline)}
        corner = index[(xs[0], ys[0])]
        for axis, other, angle in (("x", index[(xs[1], ys[0])], 0.0),
                                   ("y", index[(xs[0], ys[1])], 90.0)):
            items = [(tuple(outline[i]), {"kind": "vertex", "gid": space.GlobalId,
                                          "index": i}) for i in (corner, other)]
            p0 = items[0][0]
            line_point = (p0[0], p0[1] + distance) if angle == 0.0 else \
                (p0[0] + distance, p0[1])
            out.append(({"room": space.GlobalId, "axis": axis}, {
                "points": _raw(items), "direction": "fixed", "angle": angle,
                "offset": _line_offset(angle, p0, line_point),
                "auto": {"room": space.GlobalId, "axis": axis}}))
    return out, skipped


def _existing(doc: Document, storey) -> list[tuple]:
    """(cota, marca auto, mexida) das cotas automáticas do pavimento."""
    out = []
    for element in ifcopenshell.util.element.get_decomposition(storey):
        kind = base.kind_of(element)
        if kind is None or kind.prefix != "dimension":
            continue
        state = base.read_state(element)
        if state.get("auto"):
            out.append((element, state["auto"], any(state.get(k) for k in _EDITED)))
    return out


def plan(doc: Document, storey, levels=(*LEVELS, ROOMS), sides=SIDES) -> dict:
    """O que ``create`` faria: {"create": [dados], "remove": [gid], "kept": [...],
    "skipped": [...]}."""
    levels, sides = tuple(levels), tuple(sides)
    bad = set(levels) - {*LEVELS, ROOMS}
    if bad:
        raise OpError(f"níveis desconhecidos: {sorted(bad)} (use {', '.join((*LEVELS, ROOMS))})")
    bad = set(sides) - set(SIDES)
    if bad:
        raise OpError(f"lados desconhecidos: {sorted(bad)} (use {', '.join(SIDES)})")
    wanted = []
    skipped = []
    if set(levels) & set(LEVELS):
        outline = _outline(doc, storey)
        if outline is None:
            raise OpError("não há paredes retas para cotar neste pavimento")
        cands = _candidates(doc, storey)
        for side in sides:
            found = _side_dimensions(doc, storey, outline, side, levels, cands)
            if not found:
                skipped.append({"lado": side, "motivo": "sem fachada reta neste lado"})
            wanted += [data for _, data in found]
    if ROOMS in levels:
        rooms, room_skipped = _room_dimensions(doc, storey)
        wanted += [data for _, data in rooms]
        skipped += room_skipped
    old = _existing(doc, storey)
    redo = {(a.get("side"), a.get("level"), a.get("room"), a.get("axis"))
            for a in (d["auto"] for d in wanted)}
    remove, kept = [], []
    for element, auto, edited in old:
        key = (auto.get("side"), auto.get("level"), auto.get("room"), auto.get("axis"))
        if key not in redo:
            continue
        if edited:  # mexida à mão: fica, e a nova não sai
            kept.append(element.GlobalId)
            wanted = [d for d in wanted if (d["auto"].get("side"), d["auto"].get("level"),
                                            d["auto"].get("room"), d["auto"].get("axis"))
                      != key]
        else:
            remove.append(element.GlobalId)
    return {"create": wanted, "remove": remove, "kept": kept, "skipped": skipped}


def create(doc: Document, storey, levels=(*LEVELS, ROOMS), sides=SIDES):
    """Transação "Cotar pavimento" e o resumo (``plan``)."""
    from brasbim.core.annotations import commands as ac
    from brasbim.core.delete import delete_elements
    from brasbim.core.ops.history import combine

    storey = doc.get(storey if isinstance(storey, str) else storey.GlobalId,
                     "IfcBuildingStorey")
    found = plan(doc, storey, levels, sides)
    if not found["create"] and not found["remove"]:
        raise OpError("nada para cotar com esses níveis e lados")
    builders = []
    if found["remove"]:
        builders.append(lambda: delete_elements(doc, found["remove"])[0])
    for data in found["create"]:
        builders.append(lambda d=data: ac.create_dimension(
            doc, storey, d["points"], d["direction"], d["angle"], d["offset"],
            auto=d["auto"]))
    return combine(doc, "Cotar pavimento", builders), found
