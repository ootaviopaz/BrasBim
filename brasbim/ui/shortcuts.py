# SPDX-License-Identifier: GPL-3.0-or-later
"""Atalhos de teclado configuráveis (``spec/ui/58-atalhos-de-teclado.md``).

Todo item dos menus e toda ferramenta pode ter atalhos. O padrão é o que o programa
define; o usuário troca em Preferências > Atalhos de teclado, e só as diferenças ficam
gravadas nas preferências (``atalhos/teclado``, JSON ``{comando: [atalhos]}``; lista vazia
= sem atalho).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from brasbim.ui import theme
from brasbim.ui.command_search import normalize

SHORTCUTS_KEY = "atalhos/teclado"
_DEFAULT = "brasbim_atalho_padrao"  # propriedade da QAction com o padrão do programa
# Teclas que as ferramentas usam sozinhas (spec/ui 07 §2.2, 24): Esc, Enter, Tab, espaço,
# números, setas, Home, Delete e Backspace não podem virar atalho sem Ctrl, Alt ou Shift
# (Delete já é o padrão de Excluir e continua podendo voltar a ele).
_RESERVED = {Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Backtab,
             Qt.Key_Space, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Home,
             Qt.Key_Backspace}
_TEXT_KEYS = set(range(Qt.Key_0, Qt.Key_9 + 1)) | {
    Qt.Key_Period, Qt.Key_Comma, Qt.Key_Minus, Qt.Key_Plus, Qt.Key_Slash, Qt.Key_Asterisk,
    Qt.Key_At, Qt.Key_Less, Qt.Key_Greater}
_MODIFIERS = Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier | Qt.MetaModifier


@dataclass
class Entry:
    key: str  # "menu:Editar/Desfazer" ou "tool:wall" (as mesmas chaves dos apelidos)
    label: str
    where: str
    action: QAction


def text_of(sequence: QKeySequence) -> str:
    return sequence.toString(QKeySequence.PortableText)


def shown(texts) -> str:
    """Atalhos como aparecem na tela (Ctrl+Shift+F; no Mac, os símbolos do sistema)."""
    return "; ".join(QKeySequence(t).toString(QKeySequence.NativeText) for t in texts)


def problem(sequence: QKeySequence) -> str | None:
    """Por que o atalho não pode ser usado, ou None."""
    if sequence.isEmpty():
        return None
    if sequence.count() > 1:
        return "use uma tecla só (com ou sem Ctrl, Alt, Shift)"
    combo = sequence[0]
    key, mods = combo.key(), combo.keyboardModifiers() & _MODIFIERS
    if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_unknown):
        return "aperte também uma tecla além de Ctrl, Alt ou Shift"
    plain = not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
    if plain and key in _RESERVED:
        return "essa tecla é das ferramentas (Esc, Enter, Tab, espaço, setas); some Ctrl ou Alt"
    if plain and key in _TEXT_KEYS:
        return "números e sinais são das medidas digitadas; some Ctrl ou Alt"
    return None


# --- comandos ---------------------------------------------------------------------------


def _menu_entries(menu_bar) -> list[Entry]:
    out = []

    def walk(menu, path):
        for action in menu.actions():
            if action.isSeparator() or not action.text():
                continue
            text = action.text().replace("&", "")
            if action.menu() is not None:
                walk(action.menu(), [*path, text])
                continue
            key = "menu:" + "/".join([*path, text])
            out.append(Entry(key, text, " › ".join(path), action))

    for action in menu_bar.actions():
        if action.menu() is not None:
            walk(action.menu(), [action.text().replace("&", "")])
    return out


def tool_actions(window) -> dict[str, QAction]:
    """Uma ação (sem botão) por ferramenta, presa à janela, para o atalho dela."""
    found = getattr(window, "tool_shortcut_actions", None)
    if found is None:
        found = window.tool_shortcut_actions = {}
        for command in window.tool_commands():
            name = command.key[len("tool:"):]
            if name in found:
                continue
            action = QAction(command.label, window)
            action.setShortcutContext(Qt.WindowShortcut)
            action.triggered.connect(lambda _=False, n=name: window.activate_tool(n))
            window.addAction(action)
            found[name] = action
    return found


def entries(window) -> list[Entry]:
    """Todos os comandos que podem ter atalho: os dos menus e as ferramentas."""
    out, seen = [], set()
    for entry in _menu_entries(window.menuBar()):
        if entry.key not in seen:
            seen.add(entry.key)
            out.append(entry)
    actions = tool_actions(window)
    for command in window.tool_commands():
        if command.key not in seen:
            seen.add(command.key)
            name = command.key[len("tool:"):]
            out.append(Entry(command.key, command.label, f"Ferramenta · {command.where}",
                             actions[name]))
    for entry in out:  # o padrão é o que o programa pôs antes de qualquer troca
        if entry.action.property(_DEFAULT) is None:
            entry.action.setProperty(_DEFAULT, [text_of(s) for s in entry.action.shortcuts()])
    return out


def defaults(entries_: list[Entry]) -> dict[str, list[str]]:
    return {e.key: list(e.action.property(_DEFAULT) or []) for e in entries_}


def current(entries_: list[Entry]) -> dict[str, list[str]]:
    return {e.key: [text_of(s) for s in e.action.shortcuts()] for e in entries_}


def load(settings) -> dict[str, list[str]]:
    """Diferenças gravadas ({comando: [atalhos]})."""
    try:
        changes = json.loads(settings.value(SHORTCUTS_KEY, "") or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(changes, dict):
        return {}
    return {str(k): [str(s) for s in v] for k, v in changes.items() if isinstance(v, list)}


def diff(values: dict[str, list[str]], base: dict[str, list[str]]) -> dict[str, list[str]]:
    return {k: v for k, v in values.items() if v != base.get(k, [])}


def save(settings, changes: dict[str, list[str]]) -> None:
    settings.setValue(SHORTCUTS_KEY, json.dumps(changes, ensure_ascii=False))


def apply(window, changes: dict[str, list[str]]) -> None:
    """Põe em cada comando o padrão com as ``changes`` por cima. Um atalho trocado sai do
    comando que o tinha por padrão (nunca dois comandos com o mesmo atalho)."""
    all_entries = entries(window)
    values = defaults(all_entries)
    taken = {s for k, v in changes.items() if k in values for s in v}
    for key in values:
        if key in changes:
            values[key] = list(changes[key])
        else:
            values[key] = [s for s in values[key] if s not in taken]
    for entry in all_entries:
        entry.action.setShortcuts([QKeySequence(s) for s in values[entry.key]])


def conflicts(values: dict[str, list[str]]) -> dict[str, list[str]]:
    """Atalho → comandos que o usam, só os repetidos."""
    users: dict[str, list[str]] = {}
    for key, texts in values.items():
        for text in texts:
            users.setdefault(text, []).append(key)
    return {s: keys for s, keys in users.items() if len(keys) > 1}


# --- janela -----------------------------------------------------------------------------


class ShortcutsDialog(QDialog):
    """Preferências > Atalhos de teclado (spec/ui 58 §3)."""

    def __init__(self, parent, entries_: list[Entry]):
        super().__init__(parent)
        self.setWindowTitle("Atalhos de teclado")
        self.resize(620, 620)
        self.entries = entries_
        self.base = defaults(entries_)
        self.values = current(entries_)
        self.labels = {e.key: e.label for e in entries_}
        layout = QVBoxLayout(self)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Buscar comando ou atalho")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)
        self.table = QTableWidget(len(entries_), 3, self)
        self.table.setHorizontalHeaderLabels(["Comando", "Onde", "Atalho"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, entry in enumerate(entries_):
            for col, text in enumerate((entry.label, entry.where, "")):
                self.table.setItem(row, col, QTableWidgetItem(text))
        self._refresh_rows()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.currentCellChanged.connect(lambda *_: self._show_current())
        layout.addWidget(self.table)
        row = QHBoxLayout()
        row.addWidget(QLabel("Atalho:"))
        self.edit = QKeySequenceEdit(self)
        self.edit.setMaximumSequenceLength(1)
        self.edit.setToolTip("Clique e aperte as teclas do atalho")
        self.edit.editingFinished.connect(self._record)
        row.addWidget(self.edit, 1)
        self.clear_button = QPushButton("Sem atalho")
        self.clear_button.clicked.connect(self.clear_current)
        row.addWidget(self.clear_button)
        self.default_button = QPushButton("Voltar ao padrão")
        self.default_button.clicked.connect(self.default_current)
        row.addWidget(self.default_button)
        layout.addLayout(row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        reset = QPushButton("Restaurar todos")
        buttons.addButton(reset, QDialogButtonBox.ResetRole)
        reset.clicked.connect(self.restore_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if entries_:
            self.table.setCurrentCell(0, 0)

    # --- estado ---

    def current_key(self) -> str | None:
        row = self.table.currentRow()
        return self.entries[row].key if 0 <= row < len(self.entries) else None

    def _refresh_rows(self) -> None:
        for row, entry in enumerate(self.entries):
            item = self.table.item(row, 2)
            texts = self.values[entry.key]
            item.setText(shown(texts))
            font = item.font()
            font.setBold(texts != self.base[entry.key])  # trocado pelo usuário
            item.setFont(font)

    def _show_current(self) -> None:
        key = self.current_key()
        texts = self.values.get(key, []) if key else []
        self.edit.blockSignals(True)
        self.edit.setKeySequence(QKeySequence(texts[0]) if texts else QKeySequence())
        self.edit.blockSignals(False)
        self.default_button.setEnabled(bool(key) and texts != self.base.get(key, []))

    def _say(self, text: str, error: bool = False) -> None:
        self.note.setStyleSheet(f"color: {theme.ERROR}" if error else "")
        self.note.setText(text)

    # --- ações ---

    def assign(self, key: str, sequence: QKeySequence) -> bool:
        """Dá o atalho ao comando (tira de quem o tinha). Devolve se foi aceito."""
        why = problem(sequence)
        if why:
            self._say(f"{text_of(sequence)}: {why}.", error=True)
            self._show_current()
            return False
        text = text_of(sequence)
        if not text:
            return self.set_values(key, [])
        moved = [k for k, v in self.values.items() if k != key and text in v]
        for other in moved:
            self.values[other] = [s for s in self.values[other] if s != text]
        self.values[key] = [text]
        self._refresh_rows()
        self._show_current()
        if moved:
            names = ", ".join(self.labels[k] for k in moved)
            self._say(f"{shown([text])} era de {names} e agora é de {self.labels[key]}.")
        else:
            self._say(f"{self.labels[key]}: {shown([text])}.")
        return True

    def set_values(self, key: str, texts: list[str]) -> bool:
        self.values[key] = list(texts)
        self._refresh_rows()
        self._show_current()
        self._say("")
        return True

    def _record(self) -> None:
        key = self.current_key()
        if key is not None:
            self.assign(key, self.edit.keySequence())

    def clear_current(self) -> None:
        key = self.current_key()
        if key is not None:
            self.set_values(key, [])

    def default_current(self) -> None:
        key = self.current_key()
        if key is None:
            return
        wanted = self.base[key]
        moved = [k for k, v in self.values.items()
                 if k != key and any(s in v for s in wanted)]
        for other in moved:
            self.values[other] = [s for s in self.values[other] if s not in wanted]
        self.set_values(key, wanted)
        if moved:
            names = ", ".join(self.labels[k] for k in moved)
            self._say(f"{shown(wanted)} voltou para {self.labels[key]} e saiu de {names}.")

    def restore_defaults(self) -> None:
        self.values = {k: list(v) for k, v in self.base.items()}
        self._refresh_rows()
        self._show_current()
        self._say("Todos os atalhos voltaram ao padrão.")

    def _filter(self, text: str) -> None:
        words = normalize(text).split()
        for row, entry in enumerate(self.entries):
            hay = normalize(" ".join((entry.label, entry.where,
                                      " ".join(self.values[entry.key]),
                                      shown(self.values[entry.key]))))
            self.table.setRowHidden(row, not all(w in hay for w in words))

    def changes(self) -> dict[str, list[str]]:
        """O que difere do padrão (o que vai para as preferências)."""
        return diff(self.values, self.base)
