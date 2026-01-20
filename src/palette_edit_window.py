from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import *
from src.pal_utils import convert_palette, generate_colors, put_palette_strings, palette_to_strings

class PaletteEditWindow(QMainWindow):
    class PaletteScene(QGraphicsScene):
        changed = Signal(list)

        def __init__(self, pals, parent=None):
            super().__init__(0, 0, 16, 2, parent)

            self.current_pal = 0
            self.selected_color = 0

            self.area_changed(pals)

            self.colors = generate_colors('src/palette.pal')

        def drawBackground(self, painter: QPainter, rect):
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(32):
                painter.setBrush(self.colors[self.converted_pal[i]])
                painter.drawRect(i%16, i//16, 1, 1)

            # X's
            pen = QPen(0xFF0000)
            pen.setJoinStyle(Qt.MiterJoin)
            pen.setWidthF(1/8)
            painter.setPen(pen)
            for i in range(32):
                if self.converted_pal[i] == 0x0D:
                    x = i%16
                    y = i//16
                    painter.drawLine(x, y, x+1, y+1)
                    painter.drawLine(x+1, y, x, y+1)

        def mousePressEvent(self, event):
            super().mousePressEvent(event)

            x = int(event.scenePos().x())
            y = int(event.scenePos().y())
            target_color = int(x+y*0x10)
            self.converted_pal[target_color] = self.selected_color
            self.pals[self.current_pal] = palette_to_strings(self.converted_pal)
            self.update(self.sceneRect())

            self.changed.emit(self.converted_pal)

        @Slot(int)
        def color_picker_changed(self, color):
            self.selected_color = color

        @Slot(int)
        def palette_changed(self, pal_idx):
            self.current_pal = pal_idx
            self.converted_pal = put_palette_strings(self.pals[self.current_pal], pal=[0x0D]*0x20)
            self.update(self.sceneRect())

        def area_changed(self, pals):
            self.pals = pals
            self.converted_pal = put_palette_strings(pals[0], pal=[0x0D]*0x20)
            self.update(self.sceneRect())

    class PaletteView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)

            self.setScene(scene)
            self.setFixedSize(16*32, 2*32)
            self.scale(32, 32)
            self.setFrameStyle(QFrame.NoFrame)

    class ColorPickerScene(QGraphicsScene):
        changed = Signal(int)

        def __init__(self, parent=None):
            super().__init__(0, 0, 16, 4, parent)

            self.colors = generate_colors('src/palette.pal')
            self.selected_color = 0

            self.selected_color_rect_1 = QGraphicsRectItem(0, 0, 1, 1)
            pen = QPen(0)
            pen.setJoinStyle(Qt.MiterJoin)
            pen.setWidthF(1/8)
            self.selected_color_rect_1.setPen(pen)
            self.addItem(self.selected_color_rect_1)
            
            self.selected_color_rect_2 = QGraphicsRectItem(0, 0, 1, 1)
            pen = QPen(0xFFFFFF)
            pen.setJoinStyle(Qt.MiterJoin)
            pen.setWidthF(1/16)
            self.selected_color_rect_2.setPen(pen)
            self.addItem(self.selected_color_rect_2)

        def drawBackground(self, painter: QPainter, rect):
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(0x40):
                painter.setBrush(self.colors[i])
                painter.drawRect(i%16, i//16, 1, 1)

            # X at color $0D
            pen = QPen(0xFF0000)
            pen.setJoinStyle(Qt.MiterJoin)
            pen.setWidthF(1/8)
            painter.setPen(pen)

            painter.drawLine(0xD, 0, 0xE, 1)
            painter.drawLine(0xE, 0, 0xD, 1)

        def mousePressEvent(self, event):
            super().mousePressEvent(event)

            x = int(event.scenePos().x())
            y = int(event.scenePos().y())
            self.selected_color = int(x+y*0x10)
            self.selected_color_rect_1.setPos(x, y)
            self.selected_color_rect_2.setPos(x, y)

            self.changed.emit(self.selected_color)

    class ColorPickerView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)

            self.setScene(scene)
            self.setFixedSize(16*32, 4*32)
            self.scale(32, 32)
            self.setFrameStyle(QFrame.NoFrame)

    def __init__(self, pals, parent=None):
        super().__init__(parent)

        self.pals = pals
        self.current_pal = 0

        self.pal_select = QSpinBox(minimum=0, maximum=len(pals)-1)
        self.pal_select.setDisplayIntegerBase(16)
        self.pal_select_form = QFormLayout()
        self.pal_select_form.addRow('Palette', self.pal_select)

        self.new_pal_button = QPushButton('New palette')

        self.palette_scene = self.PaletteScene(pals)
        self.palette_view = self.PaletteView(self.palette_scene)

        self.color_picker_scene = self.ColorPickerScene()
        self.color_picker_view = self.ColorPickerView(self.color_picker_scene)

        self.update_status_bar(0)

        # Layout
        self.layout = QVBoxLayout()
        self.layout.addLayout(self.pal_select_form)
        self.layout.addWidget(self.new_pal_button)
        self.layout.addWidget(self.palette_view)
        self.layout.addWidget(self.color_picker_view)
        self.group_box = QGroupBox(self)
        self.group_box.setLayout(self.layout)
        self.setCentralWidget(self.group_box)

        # Slots
        self.pal_select.valueChanged.connect(self.palette_scene.palette_changed)
        self.new_pal_button.clicked.connect(self.new_pal_button_clicked)
        self.color_picker_scene.changed.connect(self.palette_scene.color_picker_changed)
        self.color_picker_scene.changed.connect(self.update_status_bar)

    @Slot()
    def new_pal_button_clicked(self):
        self.pals.append([])
        self.pal_select.setMaximum(len(self.pals)-1)
        self.pal_select.setValue(len(self.pals)-1)

    @Slot(int)
    def update_status_bar(self, color):
        self.statusBar().showMessage(f"Color: ${color:02X}")

    def area_changed(self, pals):
        self.pals = pals
        self.pal_select.setValue(0)
        self.palette_scene.area_changed(pals)
