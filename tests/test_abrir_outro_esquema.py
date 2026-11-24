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
import ifcopenshell.util.element
import ifcopenshell.util.placement
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
    assert doc.ifc.schema_identifier == IFC_SCHEMA
    assert doc.converted_from == f"{schema}, em milímetros"  # assign_unit: mm
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


# --- peças de outro programa na planta e no 3D (spec/ui 60 §5) ----------------------------


def _box(model, ifc_class, x, y, z, size, name="Peça", aggregate=None):
    """Peça de outro programa: caixa (x, y, z) a (x + dx, y + dy, z + dz), sem Pset do
    BrasBim, no térreo."""
    import ifcopenshell.api.geometry

    ifc = model.doc.ifc
    e = ifcopenshell.api.root.create_entity(ifc, ifc_class=ifc_class, name=name)
    body = ifcopenshell.api.geometry.add_wall_representation(
        ifc, context=model.doc.body_context, length=size[0], height=size[2], thickness=size[1])
    ifcopenshell.api.geometry.assign_representation(ifc, product=e, representation=body)
    ifcopenshell.api.geometry.edit_object_placement(
        ifc, product=e, matrix=ifcopenshell.util.placement.get_local_placement(
            model.terreo.ObjectPlacement) @ _move(x, y, z))
    if aggregate is not None:
        ifcopenshell.api.aggregate.assign_object(ifc, relating_object=aggregate, products=[e])
    else:
        ifcopenshell.api.spatial.assign_container(ifc, relating_structure=model.terreo,
                                                  products=[e])
    return e


def _move(x, y, z):
    import numpy as np

    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


def test_ao06_pecas_de_outro_programa_na_planta(model):
    import ifcopenshell.util.placement

    wall = _box(model, "IfcWall", 0, 0, 0, (4.0, 0.2, 3.0), "Parede de fora")
    table = _box(model, "IfcFurniture", 1, 1, 0, (1.0, 0.6, 0.75), "Mesa")
    member = _box(model, "IfcMember", 0, 2, 2.4, (3.0, 0.1, 0.1), "Montante alto")
    stair = ifcopenshell.api.root.create_entity(model.doc.ifc, ifc_class="IfcStair")
    ifcopenshell.api.spatial.assign_container(model.doc.ifc, relating_structure=model.terreo,
                                              products=[stair])
    _box(model, "IfcStairFlight", 5, 0, 0, (1.0, 3.0, 1.0), "Lance", aggregate=stair)
    drawn = plan.storey_plan(model.doc, model.terreo)
    by_role = {}
    for s in drawn.shapes:
        by_role.setdefault(s.role, set()).add(s.owner)
    # a parede cortada: contorno para escolher, fundo e borda grossa
    assert wall.GlobalId in by_role["foreign"]
    (ring,) = [s.points for s in drawn.shapes if s.owner == wall.GlobalId
               and s.role == "foreign"]
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    assert (min(xs), max(xs)) == pytest.approx((0, 4)) and max(ys) - min(ys) == \
        pytest.approx(0.2)
    assert any(r.key == wall.GlobalId for r in drawn.regions)
    # a mesa, abaixo do plano: em vista; o montante, acima: não aparece
    assert table.GlobalId in by_role["foreign_view"]
    assert table.GlobalId not in by_role["foreign"]
    assert member.GlobalId not in by_role.get("foreign", set()) | by_role["foreign_view"]
    # a peça da escada responde pela escada
    assert stair.GlobalId in by_role["foreign_view"]


def test_ao07_parametrico_nao_vira_malha(model):
    """Parede do BrasBim fica com o desenho de sempre (nada de ``foreign``)."""
    model.wall((0, 0), (4, 0))
    drawn = plan.storey_plan(model.doc, model.terreo)
    assert not [s for s in drawn.shapes if s.role.startswith("foreign")]


def test_ao08_pecas_de_outro_programa_no_3d(model):
    from brasbim.ui import scene3d

    table = _box(model, "IfcFurniture", 1, 1, 0, (1.0, 0.6, 0.75), "Mesa")
    member = _box(model, "IfcMember", 0, 2, 2.4, (3.0, 0.1, 0.1), "Montante")
    proxies = [_box(model, "IfcBuildingElementProxy", i, 5, 0, (0.5, 0.5, 0.5))
               for i in range(10)]  # mais de 8: triangulação em lote
    scene = scene3d.Scene()
    scene.load(model.doc.ifc, model.doc)
    assert {table.GlobalId, member.GlobalId} <= set(scene.meshes)
    assert {p.GlobalId for p in proxies} <= set(scene.meshes)


def test_ao09_arquivo_em_milimetros(tmp_path, model):
    """IFC 4.3 em mm: as medidas passam para metros ao abrir."""
    import ifcopenshell.api.unit

    f = ifcopenshell.api.project.create_file(version="IFC4X3")
    project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name="mm")
    unit = ifcopenshell.api.unit.add_si_unit(f, unit_type="LENGTHUNIT", prefix="MILLI")
    ifcopenshell.api.unit.assign_unit(f, units=[unit])
    ifcopenshell.api.context.add_context(f, context_type="Model")
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite")
    building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding")
    storey = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey")
    storey.Elevation = 3250.0
    ifcopenshell.api.aggregate.assign_object(f, relating_object=project, products=[site])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=site, products=[building])
    ifcopenshell.api.aggregate.assign_object(f, relating_object=building, products=[storey])
    path = tmp_path / "mm.ifc"
    f.write(str(path))
    doc = Document.open(str(path))
    assert doc.converted_from == "em milímetros"
    assert doc.storeys()[0].Elevation == pytest.approx(3.25)
