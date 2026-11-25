"""Notas de versão do site (scripts/site/versoes.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("versoes", ROOT / "scripts" / "site" / "versoes.py")
versoes = importlib.util.module_from_spec(_spec)
sys.modules["versoes"] = versoes  # as dataclasses procuram o módulo aqui
_spec.loader.exec_module(versoes)

CHANGELOG = """# Novidades

Texto de abertura.

## [0.2.0] — em desenvolvimento

Aberta ontem.

### Novo
- **Coisa futura.** Ainda não saiu.

## [0.1.0] — 2026‑11‑25

### Novo
- **Busca no Navegador.** Um campo filtra
  a lista `<Navegador>`.
- **Busca no Navegador.** Repetido de propósito.
### Correções
- No Windows, o Alt levava o foco ao menu. Agora não leva.
### Interno
- Só para quem desenvolve.

## [0.0.1] — 2026-11-07

Primeira versão publicada.
"""

INDEX = "<main>\n<!-- versoes:inicio -->\nvelho\n<!-- versoes:fim -->\n</main>\n"
SITEMAP = ("<urlset><url><loc>https://brasbim.org/versoes/</loc>\n"
           "    <lastmod>2000-01-01</lastmod></url></urlset>")


def test_le_so_as_versoes_lancadas():
    lancadas = versoes.released(versoes.parse(CHANGELOG))
    assert [v.number for v in lancadas] == ["0.1.0", "0.0.1"]
    assert [v.date for v in lancadas] == ["2026-11-25", "2026-11-07"]
    assert lancadas[1].intro == ["Primeira versão publicada."]


def test_itens_juntam_as_linhas_e_tiram_o_titulo():
    v = versoes.released(versoes.parse(CHANGELOG))[0]
    novo = dict(v.groups)["Novo"]
    assert novo[0].title == "Busca no Navegador"
    assert novo[0].text.endswith("Um campo filtra a lista `<Navegador>`.")
    sem_titulo = dict(v.groups)["Correções"][0]
    assert sem_titulo.title is None
    assert sem_titulo.summary == "No Windows, o Alt levava o foco ao menu"


def test_pagina_escapa_html_e_esconde_o_grupo_interno():
    page, _, _ = versoes.outputs(CHANGELOG, INDEX, SITEMAP)
    assert "<code>&lt;Navegador&gt;</code>" in page
    assert "<strong>Busca no Navegador.</strong>" in page
    assert "Interno" not in page and "Só para quem desenvolve" not in page
    assert "Coisa futura" not in page
    assert 'id="v0.1.0-busca-no-navegador"' in page
    assert 'id="v0.1.0-busca-no-navegador-2"' in page  # âncoras únicas
    assert "25 de novembro de 2026" in page


def test_pagina_inicial_mostra_a_ultima_versao():
    _, index, sitemap = versoes.outputs(CHANGELOG, INDEX, SITEMAP)
    assert "velho" not in index
    assert "Novidades da versão 0.1.0" in index
    assert 'href="versoes/#v0.1.0-busca-no-navegador"' in index
    assert index.startswith("<main>\n<!-- versoes:inicio -->") and index.endswith("</main>\n")
    assert "<lastmod>2026-11-25</lastmod>" in sitemap


def test_titulo_comprido_e_cortado_numa_palavra():
    item = versoes.Item(None, "palavra " * 20)
    assert len(item.short) <= versoes.SHORT + 1 and item.short.endswith("palavra…")
    aberto = versoes.Item(None, "Ao fim de um pedido ao Assistente, os objetos (mobiliário, louças e mais)")
    assert aberto.short == "Ao fim de um pedido ao Assistente, os objetos…"


def test_site_em_dia_com_o_changelog():
    """Ao lançar uma versão, rode ``python scripts/site/versoes.py``."""
    assert versoes.main(["--conferir"]) == 0
