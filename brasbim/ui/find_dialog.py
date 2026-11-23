# SPDX-License-Identifier: GPL-3.0-or-later
"""Janela Localizar e substituir (``spec/ui/55-estilo-de-anotacao-localizar-ajustes-copia.md``
§3), não modal. A lógica fica em ``brasbim.core.find``."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from brasbim.core import display_layers, edit_state, find, intervention
from brasbim.core.annotations import style as annotation_style
from brasbim.core.document import OpError
from brasbim.ui import theme
from brasbim.ui.tools import fmt, parse_number

FIELD_LABELS = {k: label for k, label, _ in find.FIELDS}


class _Row(QWidget):
    """Uma linha de critério: campo · (propriedade) · condição · valor · tirar."""

    def __init__(self, dialog, row: dict | None = None):
        super().__init__()
        self.dialog = dialog
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.field = QComboBox()
        for key, label, _ in find.FIELDS:
            self.field.addItem(label, key)
        self.prop = QComboBox()
        self.prop.setEditable(True)
        self.prop.setMinimumContentsLength(14)
        self.prop.lineEdit().setPlaceholderText("Pset.Propriedade")
        self.op = QComboBox()
        self.value = QLineEdit()
        self.value.setPlaceholderText("valor (entre: 1;3)")
        remove = QPushButton("×")
        remove.setToolTip("Tira este critério")
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda: dialog.remove_row(self))
        for w in (self.field, self.prop, self.op):
            layout.addWidget(w)
        layout.addWidget(self.value, 1)
        layout.addWidget(remove)
        self.field.currentIndexChanged.connect(self._field_changed)
        self._field_changed()
        if row:
            self.load(row)

    def _field_changed(self) -> None:
        key = self.field.currentData()
        kind = find.FIELD_KINDS[key]
        current = self.op.currentData()
        self.op.clear()
        ops = find.NUMBER_OPS if kind == "number" else find.TEXT_OPS
        if key == "property":
            ops = (*find.TEXT_OPS, *find.NUMBER_OPS)
        for k, label in (*ops, *find.VALUE_OPS):
            self.op.addItem(label, k)
        index = self.op.findData(current)
        self.op.setCurrentIndex(max(0, index))
        self.prop.setVisible(key in ("property", "quantity"))
        if key == "property" and self.prop.count() == 0:
            for pset, prop in find.known_properties(self.dialog.session.doc):
                self.prop.addItem(f"{pset}.{prop}")

    def load(self, row: dict) -> None:
        self.field.setCurrentIndex(self.field.findData(row["field"]))
        if row["field"] == "property":
            self.prop.setEditText(f"{row.get('pset', '')}.{row.get('prop', '')}")
        elif row["field"] == "quantity":
            self.prop.setEditText(row.get("prop", ""))
        self.op.setCurrentIndex(max(0, self.op.findData(row["op"])))
        self.value.setText("" if row.get("value") is None else str(row["value"]))

    def to_dict(self) -> dict:
        key = self.field.currentData()
        row = {"field": key, "op": self.op.currentData(), "value": self.value.text().strip()}
        text = self.prop.currentText().strip()
        if key == "property":
            pset, _, prop = text.rpartition(".")
            row.update(pset=pset, prop=prop)
        elif key == "quantity":
            row["prop"] = text
        return row


class FindDialog(QDialog):
    """Localizar (critérios, somar/tirar da seleção, critérios salvos) e Substituir."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.found: list[str] = []
        self.setWindowTitle("Localizar e substituir")
        self.setModal(False)
        self.resize(640, 520)
        tabs = self.tabs = QTabWidget()
        tabs.addTab(self._find_tab(), "Localizar")
        tabs.addTab(self._replace_tab(), "Substituir")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {theme.INK_SOFT}")
        layout.addWidget(self.status)
        self.refresh_saved()

    # --- Localizar ------------------------------------------------------------------

    def _find_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        top.addWidget(QLabel("Critérios salvos"))
        self.saved = QComboBox()
        self.saved.setMinimumContentsLength(16)
        self.saved.activated.connect(self._load_saved)
        top.addWidget(self.saved, 1)
        save = QPushButton("Salvar")
        save.clicked.connect(self._save)
        top.addWidget(save)
        delete = QPushButton("Excluir")
        delete.clicked.connect(self._delete_saved)
        top.addWidget(delete)
        layout.addLayout(top)
        layout.addWidget(QLabel("Classe (qualquer uma das marcadas; nenhuma = todas)"))
        self.classes = QListWidget()
        self.classes.setMaximumHeight(120)
        for key in find.CLASS_LABELS:
            item = QListWidgetItem(find.class_label(key))
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.classes.addItem(item)
        layout.addWidget(self.classes)
        layout.addWidget(QLabel("Critérios (todos valem)"))
        self.rows_box = QVBoxLayout()
        self.rows: list[_Row] = []
        layout.addLayout(self.rows_box)
        add = QPushButton("+ Critério")
        add.clicked.connect(lambda: self.add_row())
        layout.addWidget(add, 0, Qt.AlignLeft)
        where = QHBoxLayout()
        self.here = QRadioButton("Pavimento atual")
        self.here.setChecked(True)
        self.everywhere = QRadioButton("Todos os pavimentos")
        self.hidden = QCheckBox("Incluir ocultos e travados")
        for w in (self.here, self.everywhere, self.hidden):
            where.addWidget(w)
        where.addStretch(1)
        layout.addLayout(where)
        buttons = QHBoxLayout()
        for text, mode in (("Pegar da seleção", "pick"), ("Selecionar", "replace"),
                           ("Somar à seleção", "add"), ("Tirar da seleção", "remove")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, m=mode: self._pick() if m == "pick"
                              else self.select(m))
            buttons.addWidget(b)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return page

    def add_row(self, row: dict | None = None) -> _Row:
        widget = _Row(self, row)
        self.rows.append(widget)
        self.rows_box.addWidget(widget)
        return widget

    def remove_row(self, widget: _Row) -> None:
        self.rows.remove(widget)
        widget.setParent(None)
        widget.deleteLater()

    def criteria(self) -> dict:
        classes = [self.classes.item(i).data(Qt.UserRole) for i in range(self.classes.count())
                   if self.classes.item(i).checkState() == Qt.Checked]
        return {"classes": classes, "rows": [r.to_dict() for r in self.rows],
                "scope": "all" if self.everywhere.isChecked() else "storey",
                "include_hidden": self.hidden.isChecked()}

    def load(self, criteria: dict) -> None:
        wanted = set(criteria.get("classes") or ())
        for i in range(self.classes.count()):
            item = self.classes.item(i)
            item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in wanted
                               else Qt.Unchecked)
        for widget in list(self.rows):
            self.remove_row(widget)
        for row in criteria.get("rows") or ():
            self.add_row(row)
        (self.everywhere if criteria.get("scope") == "all" else self.here).setChecked(True)
        self.hidden.setChecked(bool(criteria.get("include_hidden")))

    def run_find(self) -> list[str] | None:
        session = self.session
        try:
            self.found = find.find(session.doc, self.criteria(), session.storey)
        except OpError as e:
            self.status.setText(str(e))
            return None
        self.status.setText(find.summary(session.doc, self.found) if self.found
                            else "nada encontrado")
        return self.found

    def select(self, mode: str) -> None:
        """Selecionar (troca), somar ou tirar da seleção os achados."""
        found = self.run_find()
        if found is None:
            return
        session = self.session
        if mode == "replace":
            session.select(found)
        elif mode == "add":
            session.select(set(found) - session.selection, add=True)
        else:
            session.select(session.selection - set(found))

    def _pick(self) -> None:
        """Critérios a partir do elemento selecionado: classe e tipo (§3.1)."""
        session = self.session
        if len(session.selection) != 1:
            self.status.setText("selecione um elemento para pegar os critérios dele")
            return
        element = session.doc.get(next(iter(session.selection)))
        criteria = {"classes": [find.class_key(element)], "rows": [],
                    "scope": "all" if self.everywhere.isChecked() else "storey"}
        type_name = find.value(session.doc, element, {"field": "type"})
        if type_name:
            criteria["rows"].append({"field": "type", "op": "is", "value": type_name})
        self.load(criteria)
        self.run_find()

    def refresh_saved(self) -> None:
        self.saved.clear()
        self.saved.addItem("(nenhum)", None)
        for item in find.saved(self.session.doc):
            self.saved.addItem(item["name"], item["criteria"])

    def _load_saved(self, index: int) -> None:
        criteria = self.saved.itemData(index)
        if criteria:
            self.load(criteria)
            self.run_find()

    def _save(self) -> None:
        name, ok = QInputDialog.getText(self, "Salvar critérios", "Nome:",
                                        text=self.saved.currentText()
                                        if self.saved.currentData() else "")
        if ok:
            self.save_as(name)

    def save_as(self, name: str) -> None:
        session = self.session
        session.run(lambda: find.save_criteria(session.doc, name, self.criteria()))
        self.refresh_saved()
        self.saved.setCurrentIndex(self.saved.findText(name.strip()))

    def _delete_saved(self) -> None:
        name = self.saved.currentText() if self.saved.currentData() else None
        if name:
            session = self.session
            session.run(lambda: find.delete_criteria(session.doc, name))
            self.refresh_saved()

    # --- Substituir -------------------------------------------------------------------

    WHATS = (("text", "Texto das anotações"), ("name", "Nome"), ("code", "Código"),
             ("property", "Propriedade"), ("type", "Tipo"), ("layer", "Camada"),
             ("situation", "Situação"), ("style", "Estilo de anotação"))

    def _replace_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.target = QComboBox()
        self.target.addItem("Elementos achados (Localizar)", "found")
        self.target.addItem("Seleção atual", "selection")
        form.addRow("Agir sobre", self.target)
        self.what = QComboBox()
        for key, label in self.WHATS:
            self.what.addItem(label, key)
        form.addRow("Trocar", self.what)
        layout.addLayout(form)
        self.stack = QStackedWidget()
        self.pages = {}
        text_page = self._page_text()  # Texto, Nome e Código: procurar / trocar por
        self.stack.addWidget(text_page)
        for key, _ in self.WHATS:
            if key in ("text", "name", "code"):
                self.pages[key] = text_page
                continue
            self.pages[key] = getattr(self, f"_page_{key}")()
            self.stack.addWidget(self.pages[key])
        self.what.currentIndexChanged.connect(
            lambda i: self.stack.setCurrentWidget(self.pages[self.what.itemData(i)]))
        layout.addWidget(self.stack)
        self.preview = QListWidget()
        layout.addWidget(self.preview, 1)
        buttons = QHBoxLayout()
        show = QPushButton("Mostrar ocorrências")
        show.clicked.connect(self.show_occurrences)
        apply = QPushButton("Substituir")
        apply.clicked.connect(self.replace)
        buttons.addStretch(1)
        buttons.addWidget(show)
        buttons.addWidget(apply)
        layout.addLayout(buttons)
        return page

    def _page_text(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.find_text = QLineEdit()
        self.new_text = QLineEdit()
        self.case = QCheckBox("Maiúsculas e minúsculas")
        self.whole = QCheckBox("Palavra inteira")
        form.addRow("Procurar", self.find_text)
        form.addRow("Trocar por", self.new_text)
        form.addRow(self.case)
        form.addRow(self.whole)
        return page

    def _page_property(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.prop_name = QComboBox()
        self.prop_name.setEditable(True)
        self.prop_name.lineEdit().setPlaceholderText("Pset.Propriedade")
        for pset, prop in find.known_properties(self.session.doc):
            self.prop_name.addItem(f"{pset}.{prop}")
        self.prop_value = QLineEdit()
        self.prop_value.setPlaceholderText("novo valor (sim/não, número ou texto)")
        form.addRow("Propriedade", self.prop_name)
        form.addRow("Novo valor", self.prop_value)
        return page

    def _page_type(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.type_combo = QComboBox()
        doc = self.session.doc
        for t in sorted(doc.ifc.by_type("IfcTypeObject"), key=lambda t: (t.is_a(), t.Name or "")):
            if t.Name:
                self.type_combo.addItem(f"{t.Name} ({t.is_a()})", t.GlobalId)
        form.addRow("Novo tipo", self.type_combo)
        form.addRow(QLabel("Só troca entre elementos da mesma classe do tipo."))
        return page

    def _page_layer(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.layer_combo = QComboBox()
        doc = self.session.doc
        if display_layers.read_config(doc) is not None:
            for text, value in display_layers.choices(doc):
                self.layer_combo.addItem(text, value)
        form.addRow("Nova camada", self.layer_combo)
        return page

    def _page_situation(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.situation_combo = QComboBox()
        for code, text, _ in intervention.SITUATIONS:
            self.situation_combo.addItem(text, code)
        form.addRow("Nova situação", self.situation_combo)
        return page

    def _page_style(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        from PySide6.QtGui import QFontDatabase

        from brasbim.ui.selection_options import FIRST_FONTS

        self.style_font = QComboBox()
        self.style_font.addItem("(não mudar)", "keep")
        self.style_font.addItem("Padrão", None)
        for name in [*FIRST_FONTS, *sorted(set(QFontDatabase.families()) - set(FIRST_FONTS))]:
            self.style_font.addItem(name, name)
        self.style_size = QComboBox()
        self.style_size.addItem("(não mudar)", None)
        for v in annotation_style.SIZES:
            self.style_size.addItem(f"{fmt(v)} mm", v)
        from brasbim.core import pens
        from brasbim.ui.selection_options import pen_combo

        table = pens.resolve(self.session.doc)
        # Penas da tabela (spec/ui 57); "(não mudar)" deixa como está.
        self.style_text_pen = pen_combo(table, None, lambda v: None, "Pena do texto",
                                        empty="(não mudar)")
        self.style_pen = pen_combo(table, None, lambda v: None, "Pena da linha",
                                   empty="(não mudar)")
        form.addRow("Fonte", self.style_font)
        form.addRow("Altura", self.style_size)
        form.addRow("Pena do texto", self.style_text_pen)
        form.addRow("Pena da linha", self.style_pen)
        return page

    def targets(self) -> list[str]:
        session = self.session
        if self.target.currentData() == "selection":
            return sorted(session.selection)
        found = self.run_find()
        return list(found or [])

    def _editable(self, gids) -> tuple[list, int]:
        """Elementos que podem mudar; travados ficam de fora (§3.2)."""
        doc = self.session.doc
        out, skipped = [], 0
        for g in gids:
            e = doc.find(g)
            if e is None:
                continue
            if edit_state.is_locked(doc, e):
                skipped += 1
                continue
            out.append(e)
        return out, skipped

    def show_occurrences(self) -> None:
        self.preview.clear()
        what = self.what.currentData()
        if what not in ("text", "name", "code"):
            return
        try:
            found = find.occurrences(self.session.doc, self.targets(), self.find_text.text(),
                                     self.case.isChecked(), self.whole.isChecked(), (what,))
        except OpError as e:
            self.status.setText(str(e))
            return
        for _gid, _key, _before, marked in found:
            self.preview.addItem(marked.replace("\n", " / "))
        self.status.setText(f"{len(found)} ocorrências")

    def _value(self, text: str):
        text = text.strip()
        if text.casefold() in ("sim", "verdadeiro", "true"):
            return True
        if text.casefold() in ("não", "nao", "falso", "false"):
            return False
        try:
            return parse_number(text)
        except ValueError:
            return text

    def replace(self) -> None:
        session = self.session
        doc = session.doc
        elements, skipped = self._editable(self.targets())
        if not elements:
            self.status.setText("nenhum elemento para trocar")
            return
        what = self.what.currentData()
        gids = [e.GlobalId for e in elements]
        try:
            if what in ("text", "name", "code"):
                def build():
                    return find.replace_text(doc, gids, self.find_text.text(),
                                             self.new_text.text(), self.case.isChecked(),
                                             self.whole.isChecked(), (what,))
            elif what == "property":
                pset, _, prop = self.prop_name.currentText().strip().rpartition(".")
                if not pset or not prop:
                    raise OpError("escreva a propriedade como Pset.Propriedade")
                value = self._value(self.prop_value.text())

                def build():
                    return find.set_fields(doc, elements, property=(pset, prop, value))
            elif what == "style":
                fields = {}
                if self.style_font.currentData() != "keep":
                    fields["font"] = self.style_font.currentData()
                for key, widget in (("size", self.style_size),
                                    ("text_pen", self.style_text_pen),
                                    ("pen", self.style_pen)):
                    if widget.currentData() is not None:
                        fields[key] = widget.currentData()
                if not fields:
                    raise OpError("escolha o que muda no estilo")

                def build():
                    return find.set_fields(doc, elements, style=fields)
            else:
                combo = {"type": self.type_combo, "layer": self.layer_combo,
                         "situation": self.situation_combo}[what]

                def build():
                    return find.set_fields(doc, elements, **{what: combo.currentData()})
        except OpError as e:
            self.status.setText(str(e))
            return
        before = len(session.history.undo_stack)
        session.run(build)
        done = len(session.history.undo_stack) > before
        text = "trocado" if done else "nada trocado"
        if skipped:
            text += f"; {skipped} travados ficaram de fora"
        self.status.setText(text)
        self.show_occurrences()
