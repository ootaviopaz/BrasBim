# SPDX-License-Identifier: GPL-3.0-or-later
"""Atalhos de teclado configuráveis (spec/ui 58)."""

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from brasbim.ui import shortcuts
from brasbim.ui.main_window import _settings


def _action(window, key):
    return next(e.action for e in shortcuts.entries(window) if e.key == key)


def test_at01_lista_tem_menus_e_ferramentas_com_o_padrao(window):
    found = {e.key: e for e in shortcuts.entries(window)}
    assert "menu:Editar/Desfazer" in found and "tool:wall" in found
    assert "menu:Preferências/Atalhos de teclado" in found
    base = shortcuts.defaults(list(found.values()))
    assert base["menu:Editar/Desfazer"] == ["Ctrl+Z"]
    assert base["menu:Editar/Refazer"] == ["Ctrl+Y", "Ctrl+Shift+Z"]
    assert base["tool:wall"] == []


def test_at02_atalho_de_ferramenta_ativa_a_ferramenta(window):
    window.save_shortcuts({"tool:wall": ["Ctrl+Alt+W"]})
    action = _action(window, "tool:wall")
    assert action.shortcut().toString() == "Ctrl+Alt+W"
    action.trigger()
    assert window.toolbox.active.name == "wall"
    assert shortcuts.load(_settings()) == {"tool:wall": ["Ctrl+Alt+W"]}
    window.save_shortcuts({})  # não deixa a troca para os outros testes


def test_at03_trocar_tira_de_quem_tinha_e_restaurar_volta(window):
    window.edit_shortcuts()
    dialog = window.shortcuts_dialog
    keys = [e.key for e in dialog.entries]
    dialog.table.setCurrentCell(keys.index("tool:wall"), 0)
    assert dialog.assign("tool:wall", QKeySequence("Ctrl+K"))
    assert dialog.values["menu:Editar/Paleta de comandos"] == []
    assert "Paleta de comandos" in dialog.note.text()
    assert dialog.changes() == {"tool:wall": ["Ctrl+K"], "menu:Editar/Paleta de comandos": []}
    window.save_shortcuts(dialog.changes())
    assert _action(window, "menu:Editar/Paleta de comandos").shortcuts() == []
    # ao abrir de novo, "Voltar ao padrão" na paleta tira o Ctrl+K da parede
    window.edit_shortcuts()
    dialog = window.shortcuts_dialog
    keys = [e.key for e in dialog.entries]
    dialog.table.setCurrentCell(keys.index("menu:Editar/Paleta de comandos"), 0)
    dialog.default_current()
    assert dialog.values["menu:Editar/Paleta de comandos"] == ["Ctrl+K"]
    assert dialog.values["tool:wall"] == []
    dialog.restore_defaults()
    assert dialog.changes() == {}
    window.save_shortcuts(dialog.changes())
    assert _action(window, "menu:Editar/Paleta de comandos").shortcut().toString() == "Ctrl+K"


@pytest.mark.parametrize("text", ["Esc", "Return", "Space", "5", "Left", "Ctrl+K, Ctrl+L"])
def test_at04_teclas_das_ferramentas_recusadas(text):
    assert shortcuts.problem(QKeySequence(text)) is not None


@pytest.mark.parametrize("text", ["W", "Shift+W", "Ctrl+5", "F2", "Ctrl+Alt+P", "Del"])
def test_at05_teclas_aceitas(text):
    assert shortcuts.problem(QKeySequence(text)) is None


def test_at06_busca_e_recusa_na_janela(window):
    window.edit_shortcuts()
    dialog = window.shortcuts_dialog
    dialog.search.setText("desfaz")
    visible = [e.key for r, e in enumerate(dialog.entries) if not dialog.table.isRowHidden(r)]
    assert visible == ["menu:Editar/Desfazer"]
    dialog.search.setText("ctrl+z")  # também pelo atalho
    assert "menu:Editar/Desfazer" in [e.key for r, e in enumerate(dialog.entries)
                                      if not dialog.table.isRowHidden(r)]
    assert not dialog.assign("tool:wall", QKeySequence("Esc"))
    assert dialog.values["tool:wall"] == []
    dialog.close()
    QApplication.processEvents()


def test_at07_gravado_vale_ao_abrir(window, app, tmp_path):
    from brasbim.ui import main_window as mw
    from brasbim.ui.session import Session

    shortcuts.save(_settings(), {"menu:Arquivo/Salvar": ["F2"]})
    other = mw.MainWindow(Session(journal_dir=tmp_path / "d2"))
    try:
        assert _action(other, "menu:Arquivo/Salvar").shortcut().toString() == "F2"
    finally:
        shortcuts.save(_settings(), {})
        other.session.modified = False
        other.close()


def test_at08_ok_e_cancelar_pela_janela_de_verdade(window, monkeypatch):
    """O caminho do menu, com a janela aberta como para o usuário (o erro de 24/11:
    ``dialog.Accepted`` não existe no PySide6)."""
    from PySide6.QtWidgets import QDialog

    def fake_exec(answer):
        def run(dialog):
            dialog.assign("tool:wall", QKeySequence("Ctrl+Alt+W"))
            return answer
        return run

    window.quiet_dialogs = False
    try:
        monkeypatch.setattr(shortcuts.ShortcutsDialog, "exec", fake_exec(QDialog.Rejected))
        assert window.edit_shortcuts() is False  # Cancelar: nada muda
        assert _action(window, "tool:wall").shortcuts() == []
        monkeypatch.setattr(shortcuts.ShortcutsDialog, "exec", fake_exec(QDialog.Accepted))
        assert window.edit_shortcuts() is True
        assert _action(window, "tool:wall").shortcut().toString() == "Ctrl+Alt+W"
    finally:
        window.quiet_dialogs = True
        window.save_shortcuts({})
