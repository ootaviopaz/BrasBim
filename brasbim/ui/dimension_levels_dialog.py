# SPDX-License-Identifier: GPL-3.0-or-later
"""Projeto > Cotar pavimento (``spec/ui/59-cotas-em-niveis.md`` §4): os níveis e os lados
das cotas em níveis, para quem não usa o Assistente."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

LEVEL_TEXTS = (("openings", "Aberturas (cantos e vãos de portas e janelas)"),
               ("structure", "Estrutura (faces dos pilares e das paredes internas)"),
               ("total", "Total (de ponta a ponta)"),
               ("rooms", "Cômodos (largura e profundidade de cada ambiente)"))
SIDE_TEXTS = (("bottom", "Abaixo"), ("top", "Acima"), ("left", "À esquerda"),
              ("right", "À direita"))


class DimensionLevelsDialog(QDialog):
    def __init__(self, parent, storey_name: str):
        super().__init__(parent)
        self.setWindowTitle("Cotar pavimento")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Cotas do pavimento <b>{storey_name}</b>, em linhas "
                                "paralelas: aberturas perto do desenho, estrutura no "
                                "meio e total por fora."))
        self.levels = self._group(layout, "Níveis", LEVEL_TEXTS,
                                  {"openings", "structure", "total"})
        self.sides = self._group(layout, "Lados da planta", SIDE_TEXTS,
                                 {k for k, _ in SIDE_TEXTS})
        note = QLabel("Refazer troca as cotas automáticas anteriores; as que você mexeu "
                      "(texto, estilo, posição do número) ficam.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Cotar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        for box in (*self.levels.values(), *self.sides.values()):
            box.toggled.connect(self._refresh)
        self._refresh()

    def _group(self, layout, title, items, checked) -> dict[str, QCheckBox]:
        group = QGroupBox(title)
        column = QVBoxLayout(group)
        boxes = {}
        for key, text in items:
            box = QCheckBox(text)
            box.setChecked(key in checked)
            column.addWidget(box)
            boxes[key] = box
        layout.addWidget(group)
        return boxes

    def _refresh(self) -> None:
        levels = self.chosen_levels()
        outer = set(levels) - {"rooms"}
        self.ok_button.setEnabled(bool(levels) and (not outer or bool(self.chosen_sides())))
        for box in self.sides.values():
            box.setEnabled(bool(outer))

    def chosen_levels(self) -> list[str]:
        return [k for k, box in self.levels.items() if box.isChecked()]

    def chosen_sides(self) -> list[str]:
        return [k for k, box in self.sides.items() if box.isChecked()]
