from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import *
from src.pal_utils import convert_palette, put_palette_strings
from src.twobpp import gfx_2_qimage

class MetatileEditWindow(QMainWindow):
    class TileSelect(QGraphicsScene):
        changed = Signal(int)

        def __init__(self, gfx, pals, parent=None):
            super().__init__(0, 0, 128, 128, parent)
            self.gfx = gfx
            self.pals = pals
            self.tiles_image = gfx_2_qimage(gfx, convert_palette(put_palette_strings(pals[0]), 'src/palette.pal', transparent=False))

            self.selected_tile = 0
            self.selected_tile_rect = QGraphicsRectItem(0, 0, 8, 8)
            pen = QPen(0x00FF00)
            pen.setJoinStyle(Qt.MiterJoin)
            self.selected_tile_rect.setPen(pen)
            self.addItem(self.selected_tile_rect)

        def drawBackground(self, painter: QPainter, rect):
            painter.drawImage(0, 0, self.tiles_image)

        def mousePressEvent(self, event):
            super().mousePressEvent(event)
            x = int(event.scenePos().x())
            y = int(event.scenePos().y())
            self.selected_tile = int(x//8+y//8*0x10)
            self.selected_tile_rect.setPos(x//8*8, y//8*8)

            self.changed.emit(self.selected_tile)

        @Slot(int)
        def palette_changed(self, pal_idx):
            self.area_changed(self.gfx, self.pals, pal_idx)

        def area_changed(self, gfx, pals, pal_idx=0):
            self.tiles_image = gfx_2_qimage(gfx, convert_palette(put_palette_strings(pals[0]), 'src/palette.pal', transparent=False), pal_per_tile=[pal_idx]*0x100)
            self.update(self.sceneRect())

    class TileSelectView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)
            self.setScene(scene)
            self.setFixedSize(128*2, 128*2)
            self.scale(2, 2)
            self.setFrameStyle(QFrame.NoFrame)

    class MetatileEdit(QGraphicsScene):
        edited = Signal(int, int)

        def __init__(self, gfx, pals, metatile_data, parent=None):
            super().__init__(0, 0, 256, 256, parent)

            self.gfx = gfx
            self.pals = pals
            self.area_changed(gfx, pals, metatile_data)

            self.selected_tile = 0

            self.show_tile_idxs = False
            self.highlight_same_tiles = False

        def drawBackground(self, painter: QPainter, rect):
            for row in range(0x10):
                for col in range(0x10):
                    mt_idx = col+row*0x10
                    painter.drawImage(col*0x10, row*0x10, self.tile_images[self.metatile_data[mt_idx*4]])
                    painter.drawImage(col*0x10+8, row*0x10, self.tile_images[self.metatile_data[mt_idx*4+1]])
                    painter.drawImage(col*0x10, row*0x10+8, self.tile_images[self.metatile_data[mt_idx*4+2]])
                    painter.drawImage(col*0x10+8, row*0x10+8, self.tile_images[self.metatile_data[mt_idx*4+3]])

            pen = QPen(0x00FF00)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            if self.show_tile_idxs:
                painter.setFont(QFont('monospace', 4, QFont.Bold))
                for row in range(0x10):
                    for col in range(0x10):
                        mt_idx = col+row*0x10
                        painter.drawText(col*0x10+1, row*0x10+6, f'{self.metatile_data[mt_idx*4]:02X}')
                        painter.drawText(col*0x10+8+1, row*0x10+6, f'{self.metatile_data[mt_idx*4+1]:02X}')
                        painter.drawText(col*0x10+1, row*0x10+6+8, f'{self.metatile_data[mt_idx*4+2]:02X}')
                        painter.drawText(col*0x10+8+1, row*0x10+6+8, f'{self.metatile_data[mt_idx*4+3]:02X}')
            if self.highlight_same_tiles:
                # workaround for Qt bug
                brush = QBrush(0x00FF00)
                painter.setBrush(brush)
                pen.setStyle(Qt.NoPen)
                painter.setPen(pen)
                painter.setOpacity(0.5)
                for row in range(0x10):
                    for col in range(0x10):
                        mt_idx = col+row*0x10
                        if self.metatile_data[mt_idx*4] == self.selected_tile:
                            painter.drawRect(col*0x10, row*0x10, 8, 8)
                        if self.metatile_data[mt_idx*4+1] == self.selected_tile:
                            painter.drawRect(col*0x10+8, row*0x10, 8, 8)
                        if self.metatile_data[mt_idx*4+2] == self.selected_tile:
                            painter.drawRect(col*0x10, row*0x10+8, 8, 8)
                        if self.metatile_data[mt_idx*4+3] == self.selected_tile:
                            painter.drawRect(col*0x10+8, row*0x10+8, 8, 8)
                brush.setStyle(Qt.NoBrush)
                painter.setBrush(brush)
                pen.setStyle(Qt.SolidLine)
                painter.setPen(pen)
                painter.setOpacity(1.0)
                for row in range(0x10):
                    for col in range(0x10):
                        mt_idx = col+row*0x10
                        if self.metatile_data[mt_idx*4] == self.selected_tile:
                            painter.drawRect(col*0x10, row*0x10, 8, 8)
                        if self.metatile_data[mt_idx*4+1] == self.selected_tile:
                            painter.drawRect(col*0x10+8, row*0x10, 8, 8)
                        if self.metatile_data[mt_idx*4+2] == self.selected_tile:
                            painter.drawRect(col*0x10, row*0x10+8, 8, 8)
                        if self.metatile_data[mt_idx*4+3] == self.selected_tile:
                            painter.drawRect(col*0x10+8, row*0x10+8, 8, 8)

        def mousePressEvent(self, event):
            super().mousePressEvent(event)

            if event.button() == Qt.LeftButton:
                x = int(event.scenePos().x())
                y = int(event.scenePos().y())
                target_mt = int(x//0x10+y//0x10*0x10)
                if target_mt != 0xFF:
                    target_corner = int((x//8)%2+((y//8)%2)*2)
                    self.metatile_data[target_mt*4+target_corner] = self.selected_tile
                    self.update(x//8*8, y//8*8, 8, 8)

                    self.edited.emit(target_mt, target_corner)

        @Slot(int)
        def tile_select_changed(self, tile):
            self.selected_tile = tile
            if self.highlight_same_tiles:
                self.update(self.sceneRect())

        @Slot(int)
        def palette_changed(self, pal_idx):
            self.tile_images = []
            pal = convert_palette(put_palette_strings(self.pals[0]), 'src/palette.pal', transparent=False)
            for i in range(0x100):
                self.tile_images.append(gfx_2_qimage(self.gfx, pal, width=1, idxs=[i], pal_per_tile=[pal_idx]))
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_tile_idxs_toggled(self, state):
            self.show_tile_idxs = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def highlight_same_tiles_toggled(self, state):
            self.highlight_same_tiles = state == Qt.Checked
            self.update(self.sceneRect())

        def area_changed(self, gfx, pals, metatile_data):
            self.metatile_data = metatile_data

            self.tile_images = []
            pal = convert_palette(put_palette_strings(pals[0]), 'src/palette.pal', transparent=False)
            for i in range(0x100):
                self.tile_images.append(gfx_2_qimage(gfx, pal, width=1, idxs=[i]))
            self.update(self.sceneRect())

    class MetatileEditView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)
            self.setScene(scene)
            self.setFixedSize(256*2, 256*2)
            self.scale(2, 2)
            self.setFrameStyle(QFrame.NoFrame)

    def __init__(self, gfx, pals, metatile_data, parent=None):
        super().__init__(parent)

        # Tile column
        self.tile_select = self.TileSelect(gfx, pals)
        self.tile_select_view = self.TileSelectView(self.tile_select)
        self.pal_select = QSpinBox(minimum=0, maximum=3)
        self.tile_select_form = QFormLayout()
        self.tile_select_form.addRow('Palette', self.pal_select)
        self.tile_select_layout = QVBoxLayout()
        self.tile_select_layout.addWidget(self.tile_select_view)
        self.tile_select_layout.addLayout(self.tile_select_form)

        # Metatile column
        self.mt_edit = self.MetatileEdit(gfx, pals, metatile_data)
        self.mt_edit_view = self.MetatileEditView(self.mt_edit)
        self.show_tile_idxs_toggle = QCheckBox()
        self.highlight_same_tiles_toggle = QCheckBox()
        self.mt_edit_form = QFormLayout()
        self.mt_edit_form.addRow('Show tile indices', self.show_tile_idxs_toggle)
        self.mt_edit_form.addRow('Highlight same tiles', self.highlight_same_tiles_toggle)
        self.mt_edit_layout = QVBoxLayout()
        self.mt_edit_layout.addWidget(self.mt_edit_view)
        self.mt_edit_layout.addLayout(self.mt_edit_form)

        # Main layout
        self.layout = QHBoxLayout()
        self.layout.addLayout(self.tile_select_layout)
        self.layout.addLayout(self.mt_edit_layout)
        self.group_box = QGroupBox(self)
        self.group_box.setLayout(self.layout)
        self.setCentralWidget(self.group_box)

        # Slots
        self.tile_select.changed.connect(self.mt_edit.tile_select_changed)
        self.pal_select.valueChanged.connect(self.tile_select.palette_changed)
        self.pal_select.valueChanged.connect(self.mt_edit.palette_changed)
        self.show_tile_idxs_toggle.checkStateChanged.connect(self.mt_edit.show_tile_idxs_toggled)
        self.highlight_same_tiles_toggle.checkStateChanged.connect(self.mt_edit.highlight_same_tiles_toggled)

    def area_changed(self, gfx, pal, metatile_data):
        self.pal_select.setValue(0)

        self.tile_select.area_changed(gfx, pal)
        self.mt_edit.area_changed(gfx, pal, metatile_data)
