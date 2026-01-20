from PySide6.QtCore import Qt, Signal, Slot, QAbstractListModel, QAbstractTableModel, QModelIndex, QMimeData
from PySide6.QtGui import QImage, QPainter, QBrush, QPen, QFont
from PySide6.QtWidgets import *
from src.pal_utils import convert_palette, put_palette_strings
from src.twobpp import gfx_2_qimage
from src.obj_widgets import ObjectGraphicsItem, ObjPropsModel, ObjPropsDelegate, ObjList

class RoomEditWindow(QMainWindow):
    class MetatileSelect(QGraphicsScene):
        changed = Signal(int)

        def __init__(self, gfx, pals, metatile_data, parent=None):
            super().__init__(0, 0, 256, 256, parent)
            self.gfx = gfx
            self.pals = pals
            self.metatile_data = metatile_data

            # Cursor at selected metatile
            self.selected_mt = 0
            self.selected_mt_rect = QGraphicsRectItem(0, 0, 16, 16)
            self.addItem(self.selected_mt_rect)

            self.palette_changed(0)
            self.show_tile_idxs = False

        def drawBackground(self, painter: QPainter, rect):
            for row in range(0x10):
                for col in range(0x10):
                    painter.drawImage(col*0x10, row*0x10, self.mt_images[col+row*0x10])
            if self.show_tile_idxs:
                pen = QPen((0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF)[self.selected_pal])
                pen.setJoinStyle(Qt.MiterJoin)
                painter.setPen(pen)
                painter.setFont(QFont('monospace', 4, QFont.Bold))
                for row in range(0x10):
                    for col in range(0x10):
                        mt_idx = col+row*0x10
                        pen.setJoinStyle(Qt.MiterJoin)
                        painter.drawText(col*0x10+1, row*0x10+6, f'{self.metatile_data[mt_idx*4]:02X}')
                        painter.drawText(col*0x10+8+1, row*0x10+6, f'{self.metatile_data[mt_idx*4+1]:02X}')
                        painter.drawText(col*0x10+1, row*0x10+6+8, f'{self.metatile_data[mt_idx*4+2]:02X}')
                        painter.drawText(col*0x10+8+1, row*0x10+6+8, f'{self.metatile_data[mt_idx*4+3]:02X}')

        def mousePressEvent(self, event):
            super().mousePressEvent(event)
            x = int(event.scenePos().x())
            y = int(event.scenePos().y())
            self.selected_mt = int(x//16+y//16*16)
            self.selected_mt_rect.setPos(x//16*16, y//16*16)

            self.changed.emit(self.selected_mt)

        @Slot(int)
        def palette_changed(self, pal_idx):
            self.selected_pal = pal_idx

            # Generate metatile images
            self.mt_images = []
            pal = convert_palette(put_palette_strings(self.pals[0]), 'src/palette.pal', transparent=False)
            for i in range(0x100):
                self.mt_images.append(gfx_2_qimage(self.gfx, pal, width=2, idxs=self.metatile_data[i*4:i*4+4], pal_per_tile=[pal_idx]*4))

            # Cursor at selected metatile
            pen = QPen((0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF)[pal_idx])
            pen.setJoinStyle(Qt.MiterJoin)
            self.selected_mt_rect.setPen(pen)

            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_tile_idxs_toggled(self, state):
            self.show_tile_idxs = state == Qt.Checked
            self.update(self.sceneRect())

        def area_changed(self, gfx, pals, metatile_data):
            self.gfx = gfx
            self.pals = pals
            self.metatile_data = metatile_data

            self.palette_changed(self.selected_pal)

        def colors_changed(self, pals):
            self.area_changed(self.gfx, pals, self.metatile_data)

        def metatile_edited(self, mt_idx):
            pal = convert_palette(put_palette_strings(self.pals[0]), 'src/palette.pal', transparent=False)
            self.mt_images[mt_idx] = gfx_2_qimage(self.gfx, pal, width=2, idxs=self.metatile_data[mt_idx*4:mt_idx*4+4], pal_per_tile=[self.selected_pal]*4)
            self.update(mt_idx%0x10*0x10, mt_idx//0x10*0x10, 0x10, 0x10)

    class MetatileSelectView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)
            self.setScene(scene)
            self.setFixedSize(256*2, 256*2)
            self.scale(2, 2)
            self.setFrameStyle(QFrame.NoFrame)

    class RoomEdit(QGraphicsScene):
        edited = Signal(int, int, int)

        def __init__(self, gfx, pals, metatile_data, rooms_data, parent=None):
            super().__init__(0, 0, 256, 240, parent)

            self.area_changed(gfx, pals, metatile_data, rooms_data)

            self.selected_mt = 0
            self.selected_pal = 0
            self.show_tile_idxs = False
            self.show_mt_idxs = False
            self.highlight_same_mts = False

        def drawBackground(self, painter: QPainter, rect):
            tm = self.rooms_data[self.current_room]['tilemap']
            attrs = self.rooms_data[self.current_room]['attrs']
            for row in range(0xF):
                for col in range(0x10):
                    painter.drawImage(col*0x10, row*0x10, self.mt_images[attrs[col+row*0x10]][tm[col+row*0x10]])

            pen = QPen(0x00FF00)
            pen.setJoinStyle(Qt.MiterJoin)
            painter.setPen(pen)
            if self.show_tile_idxs:
                painter.setFont(QFont('monospace', 4, QFont.Bold))
                for row in range(0xF):
                    for col in range(0x10):
                        mt_idx = tm[col+row*0x10]
                        pen.setColor((0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF)[attrs[col+row*0x10]])
                        painter.setPen(pen)
                        painter.drawText(col*0x10+1, row*0x10+6, f'{self.metatile_data[mt_idx*4]:02X}')
                        painter.drawText(col*0x10+8+1, row*0x10+6, f'{self.metatile_data[mt_idx*4+1]:02X}')
                        painter.drawText(col*0x10+1, row*0x10+6+8, f'{self.metatile_data[mt_idx*4+2]:02X}')
                        painter.drawText(col*0x10+8+1, row*0x10+6+8, f'{self.metatile_data[mt_idx*4+3]:02X}')
            elif self.show_mt_idxs:
                painter.setFont(QFont('monospace', 8, QFont.Bold))
                for row in range(0xF):
                    for col in range(0x10):
                        pen.setColor((0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF)[attrs[col+row*0x10]])
                        painter.setPen(pen)
                        painter.drawText(col*0x10+1, row*0x10+12, f'{tm[col+row*0x10]:02X}')
            if self.highlight_same_mts:
                # workaround for Qt bug
                brush = QBrush(0x00FF00)
                painter.setBrush(brush)
                pen.setStyle(Qt.NoPen)
                painter.setPen(pen)
                painter.setOpacity(0.5)
                for row in range(0xF):
                    for col in range(0x10):
                        if tm[col+row*0x10] == self.selected_mt:
                            brush.setColor((0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF)[attrs[col+row*0x10]])
                            painter.setBrush(brush)
                            painter.drawRect(col*0x10, row*0x10, 0x10, 0x10)
                brush.setStyle(Qt.NoBrush)
                painter.setBrush(brush)
                pen.setStyle(Qt.SolidLine)
                painter.setOpacity(1.0)
                for row in range(0xF):
                    for col in range(0x10):
                        if tm[col+row*0x10] == self.selected_mt:
                            pen.setColor((0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF)[attrs[col+row*0x10]])
                            painter.setPen(pen)
                            painter.drawRect(col*0x10, row*0x10, 0x10, 0x10)

        def mousePressEvent(self, event):
            super().mousePressEvent(event)

            if self.mouseGrabberItem() == None and event.button() == Qt.LeftButton:
                self.edit_room_metatile(int(event.scenePos().x()), int(event.scenePos().y()))

        def mouseMoveEvent(self, event):
            super().mouseMoveEvent(event)

            if self.mouseGrabberItem() == None and event.buttons() & Qt.LeftButton:
                self.edit_room_metatile(int(event.scenePos().x()), int(event.scenePos().y()))

        def edit_room_metatile(self, x, y):
            if x >= 0 and x < 0x100 and y >= 0 and y < 0xF0:
                target_mt_loc = int(x//0x10+y//0x10*0x10)
                self.rooms_data[self.current_room]['tilemap'][target_mt_loc] = self.selected_mt
                self.rooms_data[self.current_room]['attrs'][target_mt_loc] = self.selected_pal
                self.update(x//0x10*0x10, y//0x10*0x10, 0x10, 0x10)

                self.edited.emit(self.current_room, x//0x10*0x10, y//0x10*0x10)

        @Slot(int)
        def room_changed(self, room_idx):
            self.current_room = room_idx
            self.update(self.sceneRect())

            # Update objs display
            self.obj_list_changed(self.rooms_data[room_idx]['objs'])

        @Slot(int)
        def mt_select_changed(self, mt_idx):
            self.selected_mt = mt_idx
            if self.highlight_same_mts:
                self.update(self.sceneRect())

        @Slot(int)
        def palette_changed(self, pal_idx):
            self.selected_pal = pal_idx

        @Slot(Qt.CheckState)
        def show_tile_idxs_toggled(self, state):
            self.show_tile_idxs = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_mt_idxs_toggled(self, state):
            self.show_mt_idxs = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def highlight_same_mts_toggled(self, state):
            self.highlight_same_mts = state == Qt.Checked
            self.update(self.sceneRect())

        @Slot(Qt.CheckState)
        def show_objs_toggled(self, state):
            for obj in self.objs:
                obj.setVisible(state == Qt.Checked)

        @Slot(list)
        def obj_list_changed(self, objs):
            # Update objs display
            self.clear()
            self.objs = []
            for i, obj_data in enumerate(self.rooms_data[self.current_room]['objs']): # instead of enumerate(objs) due to a PySide6 bug
                obj = ObjectGraphicsItem(obj_data, i)
                self.addItem(obj)
                self.objs.append(obj)

        @Slot(int)
        def obj_data_changed(self, idx):
            obj_data = self.objs[idx].obj_data
            self.objs[idx].setPos(obj_data[1][1], obj_data[2][1])
            self.objs[idx].update(self.objs[idx].boundingRect())

        def area_changed(self, gfx, pals, metatile_data, rooms_data):
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

            self.current_room = 0
            self.update(self.sceneRect())

            # Objects display
            self.obj_list_changed(self.rooms_data[self.current_room]['objs'])

        def colors_changed(self, pals):
            self.area_changed(self.gfx, pals, self.metatile_data, self.rooms_data)

        def metatile_edited(self, mt_idx):
            pal = convert_palette(put_palette_strings(self.pals[0]), 'src/palette.pal', transparent=False)
            for pal_idx in range(4):
                self.mt_images[pal_idx][mt_idx] = gfx_2_qimage(self.gfx, pal, width=2, idxs=self.metatile_data[mt_idx*4:mt_idx*4+4], pal_per_tile=[pal_idx]*4)
            self.update(self.sceneRect())

    class RoomEditView(QGraphicsView):
        def __init__(self, scene, parent=None):
            super().__init__(parent)
            self.setScene(scene)
            self.setFixedSize(256*2, 240*2)
            self.scale(2, 2)
            self.setFrameStyle(QFrame.NoFrame)

    new_room_added = Signal()

    def __init__(self, gfx, pals, metatile_data, rooms_data, obj_types, parent=None):
        super().__init__(parent)

        self.rooms_data = rooms_data
        self.obj_types = obj_types
        self.current_room = 0

        # Metatile column
        self.mt_select = self.MetatileSelect(gfx, pals, metatile_data)
        self.mt_select_view = self.MetatileSelectView(self.mt_select)
        self.pal_select = QSpinBox(minimum=0, maximum=3)
        self.show_tile_idxs_toggle = QCheckBox()
        self.mt_select_form = QFormLayout()
        self.mt_select_form.addRow('Palette', self.pal_select)
        self.mt_select_form.addRow('Show tile indices', self.show_tile_idxs_toggle)
        self.mt_select_layout = QVBoxLayout()
        self.mt_select_layout.addWidget(self.mt_select_view)
        self.mt_select_layout.addLayout(self.mt_select_form)

        # Room column
        self.room_select = QSpinBox(minimum=0, maximum=len(self.rooms_data)-1)
        self.room_select.setDisplayIntegerBase(16)
        self.room_select_form = QFormLayout()
        self.room_select_form.addRow('Room', self.room_select)
        self.new_room_button = QPushButton('New room')
        self.room_edit = self.RoomEdit(gfx, pals, metatile_data, self.rooms_data)
        self.room_edit_view = self.RoomEditView(self.room_edit)
        self.show_mt_idxs_toggle = QCheckBox()
        self.highlight_same_mts_toggle = QCheckBox()
        self.show_objs_toggle = QCheckBox()
        self.show_objs_toggle.setCheckState(Qt.Checked)
        self.room_edit_form = QFormLayout()
        self.room_edit_form.addRow('Show metatile indices', self.show_mt_idxs_toggle)
        self.room_edit_form.addRow('Highlight same metatiles', self.highlight_same_mts_toggle)
        self.room_edit_form.addRow('Show objects', self.show_objs_toggle)
        self.room_edit_layout = QVBoxLayout()
        self.room_edit_layout.addLayout(self.room_select_form)
        self.room_edit_layout.addWidget(self.new_room_button)
        self.room_edit_layout.addWidget(self.room_edit_view)
        self.room_edit_layout.addLayout(self.room_edit_form)

        # Object column
        self.obj_list = ObjList(self.rooms_data[self.current_room]['objs'])
        self.obj_props_table = QTableView()
        self.obj_props_table.setItemDelegate(ObjPropsDelegate(obj_types))
        self.room_changed(self.current_room)
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
        self.layout.addLayout(self.mt_select_layout)
        self.layout.addLayout(self.room_edit_layout)
        self.group_box = QGroupBox(self)
        self.group_box.setLayout(self.layout)
        self.setCentralWidget(self.group_box)

        self.addDockWidget(Qt.RightDockWidgetArea, self.obj_dock)

        # Slots
        self.mt_select.changed.connect(self.room_edit.mt_select_changed)
        self.pal_select.valueChanged.connect(self.mt_select.palette_changed)
        self.pal_select.valueChanged.connect(self.room_edit.palette_changed)
        self.show_tile_idxs_toggle.checkStateChanged.connect(self.mt_select.show_tile_idxs_toggled)
        self.show_tile_idxs_toggle.checkStateChanged.connect(self.room_edit.show_tile_idxs_toggled)
        self.show_objs_toggle.checkStateChanged.connect(self.room_edit.show_objs_toggled)

        self.room_select.valueChanged.connect(self.room_edit.room_changed)
        self.room_select.valueChanged.connect(self.room_changed)
        self.new_room_button.clicked.connect(self.new_room_button_clicked)
        self.show_mt_idxs_toggle.checkStateChanged.connect(self.room_edit.show_mt_idxs_toggled)
        self.highlight_same_mts_toggle.checkStateChanged.connect(self.room_edit.highlight_same_mts_toggled)

        self.obj_list.pressed.connect(self.obj_list_pressed)

    @Slot(int)
    def room_changed(self, idx):
        self.current_room = idx
        objs = self.rooms_data[idx]['objs']
        self.obj_list.objs = objs
        self.obj_list.model = ObjList.ObjListModel(objs)
        self.obj_list.setModel(self.obj_list.model)

        self.obj_list.model.changed.connect(self.obj_list_changed)
        self.obj_list.model.changed.connect(self.room_edit.obj_list_changed)
        if len(objs) > 0:
            self.obj_props_model = ObjPropsModel(objs[0], 0, self.obj_types)
            self.obj_props_model.changed.connect(self.room_edit.obj_data_changed)
        else:
            self.obj_props_model = None
        self.obj_props_table.setModel(self.obj_props_model)

    @Slot()
    def new_room_button_clicked(self):
        self.rooms_data.append({
            'tilemap': [0xFF]*0xF0,
            'attrs': [0]*0x100,
            'objs': []
        })
        self.room_select.setMaximum(len(self.rooms_data)-1)
        self.room_select.setValue(len(self.rooms_data)-1)

        self.new_room_added.emit()

    @Slot(list)
    def obj_list_changed(self, objs):
        if self.obj_list.currentIndex().isValid():
            idx = self.obj_list.currentIndex().row()
            self.obj_props_model = ObjPropsModel(self.rooms_data[self.current_room]['objs'][idx], idx, self.obj_types)
            self.obj_props_model.changed.connect(self.room_edit.obj_data_changed)
        else:
            self.obj_props_model = None
        self.obj_props_table.setModel(self.obj_props_model)

    @Slot(QModelIndex)
    def obj_list_pressed(self, index):
        self.obj_props_model = ObjPropsModel(self.rooms_data[self.current_room]['objs'][index.row()], index.row(), self.obj_types)
        self.obj_props_table.setModel(self.obj_props_model)

        self.obj_props_model.changed.connect(self.room_edit.obj_data_changed)

    def area_changed(self, gfx, pals, metatile_data, rooms_data):
        self.rooms_data = rooms_data

        self.pal_select.setValue(0)
    
        self.room_select.setValue(0)
        self.room_select.setMaximum(len(rooms_data)-1)

        self.mt_select.area_changed(gfx, pals, metatile_data)
        self.room_edit.area_changed(gfx, pals, metatile_data, rooms_data)

        self.room_changed(0)

    def colors_changed(self, pals):
        self.mt_select.colors_changed(pals)
        self.room_edit.colors_changed(pals)

    def metatile_edited(self, mt_idx, corner):
        self.mt_select.metatile_edited(mt_idx)
        self.room_edit.metatile_edited(mt_idx)
