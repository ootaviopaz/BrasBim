# SPDX-License-Identifier: LGPL-3.0-or-later
"""Abrir IFC 2x3 e IFC 4 (spec/ui 60)."""

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.type
import ifcopenshell.api.unit
import pytest

from brasbim.core import IFC_SCHEMA, plan
from brasbim.core.document import Document
from brasbim.ui.session import Session


def _owner(monkeypatch, f):
    """O 2x3 exige o histórico do dono em cada objeto."""
    import ifcopenshell.api.owner.settings as owner

    person = f.create_entity("IfcPerson", FamilyName="Teste")
    org = f.create_entity("IfcOrganization", Name="Teste")
    user = f.create_entity("IfcPersonAndOrganization", person, org)
    app = f.create_entity("IfcApplication", org, "1", "Outro", "Outro")
    monkeypatch.setattr(owner, "get_user", lambda f: user)
    monkeypatch.setattr(owner, "get_application", lambda f: app)


def _old_file(path, schema="IFC2X3", monkeypatch=None):
    """Projeto de outro programa: edificação, pavimento, parede, porta com o tipo antigo
    (IfcDoorStyle, só até o IFC 4) e um estilo de superfície na forma do 2x3."""
    f = ifcopenshell.api.project.create_file(version=schema)
    if schema == "IFC2X3":
        _owner(monkeypatch, f)
    project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name="Outro")
    ifcopenshell.api.unit.assign_unit(f)
    ifcopenshell.api.context.add_context(f, context_type="Model")
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite")
    building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding")
    storey = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name="1º")
    ifcopenshell.api.aggregate.assign_object(f, relating_object=project, products=[site])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=site, products=[building])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=building, products=[storey])
    wall = ifcopenshell.api.root.create_entity(f, ifc_class="IfcWall", name="Parede")
    door = ifcopenshell.api.root.create_entity(f, ifc_class="IfcDoor", name="Porta")
    style = f.create_entity("IfcDoorStyle", ifcopenshell.guid.new(), Name="P1",
                            OperationType="SINGLE_SWING_LEFT", ConstructionType="WOOD",
                            ParameterTakesPrecedence=False, Sizeable=False)
    f.create_entity("IfcRelDefinesByType", ifcopenshell.guid.new(), RelatedObjects=[door],
                    RelatingType=style)
    ifcopenshell.api.spatial.assign_container(f, relating_structure=storey,
                                              products=[wall, door])
    if schema == "IFC2X3":
        colour = f.create_entity("IfcColourRgb", None, 0.5, 0.5, 0.5)
        shading = f.create_entity("IfcSurfaceStyleRendering", colour)
        surface = f.create_entity("IfcSurfaceStyle", "Cinza", "BOTH", [shading])
        assignment = f.create_entity("IfcPresentationStyleAssignment", [surface])
        f.create_entity("IfcStyledItem", None, [assignment], None)
    f.write(str(path))
    return path


@pytest.mark.parametrize("schema", ["IFC2X3", "IFC4"])
def test_ao01_converte_para_43(tmp_path, schema, monkeypatch):
    doc = Document.open(str(_old_file(tmp_path / "outro.ifc", schema, monkeypatch)))
    assert doc.ifc.schema_identifier == IFC_SCHEMA and doc.converted_from == schema
    (door_type,) = doc.ifc.by_type("IfcDoorType")  # o estilo antigo vira tipo
    assert door_type.Name == "P1" and door_type.PredefinedType == "DOOR"
    assert door_type.OperationType == "SINGLE_SWING_LEFT"
    (door,) = doc.ifc.by_type("IfcDoor")
    assert ifcopenshell.util.element.get_type(door) == door_type
    assert len(doc.ifc.by_type("IfcWall")) == 1 and len(doc.storeys()) == 1
    plan.storey_plan(doc, doc.storeys()[0])  # a planta se monta (terreno, sólidos…)


def test_ao02_43_abre_como_esta(tmp_path, model):
    path = tmp_path / "nosso.ifc"
    model.doc.save(str(path))
    doc = Document.open(str(path))
    assert doc.converted_from is None


def test_ao03_sessao_nao_grava_por_cima(tmp_path, monkeypatch):
    source = _old_file(tmp_path / "outro.ifc", monkeypatch=monkeypatch)
    before = source.read_bytes()
    session = Session(journal_dir=tmp_path / "diarios")
    seen = []
    session.open(str(source), lambda done, total: seen.append((done, total)))
    assert session.path is None and session.modified  # Salvar pede um nome
    assert any("IFC2X3" in m["text"] and "convertido" in m["text"]
               for m in session.messages)
    assert seen and all(d <= t for d, t in seen)
    assert source.read_bytes() == before


def test_ao04_etiqueta_de_viga_com_contorno_qualquer(model):
    """Viga de outro programa: o contorno na planta pode ter mais de 4 vértices."""
    beam = model.doc.ifc.create_entity("IfcBeam", ifcopenshell.guid.new(), Name="V9")
    ring = [(0, 0), (3, 0), (3, 0.1), (2.9, 0.15), (0.1, 0.15), (0, 0.1)]
    found = [plan._Element(beam, "beam", ring, [], (0.0, 0.4), {}, 0.25)]
    (label,) = plan.structure_labels(found)
    assert label.code.startswith("V9")
    assert label.angle == pytest.approx(0.0)  # ao longo da viga
    assert 1.0 < label.at[0] < 2.0


def test_ao05_selecionar_parede_de_outro_programa(window):
    """Parede com tipo sem as camadas do BrasBim: a barra Opções não quebra."""
    s = window.session
    ifc = s.doc.ifc
    wall = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcWall", name="SW - 209")
    wall_type = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcWallType", name="SW")
    ifcopenshell.api.type.assign_type(ifc, related_objects=[wall], relating_type=wall_type)
    ifcopenshell.api.spatial.assign_container(ifc, relating_structure=s.doc.get(s.storey_id),
                                              products=[wall])
    window.toolbox.activate("select")
    s.select([wall.GlobalId])
    assert window.options_bar._last_label == "Características no painel Propriedades"
