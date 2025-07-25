from PySide6.QtCore import Qt, Signal, Slot, QRectF, QAbstractListModel, QAbstractTableModel, QModelIndex, QMimeData
from PySide6.QtGui import QImage, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import *
from src.pal_utils import convert_palette, put_palette_strings
from src.twobpp import gfx_2_qimage
from src.obj_widgets import ObjPropsModel, ObjPropsDelegate, ObjList
import copy, base64, json

class MapEditWindow(QMainWindow):
    class RoomSelect(QGraphicsScene):
        changed = Signal(int)

        def __init__(self, gfx, pals, metatile_data, rooms_data, parent=None):
            super().__init__(parent)

            self.selected_room_rect = QGraphicsRectItem(0, 0, 0x100, 0xF0)
            pen = QPen(0x00FF00)
            pen.setJoinStyle(Qt.MiterJoin)
            self.selected_room_rect.setPen(pen)
            self.addItem(self.selected_room_rect)

            self.area_changed(gfx, pals, metatile_data, rooms_data)

            self.show_grid = False
            self.show_room_idxs = False

        def drawBackground(self, painter: QPainter, rect):
            for room_i in range(len(self.rooms_data)):
                tm = self.rooms_data[room_i]['tilemap']
                attrs = self.rooms_data[room_i]['attrs']
                for row in range(0xF):
                    for col in range(0x10):
                        painter.drawImage(col*0x10, row*0x10+room_i*0xF0, self.mt_images[attrs[col+row*0x10]][tm[col+row*0x10]])

            pen = QPen(0xFFFFFF)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            if self.show_grid:
                for room_i in range(len(self.rooms_data)):
                    painter.drawRect(0, room_i*0xF0, 0x100, 0xF0)

            if self.show_room_idxs:
                painter.setFont(QFont('monospace', 30, QFont.Bold))
                for room_i in range(len(self.rooms_data)):
                    painter.drawText(0, room_i*0xF0+0x24, f'{room_i:02X}')
                painter.drawText(0, len(self.rooms_data)*0xF0+0x24, 'FF')

        def mousePressEvent(self, event):
            super().mousePressEvent(event)
            x = int(event.scenePos().x())
            y = int(event.scenePos().y())
            self.selected_room = int(y//0xF0)
            if self.selected_room >= len(self.rooms_data):
                self.selected_room = 0xFF
            self.selected_room_rect.setPos(0, y//0xF0*0xF0)

            self.changed.emit(self.selected_room)

        @Slot(Qt.CheckState)
        def show_grid_toggled(self, state):
            self.show_grid = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_room_idxs_toggled(self, state):
            self.show_room_idxs = state == Qt.Checked
            self.update(self.sceneRect())

        def area_changed(self, gfx, pals, metatile_data, rooms_data):
            self.setSceneRect(0, 0, 0x100, 0xF0*len(rooms_data)+0xF1)

            self.gfx = gfx
            self.pals = pals
            self.metatile_data = metatile_data
            self.rooms_data = rooms_data

            # Generate metatile images
            self.mt_images = []
            pal = convert_palette(put_palette_strings(pals[0]), 'src/palette.pal', transparent=False)
            for pal_idx in range(4):
                mts_per_pal = []
                for i in range(0x100):
                    mts_per_pal.append(gfx_2_qimage(gfx, pal, width=2, idxs=metatile_data[i*4:i*4+4], pal_per_tile=[pal_idx]*4))
                self.mt_images.append(mts_per_pal)

            self.selected_room = 0
            self.selected_room_rect.setPos(0, 0)

            self.update(self.sceneRect())

        def metatile_edited(self, mt_idx):
            pal = convert_palette(put_palette_strings(self.pals[0]), 'src/palette.pal', transparent=False)
            for pal_idx in range(4):
                self.mt_images[pal_idx][mt_idx] = gfx_2_qimage(self.gfx, pal, width=2, idxs=self.metatile_data[mt_idx*4:mt_idx*4+4], pal_per_tile=[pal_idx]*4)
            self.update(self.sceneRect())

        def room_edited(self, room_idx, x, y):
            self.update(x, y+room_idx*0xF0, 0x10, 0x10)

        def new_room_added(self):
            self.setSceneRect(0, 0, 0x100, 0xF0*len(self.rooms_data)+0xF1)
            self.update(self.sceneRect())

    class RoomSelectView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)
            self.setScene(scene)
            self.setFixedWidth(0x120)
            self.scale(1, 1)
            self.setFrameStyle(QFrame.NoFrame)

    class MapEdit(QGraphicsScene):
        class GlobalObject(QGraphicsItem):
            def __init__(self, obj_data, idx, parent=None):
                super().__init__(parent)
                self.obj_data = obj_data
                self.idx = idx
                self.setPos(obj_data[1][1], obj_data[2][1]//0x100*0xF0+(obj_data[2][1]&0xFF))

            def paint(self, painter, option, widget):
                pen = QPen(0xFFFFFF)
                pen.setJoinStyle(Qt.MiterJoin)
                painter.setPen(pen)
                painter.drawLine(-0x10, 0, 0, 0)
                painter.drawLine(0, -0x10, 0, 0x10)
                painter.setFont(QFont('monospace', 10, QFont.Bold))
                painter.drawText(4, 10, str(self.obj_data[0][1]))
                painter.drawText(4, -4, f'{self.idx:02X}')

            def boundingRect(self):
                return QRectF(-0x20, -0x20, 0xC0, 0x40)

        def __init__(self, gfx, pals, metatile_data, rooms_data, global_obj_data, world_map, parent=None):
            super().__init__(0, 0, 0x100*0x20+1, 0xF0*0x20+1, parent)

            self.world_map = world_map

            self.show_grid = False
            self.show_room_idxs = False
            self.show_map_coords = False

            self.area_changed(gfx, pals, metatile_data, rooms_data, global_obj_data)

        def drawBackground(self, painter: QPainter, rect):
            for map_row in range(0x20):
                for map_col in range(0x20):
                    room_i = self.world_map[map_col+map_row*0x20]
                    if room_i < len(self.rooms_data):
                        tm = self.rooms_data[room_i]['tilemap']
                        attrs = self.rooms_data[room_i]['attrs']
                        for row in range(0xF):
                            for col in range(0x10):
                                painter.drawImage(col*0x10+map_col*0x100, row*0x10+map_row*0xF0, self.mt_images[attrs[col+row*0x10]][tm[col+row*0x10]])

            pen = QPen(0xFFFFFF)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            if self.show_grid:
                for row in range(0x20):
                    for col in range(0x20):
                        if self.world_map[col+row*0x20] < len(self.rooms_data):
                            painter.drawRect(col*0x100, row*0xF0, 0x100, 0xF0)

            if self.show_room_idxs:
                painter.setFont(QFont('monospace', 30, QFont.Bold))
                for row in range(0x20):
                    for col in range(0x20):
                        room_i = self.world_map[col+row*0x20]
                        if room_i != 0xFF:
                            painter.drawText(col*0x100, row*0xF0+0x24, f'{room_i:02X}')

            if self.show_map_coords:
                painter.setFont(QFont('monospace', 15, QFont.Bold))
                y_offset = 0x38 if self.show_room_idxs else 0x38-0x24
                for row in range(0x20):
                    for col in range(0x20):
                        room_i = self.world_map[col+row*0x20]
                        if room_i != 0xFF:
                            painter.drawText(col*0x100, row*0xF0+y_offset, f'{col:02X},{row:02X}')

        def mousePressEvent(self, event):
            super().mousePressEvent(event)

            if event.button() == Qt.LeftButton:
                x = event.scenePos().x()
                y = event.scenePos().y()
                self.world_map[int(x//0x100+y//0xF0*0x20)] = self.selected_room
                self.update(x//0x100*0x100, y//0xF0*0xF0, 0x100, 0xF0)

        @Slot(int)
        def room_select_changed(self, room_i):
            self.selected_room = room_i

        @Slot(list)
        def obj_list_changed(self, objs):
            # Update objs display
            self.clear()
            self.objs = []
            for i, obj_data in enumerate(self.global_obj_data): # instead of enumerate(objs) due to a PySide6 bug
                obj = self.GlobalObject(obj_data, i)
                self.addItem(obj)
                self.objs.append(obj)

        @Slot(int)
        def obj_data_changed(self, idx):
            obj_data = self.objs[idx].obj_data
            self.objs[idx].setPos(obj_data[1][1], obj_data[2][1]//0x100*0xF0+(obj_data[2][1]&0xFF))
            self.objs[idx].update(self.objs[idx].boundingRect())

        @Slot(Qt.CheckState)
        def show_grid_toggled(self, state):
            self.show_grid = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_room_idxs_toggled(self, state):
            self.show_room_idxs = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_map_coords_toggled(self, state):
            self.show_map_coords = state == Qt.Checked
            self.update(self.sceneRect())

        def area_changed(self, gfx, pals, metatile_data, rooms_data, global_obj_data):
            self.gfx = gfx
            self.pals = pals
            self.metatile_data = metatile_data
            self.rooms_data = rooms_data
            self.global_obj_data = global_obj_data

            # Generate metatile images
            self.mt_images = []
            pal = convert_palette(put_palette_strings(pals[0]), 'src/palette.pal', transparent=False)
            for pal_idx in range(4):
                mts_per_pal = []
                for i in range(0x100):
                    mts_per_pal.append(gfx_2_qimage(gfx, pal, width=2, idxs=metatile_data[i*4:i*4+4], pal_per_tile=[pal_idx]*4))
                self.mt_images.append(mts_per_pal)

            self.selected_room = 0
            self.update(self.sceneRect())

            # Objects display
            self.obj_list_changed(self.global_obj_data)

        def metatile_edited(self, mt_idx):
            pal = convert_palette(put_palette_strings(self.pals[0]), 'src/palette.pal', transparent=False)
            for pal_idx in range(4):
                self.mt_images[pal_idx][mt_idx] = gfx_2_qimage(self.gfx, pal, width=2, idxs=self.metatile_data[mt_idx*4:mt_idx*4+4], pal_per_tile=[pal_idx]*4)
            self.update(self.sceneRect())

        def room_edited(self):
            self.update(self.sceneRect())

    class MapEditView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)
            self.setScene(scene)
            self.scale(1, 1)
            self.setFrameStyle(QFrame.NoFrame)

    def __init__(self, gfx, pals, metatile_data, rooms_data, global_obj_data, obj_types, world_map, parent=None):
        super().__init__(parent)

        self.rooms_data = rooms_data
        self.global_obj_data = global_obj_data
        self.obj_types = obj_types

        # Room column
        self.room_select = self.RoomSelect(gfx, pals, metatile_data, self.rooms_data)
        self.room_select_view = self.RoomSelectView(self.room_select)
        self.room_select_layout = QVBoxLayout()
        self.room_select_layout.addWidget(self.room_select_view)

        # Map column
        self.map_edit = self.MapEdit(gfx, pals, metatile_data, self.rooms_data, self.global_obj_data, world_map)
        self.map_edit_view = self.MapEditView(self.map_edit)
        self.show_grid_toggle = QCheckBox()
        self.show_room_idxs_toggle = QCheckBox()
        self.show_map_coords_toggle = QCheckBox()
        self.map_edit_form = QFormLayout()
        self.map_edit_form.addRow('Show grid', self.show_grid_toggle)
        self.map_edit_form.addRow('Show room indices', self.show_room_idxs_toggle)
        self.map_edit_form.addRow('Show map coordinates', self.show_map_coords_toggle)
        self.map_edit_layout = QVBoxLayout()
        self.map_edit_layout.addWidget(self.map_edit_view)
        self.map_edit_layout.addLayout(self.map_edit_form)

        # Object column
        self.obj_list = ObjList(self.global_obj_data)
        self.obj_props_table = QTableView()
        self.obj_props_table.setItemDelegate(ObjPropsDelegate(obj_types, global_flag=True))

        self.obj_list.model.changed.connect(self.obj_list_changed)
        self.obj_list.model.changed.connect(self.map_edit.obj_list_changed)
        if len(self.global_obj_data) > 0:
            self.obj_props_model = ObjPropsModel(self.global_obj_data[0], 0, self.obj_types)
            self.obj_props_model.changed.connect(self.map_edit.obj_data_changed)
        else:
            self.obj_props_model = None
        self.obj_props_table.setModel(self.obj_props_model)

        self.obj_layout = QVBoxLayout()
        self.obj_layout.addWidget(self.obj_list)
        self.obj_layout.addWidget(self.obj_props_table)
        self.obj_group_box = QGroupBox()
        self.obj_group_box.setLayout(self.obj_layout)
        self.obj_dock = QDockWidget()
        self.obj_dock.setWidget(self.obj_group_box)
        self.obj_dock.setFeatures(QDockWidget.DockWidgetMovable)

        # Main layout
        self.layout = QHBoxLayout()
        self.layout.addLayout(self.room_select_layout)
        self.layout.addLayout(self.map_edit_layout)
        self.group_box = QGroupBox(self)
        self.group_box.setLayout(self.layout)
        self.setCentralWidget(self.group_box)

        self.addDockWidget(Qt.RightDockWidgetArea, self.obj_dock)

        # Slots
        self.room_select.changed.connect(self.map_edit.room_select_changed)

        self.show_grid_toggle.checkStateChanged.connect(self.room_select.show_grid_toggled)
        self.show_grid_toggle.checkStateChanged.connect(self.map_edit.show_grid_toggled)
        self.show_room_idxs_toggle.checkStateChanged.connect(self.room_select.show_room_idxs_toggled)
        self.show_room_idxs_toggle.checkStateChanged.connect(self.map_edit.show_room_idxs_toggled)
        self.show_map_coords_toggle.checkStateChanged.connect(self.map_edit.show_map_coords_toggled)

        self.obj_list.pressed.connect(self.obj_list_pressed)

    @Slot(list)
    def obj_list_changed(self, objs):
        if self.obj_list.currentIndex().isValid():
            idx = self.obj_list.currentIndex().row()
            self.obj_props_model = ObjPropsModel(self.global_obj_data[idx], idx, self.obj_types)
            self.obj_props_model.changed.connect(self.map_edit.obj_data_changed)
        else:
            self.obj_props_model = None
        self.obj_props_table.setModel(self.obj_props_model)

    @Slot(QModelIndex)
    def obj_list_pressed(self, index):
        self.obj_props_model = ObjPropsModel(self.global_obj_data[index.row()], index.row(), self.obj_types)
        self.obj_props_table.setModel(self.obj_props_model)

        self.obj_props_model.changed.connect(self.map_edit.obj_data_changed)

    def area_changed(self, gfx, pals, metatile_data, rooms_data, global_obj_data):
        self.rooms_data = rooms_data
        self.global_obj_data = global_obj_data

        self.room_select.area_changed(gfx, pals, metatile_data, rooms_data)
        self.map_edit.area_changed(gfx, pals, metatile_data, rooms_data, global_obj_data)

        self.obj_list.objs = global_obj_data
        self.obj_list.model = ObjList.ObjListModel(global_obj_data)
        self.obj_list.setModel(self.obj_list.model)

        self.obj_list.model.changed.connect(self.obj_list_changed)
        self.obj_list.model.changed.connect(self.map_edit.obj_list_changed)
        if len(global_obj_data) > 0:
            self.obj_props_model = ObjPropsModel(global_obj_data[0], 0, self.obj_types)
            self.obj_props_model.changed.connect(self.map_edit.obj_data_changed)
        else:
            self.obj_props_model = None
        self.obj_props_table.setModel(self.obj_props_model)

    def metatile_edited(self, mt_idx):
        self.room_select.metatile_edited(mt_idx)
        self.map_edit.metatile_edited(mt_idx)

    def room_edited(self, room_idx, x, y):
        self.room_select.room_edited(room_idx, x, y)
        self.map_edit.room_edited()
