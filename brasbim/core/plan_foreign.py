# SPDX-License-Identifier: LGPL-3.0-or-later
"""Elementos de outro programa na planta (``spec/ui/60-abrir-ifc-de-outro-esquema.md`` §3).

Parede, escada, móvel, fachada-cortina, peça genérica… que não tem os dados do BrasBim
para o desenho paramétrico aparece pela malha do corpo, como no corte (spec/ui 14 §4):

- **cortado**: a interseção da malha com o plano de corte, com fundo e contorno grosso;
- **em vista**: as arestas do corpo abaixo do plano, projetadas, em linha fina, sem o que
  fica sob as partes cortadas.

As malhas ficam guardadas por elemento (posição e representação), para a planta não
refazer a triangulação a cada redesenho.
"""

from __future__ import annotations

import logging
import weakref

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np

from brasbim.core import clip, props

log = logging.getLogger(__name__)

SKIP = ("IfcOpeningElement", "IfcVirtualElement", "IfcFeatureElement", "IfcSpatialElement",
        "IfcAnnotation", "IfcGrid")
_MIN = 1e-3  # m: aresta projetada menor que isto não aparece
_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


# Psets que o BrasBim põe também em elementos de outro programa (situação, penas): não
# fazem do elemento um elemento paramétrico.
_ANY_ELEMENT_PSETS = ("BrasBim_Intervencao", "BrasBim_PenasElemento")


def own(element) -> bool:
    """O elemento tem os dados de um elemento do BrasBim (desenho paramétrico)."""
    psets = ifcopenshell.util.element.get_psets(element, psets_only=True,
                                                 should_inherit=False)
    return any(name.startswith("BrasBim_") and name not in _ANY_ELEMENT_PSETS
               for name in psets)


def is_foreign(element) -> bool:
    """Peça de outro programa que só se desenha pela malha: elemento com corpo, sem os
    dados do BrasBim, nem ele nem o conjunto de que faz parte."""
    if element is None or not element.is_a("IfcElement") or element.Representation is None             or any(element.is_a(c) for c in SKIP):
        return False
    return not own(element) and not own(owner_of(element))


def owner_of(element):
    """Quem a peça representa: o conjunto de fora (escada, fachada-cortina, rampa)."""
    top = element
    while True:
        up = ifcopenshell.util.element.get_aggregate(top)
        if up is None or not up.is_a("IfcElement"):
            return top
        top = up


def _key(element) -> tuple:
    m = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement) \
        if element.ObjectPlacement is not None else np.eye(4)
    reps = element.Representation.Representations if element.Representation else ()
    return (np.round(m, 9).tobytes(), tuple(r.id() for r in reps))


def _settings():
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    return settings


def shapes(doc, elements, progress=None) -> dict:
    """{GlobalId: geometria do IfcOpenShell} (coordenadas do mundo), da reserva ou
    triangulada agora — as que faltam, juntas e em paralelo. A planta e o 3D usam a mesma
    reserva: o elemento é triangulado uma vez só enquanto não muda."""
    store = _cache.setdefault(doc, {})
    out, missing = {}, []
    for e in elements:
        key = _key(e)
        found = store.get(e.GlobalId)
        if found is not None and found[0] == key:
            if found[1] is not None:
                out[e.GlobalId] = found[1]
        else:
            missing.append((e, key))
    if missing:
        made = geometries(doc.ifc, [e for e, _ in missing], progress=progress)             if len(missing) > 8 else {}
        settings = _settings()
        for e, key in missing:
            g = made.get(e.id())
            if g is None:
                try:
                    g = props.body_shape(settings, e).geometry
                except (RuntimeError, ValueError) as error:
                    log.debug("sem geometria para %s: %s", e.GlobalId, error)
            if g is not None and not len(g.faces):
                g = None
            store[e.GlobalId] = (key, g, None)
            if g is not None:
                out[e.GlobalId] = g
    return out


def meshes(doc, elements) -> dict:
    """{GlobalId: (vértices, faces, quinas)} em coordenadas do mundo; o que não se
    triangula fica de fora."""
    found = shapes(doc, elements)
    store = _cache[doc]
    out = {}
    for gid, g in found.items():
        key, _, mesh = store[gid]
        if mesh is None:
            mesh = _mesh(g)
            store[gid] = (key, g, mesh)
        if mesh is not None:
            out[gid] = mesh
    return out


def _mesh(g):
    """(vértices, faces, quinas): só as quinas e as bordas (a divisão em triângulos de uma
    face plana ou curva não aparece)."""
    from brasbim.core.freeform.mesh import crease_edges

    verts = np.asarray(g.verts, dtype=float).reshape(-1, 3)
    faces = np.asarray(g.faces, dtype=np.int64).reshape(-1, 3)
    if not len(faces):
        return None
    return verts, faces, crease_edges(verts, faces)


def geometries(ifc, elements, settings=None, progress=None) -> dict:
    """Triangulação de muitos elementos de uma vez, em paralelo: {id do elemento:
    geometria do IfcOpenShell}. O que falhar fica de fora (quem chama faz um a um).
    ``progress(feitos, total)`` de tempos em tempos."""
    import multiprocessing

    out = {}
    if not elements:
        return out
    try:
        it = ifcopenshell.geom.iterator(settings or _settings(), ifc,
                                        max(1, multiprocessing.cpu_count()), include=elements)
        if not it.initialize():
            return out
        while True:
            shape = it.get()
            out[shape.id] = shape.geometry
            if progress and len(out) % 50 == 0:
                progress(len(out), len(elements))
            if not it.next():
                break
    except RuntimeError as error:
        log.debug("triangulação em lote falhou: %s", error)
    return out


def _section(local: np.ndarray, faces: np.ndarray, cut: float) -> list:
    """Anéis da interseção com o plano z = ``cut`` (em x, y)."""
    from brasbim.core.drawings.section import _chain

    z = local[faces][:, :, 2] - cut
    crossing = (z.min(axis=1) < 0) & (z.max(axis=1) > 0)
    segments = []
    for tri in faces[crossing]:
        p = local[tri]
        pts = []
        for i in range(3):
            a, b = p[i], p[(i + 1) % 3]
            za, zb = a[2] - cut, b[2] - cut
            if (za < 0) != (zb < 0):
                t = -za / (zb - za)
                q = a + t * (b - a)
                pts.append((float(q[0]), float(q[1])))
        if len(pts) == 2 and abs(pts[0][0] - pts[1][0]) + abs(pts[0][1] - pts[1][1]) > 1e-9:
            segments.append(tuple(pts))
    return _chain(segments) if segments else []


def _view_lines(local: np.ndarray, edges: np.ndarray, cut: float) -> list:
    """Arestas abaixo do plano (a parte de baixo das que o cruzam), projetadas."""
    a, b = local[edges[:, 0]], local[edges[:, 1]]
    below = (a[:, 2] <= cut) | (b[:, 2] <= cut)
    a, b = a[below], b[below]
    over_a, over_b = a[:, 2] > cut, b[:, 2] > cut
    # a parte de baixo de quem cruza o plano
    for over, keep, other in ((over_a, a, b), (over_b, b, a)):
        if over.any():
            t = (cut - other[over, 2]) / (keep[over, 2] - other[over, 2])
            keep[over] = other[over] + t[:, None] * (keep[over] - other[over])
    d = np.hypot(a[:, 0] - b[:, 0], a[:, 1] - b[:, 1])
    a, b = a[d > _MIN], b[d > _MIN]
    seen, out = set(), []
    for p, q in zip(a[:, :2].round(4).tolist(), b[:, :2].round(4).tolist(), strict=True):
        k = (tuple(p), tuple(q)) if p <= q else (tuple(q), tuple(p))
        if k not in seen:
            seen.add(k)
            out.append([tuple(p), tuple(q)])
    return out


def draw(doc, storey, elements, cut: float) -> tuple[dict, dict]:
    """({dono: anéis cortados}, {dono: linhas em vista}) dos ``elements`` do pavimento,
    em coordenadas do pavimento; o que fica todo acima do plano não aparece."""
    found = meshes(doc, elements)
    m = np.linalg.inv(ifcopenshell.util.placement.get_local_placement(storey.ObjectPlacement))
    cut_rings: dict = {}
    view: dict = {}
    for e in elements:
        mesh = found.get(e.GlobalId)
        if mesh is None:
            continue
        verts, faces, edges = mesh
        local = (m @ np.c_[verts, np.ones(len(verts))].T).T[:, :3]
        if local[:, 2].min() > cut:
            continue  # todo acima do plano
        owner = owner_of(e).GlobalId
        if local[:, 2].max() > cut:
            rings = _section(local, faces, cut)
            if rings:
                cut_rings.setdefault(owner, []).extend(rings)
        lines = _view_lines(local, edges, cut)
        if lines:
            view.setdefault(owner, []).extend(lines)
    covered = [r for rings in cut_rings.values() for r in rings]
    if covered:  # o que está em vista sob uma parte cortada não aparece
        outside = clip.difference([[(-1e5, -1e5), (1e5, -1e5), (1e5, 1e5), (-1e5, 1e5)]],
                                  covered)
        view = {o: kept for o, lines in view.items()
                if (kept := clip.clip_lines(lines, outside))}
    return cut_rings, view


def prepare(doc, progress=None) -> int:
    """Triangula de uma vez as peças de outro programa do projeto (logo depois de abrir),
    para a planta e o 3D não pararem na primeira vez. Devolve quantas são."""
    elements = [e for e in doc.ifc.by_type("IfcElement") if is_foreign(e)]
    if elements:
        shapes(doc, elements, progress)
    return len(elements)
