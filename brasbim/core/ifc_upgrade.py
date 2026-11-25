# SPDX-License-Identifier: LGPL-3.0-or-later
"""Abrir IFC 2x3 e IFC 4 (``spec/ui/60-abrir-ifc-de-outro-esquema.md``): o arquivo é
convertido para o 4.3, o esquema do BrasBim, pelo ``ifcopenshell.util.schema.Migrator``
(2x3 → 4 → 4.3, o caminho inverso do Exportar IFC, spec/ui 47), e as medidas de um
arquivo em mm, cm ou pés passam para metros, a unidade do modelo do BrasBim."""

from __future__ import annotations

import contextlib
import io
from collections.abc import Callable

import ifcopenshell
import ifcopenshell.util.schema
import ifcopenshell.util.unit

from brasbim.core import IFC_SCHEMA

# classes do IFC 4 que o 4.3 não tem mais, e a que as substitui
_TO_4X3 = {
    "IfcDoorStyle": ("IfcDoorType", "DOOR"),
    "IfcWindowStyle": ("IfcWindowType", "WINDOW"),
    "IfcBeamStandardCase": ("IfcBeam", None),
    "IfcColumnStandardCase": ("IfcColumn", None),
    "IfcDoorStandardCase": ("IfcDoor", None),
    "IfcMemberStandardCase": ("IfcMember", None),
    "IfcOpeningStandardCase": ("IfcOpeningElement", None),
    "IfcPlateStandardCase": ("IfcPlate", None),
    "IfcSlabElementedCase": ("IfcSlab", None),
    "IfcSlabStandardCase": ("IfcSlab", None),
    "IfcWallElementedCase": ("IfcWall", None),
    "IfcWindowStandardCase": ("IfcWindow", None),
}


class _Migrator(ifcopenshell.util.schema.Migrator):
    def migrate_class(self, element, new_file):
        found = _TO_4X3.get(element.is_a()) if new_file.schema == "IFC4X3" else None
        if found is None:
            return super().migrate_class(element, new_file)
        new = new_file.create_entity(found[0])
        if found[1]:  # o tipo do 4.3 pede o tipo predefinido, que o estilo não tinha
            new.PredefinedType = found[1]
        return new


def needs_upgrade(ifc: ifcopenshell.file) -> bool:
    return ifc.schema_identifier != IFC_SCHEMA and ifc.schema != "IFC4X3"


def _step(src: ifcopenshell.file, schema: str, progress: Callable | None,
          done: int, total: int) -> ifcopenshell.file:
    out = ifcopenshell.file(schema=schema)
    migrator = _Migrator()
    # o conversor imprime cada atributo sem equivalente: não é erro
    with contextlib.redirect_stdout(io.StringIO()):
        migrator.preprocess(src, out)
        for i, e in enumerate(src):
            migrator.migrate(e, out)
            if progress and i % 20000 == 0:
                progress(done + i, total)
    return out


def upgrade(ifc: ifcopenshell.file, progress: Callable | None = None) -> ifcopenshell.file:
    """O mesmo modelo no IFC 4.3 (o próprio arquivo, se já estiver nele). ``progress(n,
    total)`` é chamado de tempos em tempos (arquivos grandes levam minutos)."""
    if not needs_upgrade(ifc):
        return ifc
    steps = ["IFC4", "IFC4X3"] if ifc.schema == "IFC2X3" else ["IFC4X3"]
    per = len(list(ifc)) if progress else 0
    total = per * len(steps)
    for k, schema in enumerate(steps):
        ifc = _step(ifc, schema, progress, k * per, total)
    return ifc


UNIT_NAMES = {0.001: "milímetros", 0.01: "centímetros", 0.3048: "pés", 0.0254: "polegadas"}


def length_scale(ifc: ifcopenshell.file) -> float:
    try:
        return float(ifcopenshell.util.unit.calculate_unit_scale(ifc))
    except (AttributeError, IndexError, RuntimeError, TypeError):
        return 1.0


def to_meters(ifc: ifcopenshell.file) -> ifcopenshell.file:
    """O arquivo com as medidas de comprimento em metros (o próprio, se já estiver)."""
    if abs(length_scale(ifc) - 1.0) < 1e-12:
        return ifc
    with contextlib.redirect_stdout(io.StringIO()):
        return ifcopenshell.util.unit.convert_file_length_units(ifc, "METER")


def prepare(ifc: ifcopenshell.file, progress: Callable | None = None
            ) -> tuple[ifcopenshell.file, list[str]]:
    """Esquema 4.3 e medidas em metros; devolve o arquivo e o que foi convertido
    (``["IFC2X3", "milímetros"]``), vazio se nada mudou."""
    notes = []
    if needs_upgrade(ifc):
        notes.append(ifc.schema)
        ifc = upgrade(ifc, progress)
    scale = length_scale(ifc)
    if abs(scale - 1.0) > 1e-12:
        notes.append(next((name for s, name in UNIT_NAMES.items() if abs(s - scale) < 1e-9),
                          f"unidade de {scale:g} m"))
        ifc = to_meters(ifc)
    return ifc, notes
