"""Notas de versão do site do BrasBim, geradas do CHANGELOG.md.

Lê as versões **lançadas** (as que têm data; a "em desenvolvimento" fica de fora) e grava:
- ``site/versoes/index.html``: a página com as notas completas de cada versão;
- o bloco entre ``<!-- versoes:inicio -->`` e ``<!-- versoes:fim -->`` em
  ``site/index.html``: a seção "Novidades da versão X", com os títulos da última;
- a data da última versão no ``<lastmod>`` de ``/versoes/`` em ``site/sitemap.xml``.

O grupo **Interno** (só para quem desenvolve) não vai para o site.

Uso, na raiz do repositório:
    python scripts/site/versoes.py            # grava os arquivos
    python scripts/site/versoes.py --conferir # só confere (sai com 1 se estiver velho)

Rode ao lançar uma versão, depois de datar a seção no CHANGELOG.md. O teste
``tests/test_site_versoes.py`` falha enquanto o site não estiver em dia com o CHANGELOG.
"""

from __future__ import annotations

import html
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
REPO = "https://github.com/ootaviopaz/BrasBim"
START, END = "<!-- versoes:inicio -->", "<!-- versoes:fim -->"
HIDDEN_GROUPS = {"Interno"}
HOME_ITEMS = 9  # títulos do grupo Novo mostrados na página inicial
SHORT = 64  # tamanho máximo de um título na página inicial
MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro")

_VERSION = re.compile(r"^## \[(?P<num>[^\]]+)\]\s*[—-]\s*(?P<when>.+?)\s*$")
_DATE = re.compile(r"^(\d{4})[-‑](\d{2})[-‑](\d{2})$")


@dataclass
class Item:
    title: str | None  # texto em negrito do começo, sem o ponto final
    text: str  # markdown do item inteiro, numa linha só

    @property
    def summary(self) -> str:
        """Título, ou a primeira frase quando o item não tem título."""
        if self.title:
            return self.title
        plain = _plain(self.text)
        return re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0].rstrip(".")

    @property
    def short(self) -> str:
        """O resumo cortado numa palavra inteira, para a página inicial."""
        text = self.summary
        if len(text) <= SHORT:
            return text
        cut = text[:SHORT].rsplit(" ", 1)[0]
        if cut.count("(") > cut.count(")"):  # não deixa parêntese aberto
            cut = cut[:cut.rindex("(")]
        cut = cut.rstrip(" ,;:(")
        return cut + "…"


@dataclass
class Version:
    number: str
    date: str | None  # AAAA-MM-DD; None = em desenvolvimento
    intro: list[str] = field(default_factory=list)
    groups: list[tuple[str, list[Item]]] = field(default_factory=list)

    @property
    def anchor(self) -> str:
        return "v" + self.number

    def shown_groups(self) -> list[tuple[str, list[Item]]]:
        return [(name, items) for name, items in self.groups
                if name not in HIDDEN_GROUPS and items]


def parse(text: str) -> list[Version]:
    """As versões do CHANGELOG, na ordem do arquivo (a mais nova primeiro)."""
    versions: list[Version] = []
    current: Version | None = None
    items: list[Item] | None = None
    lines: list[str] = []  # item ou parágrafo em andamento

    def flush() -> None:
        if not lines or current is None:
            lines.clear()
            return
        joined = " ".join(s.strip() for s in lines)
        lines.clear()
        if joined.startswith("- "):
            body = joined[2:]
            m = re.match(r"\*\*(.+?)\*\*", body)
            title = m.group(1).strip().rstrip(".") if m else None
            if items is not None:
                items.append(Item(title, body))
        elif items is None:
            current.intro.append(joined)

    for raw in text.splitlines():
        line = raw.rstrip()
        m = _VERSION.match(line)
        if m:
            flush()
            when = m.group("when")
            d = _DATE.match(when)
            current = Version(m.group("num"), "-".join(d.groups()) if d else None)
            versions.append(current)
            items = None
        elif current is None:
            continue
        elif line.startswith("### "):
            flush()
            items = []
            current.groups.append((line[4:].strip(), items))
        elif not line:
            flush()
        elif line.startswith("- "):
            flush()
            lines.append(line)
        else:
            lines.append(line)
    flush()
    return versions


def released(versions: list[Version]) -> list[Version]:
    return [v for v in versions if v.date]


# ---------------------------------------------------------------- texto


def _inline(md: str) -> str:
    """Markdown de uma linha (negrito e código) para HTML."""
    out = html.escape(md, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)


def _plain(md: str) -> str:
    return re.sub(r"\*\*|`", "", md)


def _slug(text: str) -> str:
    base = unicodedata.normalize("NFKD", _plain(text).replace("‑", "-")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:60]


def long_date(date: str) -> str:
    y, m, d = (int(p) for p in date.split("-"))
    return f"{d} de {MONTHS[m - 1]} de {y}"


def _item_ids(version: Version) -> dict[int, str]:
    """Âncora de cada item (pelo id do objeto), única dentro da página."""
    ids: dict[int, str] = {}
    seen: set[str] = set()
    for _, items in version.shown_groups():
        for item in items:
            base = f"{version.anchor}-{_slug(item.summary)}"
            slug, n = base, 2
            while slug in seen:
                slug, n = f"{base}-{n}", n + 1
            seen.add(slug)
            ids[id(item)] = slug
    return ids


# ---------------------------------------------------------------- página inicial


def render_home(version: Version) -> str:
    ids = _item_ids(version)
    groups = version.shown_groups()
    cards = []
    for name, items in groups:
        shown = items[:HOME_ITEMS] if name == "Novo" else items
        lis = "\n".join(
            f'            <li><a href="versoes/#{ids[id(i)]}">{html.escape(i.short)}</a></li>'
            for i in shown)
        rest = len(items) - len(shown)
        more = (f'\n          <a class="versoes-mais" href="versoes/#{version.anchor}">'
                f"e mais {rest} novidades</a>") if rest else ""
        wide = " versoes-grupo-largo" if name == "Novo" else ""
        cards.append(f"""        <div class="versoes-grupo{wide}">
          <h3>{html.escape(name)} <span>{len(items)}</span></h3>
          <ul>
{lis}
          </ul>{more}
        </div>""")
    body = "\n".join(cards)
    return f"""{START}
    <!-- Gerado por scripts/site/versoes.py a partir do CHANGELOG.md: não editar à mão. -->
    <section id="versoes" class="bloco versoes">
      <h2 class="titulo-bloco">Novidades da versão {version.number}</h2>
      <p class="versoes-data">Publicada em {long_date(version.date)}.
        <a href="versoes/#{version.anchor}">Notas completas</a> ·
        <a href="versoes/">Todas as versões</a></p>
      <div class="versoes-grupos">
{body}
      </div>
    </section>
    {END}"""


# ---------------------------------------------------------------- página de versões


def _version_block(version: Version) -> str:
    ids = _item_ids(version)
    parts = [f"""      <article class="nota" id="{version.anchor}">
        <header class="nota-cabeca">
          <h2><a href="#{version.anchor}">{html.escape(version.number)}</a></h2>
          <p><time datetime="{version.date}">{long_date(version.date)}</time> ·
            <a href="{REPO}/releases/tag/{version.anchor}">Baixar esta versão</a></p>
        </header>"""]
    for para in version.intro:
        parts.append(f"        <p class=\"nota-intro\">{_inline(para)}</p>")
    for name, items in version.shown_groups():
        lis = "\n".join(f'          <li id="{ids[id(i)]}">{_inline(i.text)}</li>' for i in items)
        parts.append(f"""        <h3>{html.escape(name)}</h3>
        <ul>
{lis}
        </ul>""")
    parts.append("      </article>")
    return "\n".join(parts)


def render_page(versions: list[Version]) -> str:
    latest = versions[0]
    index = "\n".join(
        f'          <li><a href="#{v.anchor}">{html.escape(v.number)}</a> '
        f'<span>{long_date(v.date)}</span></li>' for v in versions)
    blocks = "\n".join(_version_block(v) for v in versions)
    desc = (f"Notas de versão do BrasBim, software BIM gratuito e de código aberto: o que mudou "
            f"em cada versão. A mais recente é a {latest.number}, de {long_date(latest.date)}.")
    return f"""<!DOCTYPE html>
<!-- Gerado por scripts/site/versoes.py a partir do CHANGELOG.md: não editar à mão. -->
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Versões do BrasBim: notas de versão e novidades</title>
  <meta name="description" content="{html.escape(desc)}">
  <link rel="canonical" href="https://brasbim.org/versoes/">
  <meta name="robots" content="index, follow">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="pt_BR">
  <meta property="og:site_name" content="BrasBim">
  <meta property="og:url" content="https://brasbim.org/versoes/">
  <meta property="og:title" content="Versões do BrasBim">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:image" content="https://brasbim.org/imagens/torre-abertura.jpg">
  <link rel="icon" href="../imagens/simbolo-32.png">
  <link rel="apple-touch-icon" href="../imagens/simbolo-128.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&display=swap">
  <link rel="stylesheet" href="../estilo.css">
</head>
<body>
  <a class="pular" href="#conteudo">Pular para o conteúdo</a>

  <header class="topo">
    <div class="topo-dentro">
      <a class="marca" href="../">
        <img src="../imagens/simbolo-128.png" alt="" width="30" height="30">
        <span>BrasBim</span>
      </a>
      <nav aria-label="Principal">
        <a href="../#recursos">Recursos</a>
        <a href="../#roteiro">Roteiro</a>
        <a href="../#forum">Fórum</a>
        <a href="./" aria-current="page">Versões</a>
        <a href="https://github.com/ootaviopaz/BrasBim">Código</a>
        <a class="botao" href="../#baixar">Baixar</a>
      </nav>
    </div>
  </header>

  <main id="conteudo" class="notas">
    <div class="notas-dentro">
      <aside class="notas-indice">
        <h1>Versões</h1>
        <p>O que mudou em cada versão do BrasBim, da mais nova para a mais antiga.</p>
        <ol>
{index}
        </ol>
        <a class="botao" href="../#baixar">Baixar a {html.escape(latest.number)}</a>
      </aside>
      <div class="notas-lista">
{blocks}
        <p class="notas-rodape">A lista completa, com as mudanças internas, está no
          <a href="{REPO}/blob/main/CHANGELOG.md">CHANGELOG.md</a>.</p>
      </div>
    </div>
  </main>

  <footer class="rodape">
    <div class="rodape-fim">
      <a class="marca" href="../"><img src="../imagens/simbolo-128.png" alt="" width="26" height="26"><span>BrasBim</span></a>
      <p>Criado e mantido por Otávio Paz e pelos contribuidores do projeto.</p>
    </div>
  </footer>
</body>
</html>
"""


# ---------------------------------------------------------------- arquivos


def outputs(changelog: str, index_html: str, sitemap: str) -> tuple[str, str, str]:
    """(página de versões, index.html, sitemap.xml) atualizados."""
    versions = released(parse(changelog))
    if not versions:
        raise SystemExit("CHANGELOG.md sem nenhuma versão lançada (com data)")
    page = render_page(versions)
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(index_html):
        raise SystemExit(f"site/index.html sem os marcadores {START} … {END}")
    index_html = pattern.sub(lambda _: render_home(versions[0]), index_html, count=1)
    loc = re.compile(r"(<loc>https://brasbim\.org/versoes/</loc>\s*<lastmod>)[^<]*(</lastmod>)")
    if not loc.search(sitemap):
        raise SystemExit("site/sitemap.xml sem a entrada https://brasbim.org/versoes/")
    sitemap = loc.sub(lambda m: m.group(1) + versions[0].date + m.group(2), sitemap, count=1)
    return page, index_html, sitemap


def _read(path: Path) -> str:
    # CRLF de um checkout no Windows (core.autocrlf) não conta como diferença
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def main(argv: list[str]) -> int:
    files = (SITE / "versoes" / "index.html", SITE / "index.html", SITE / "sitemap.xml")
    old = [(_read(p) if p.exists() else "") for p in files]
    new = outputs(_read(ROOT / "CHANGELOG.md"), old[1], old[2])
    stale = [p for p, a, b in zip(files, old, new, strict=True) if a != b]
    if "--conferir" in argv:
        for p in stale:
            print(f"desatualizado: {p.relative_to(ROOT)}")
        return 1 if stale else 0
    for p, text in zip(files, new, strict=True):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    for p in stale:
        print(f"gravado: {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
