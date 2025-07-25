from PySide6.QtCore import Qt, Signal, Slot, QAbstractListModel, QAbstractTableModel, QModelIndex, QMimeData
from PySide6.QtWidgets import *
import copy, json

class ObjPropsModel(QAbstractTableModel):
    changed = Signal(int)

    def __init__(self, obj_data, obj_idx, obj_types, parent=None):
        super().__init__(parent)
        self.obj_data = obj_data
        self.obj_idx = obj_idx
        self.obj_types = obj_types

    def rowCount(self, parent):
        return len(self.obj_data)

    def columnCount(self, parent):
        return 2

    def data(self, index: QModelIndex, role):
        if role == Qt.DisplayRole:
            if index.column() == 1 and index.row() > 0:
                return f'{self.obj_data[index.row()][1]:x}'
            else:
                return self.obj_data[index.row()][index.column()]
        elif role == Qt.EditRole:
            if index.column() == 1:
                return self.obj_data[index.row()][1]

    def setData(self, index: QModelIndex, value, role):
        if role == Qt.EditRole:
            self.obj_data[index.row()][1] = value
            if index.row() == 0:
                self.removeRows(3, len(self.obj_data)-3, QModelIndex())

                new_props = []
                for param_byte in self.obj_types[self.obj_data[0][1]]['props']:
                    new_props.extend(prop for prop in param_byte)
                if 'x' in new_props:
                    new_props.remove('x')
                if 'y' in new_props:
                    new_props.remove('y')

                self.insertRows(3, len(new_props), QModelIndex())
                for i, prop in enumerate(new_props):
                    self.obj_data[i+3][0] = prop

            self.changed.emit(self.obj_idx)
            return True
        return False

    def flags(self, index: QModelIndex):
        if index.column() == 1:
            return Qt.ItemIsEditable | super().flags(index)
        else:
            return super().flags(index)

    def insertRows(self, pos, rows, parent: QModelIndex = QModelIndex()):
        self.beginInsertRows(QModelIndex(), pos, pos+rows-1)
        for row in range(rows):
            self.obj_data.insert(pos, ['', 0])
        self.endInsertRows()
        return True

    def removeRows(self, pos, rows, parent: QModelIndex = QModelIndex()):
        self.beginRemoveRows(QModelIndex(), pos, pos+rows-1)
        for row in range(rows):
            self.obj_data.pop(pos)
        self.endRemoveRows()
        return True

class ObjPropsDelegate(QStyledItemDelegate):
    def __init__(self, obj_types, global_flag=False, parent=None):
        super().__init__(parent)

        self.obj_types = obj_types
        self.global_flag = global_flag

    def createEditor(self, parent, option: QStyleOptionViewItem, index: QModelIndex):
        if index.row() == 0:
            editor = QComboBox(parent)
            for obj_type in self.obj_types:
                editor.addItem(obj_type)
        else:
            if self.global_flag and index.row() <= 2:
                editor = QSpinBox(parent, minimum=0, maximum=0x1FFF)
            else:
                editor = QSpinBox(parent, minimum=0, maximum=0xFF)
            editor.setDisplayIntegerBase(16)
        editor.setFrame(False)
        return editor

    def setEditorData(self, editor, index: QModelIndex):
        if index.row() == 0:
            editor.setCurrentText(index.data(Qt.EditRole))
        else:
            editor.setValue(index.data(Qt.EditRole))

    def setModelData(self, editor, model, index: QModelIndex):
        if index.row() == 0:
            model.setData(index, editor.currentText(), Qt.EditRole)
        else:
            model.setData(index, editor.value(), Qt.EditRole)

class ObjList(QListView):
    class ObjListModel(QAbstractListModel):
        changed = Signal(list)

        def __init__(self, objs, parent=None):
            super().__init__(parent)
            self.objs = objs

        def rowCount(self, parent):
            return len(self.objs)

        def columnCount(self, parent):
            return 1

        def data(self, index: QModelIndex, role):
            if role == Qt.DisplayRole:
                return f'{index.row():02X}: {self.objs[index.row()][0][1]}'
            elif role == Qt.EditRole:
                return copy.deepcopy(self.objs[index.row()])

        def setData(self, index: QModelIndex, value, role):
            if role == Qt.EditRole:
                self.objs[index.row()] = copy.deepcopy(value)
                return True
            return False

        def supportedDropActions(self):
            return Qt.CopyAction | Qt.MoveAction

        def flags(self, index: QModelIndex):
            if index.isValid():
                return Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled | super().flags(index)
            else:
                return Qt.ItemIsDropEnabled | super().flags(index)

        def mimeTypes(self):
            return ['application/vnd.text.list']

        def mimeData(self, indices):
            to_json = []
            for index in indices:
                if index.isValid():
                    to_json.append(self.objs[index.row()])

            mime_data = QMimeData()
            mime_data.setData('application/vnd.text.list', bytearray(json.dumps(to_json), 'utf8'))
            return mime_data

        def canDropMimeData(self, data, action, row, column, parent):
            return data.hasFormat('application/vnd.text.list')

        def dropMimeData(self, data, action, row, column, parent):
            if not self.canDropMimeData(data, action, row, column, parent):
                return False

            if action == Qt.IgnoreAction:
                return True

            if row != -1:
                begin_row = row
            elif parent.isValid():
                begin_row = parent.row()
            else:
                begin_row = self.rowCount(QModelIndex())

            objs = json.loads(str(data.data('application/vnd.text.list'), 'utf8'))
            self.insertRows(begin_row, len(objs), QModelIndex())
            for i, obj in enumerate(objs):
                self.setData(self.index(begin_row+i, 0, QModelIndex()), obj, Qt.EditRole)

            self.changed.emit(self.objs)
            return True

        def insertRows(self, pos, rows, parent: QModelIndex = QModelIndex()):
            self.beginInsertRows(QModelIndex(), pos, pos+rows-1)
            for row in range(rows):
                self.objs.insert(pos, [
                    ['obj_type', ''],
                    ['x', 0x80],
                    ['y', 0x80]
                ])
            self.endInsertRows()
            self.changed.emit(self.objs)
            return True

        def removeRows(self, pos, rows, parent: QModelIndex = QModelIndex()):
            self.beginRemoveRows(QModelIndex(), pos, pos+rows-1)
            for row in range(rows):
                self.objs.pop(pos)
            self.endRemoveRows()
            self.changed.emit(self.objs)
            return True

    def __init__(self, objs, parent=None):
        super().__init__(parent)

        self.objs = objs

        self.model = self.ObjListModel(objs)
        self.setModel(self.model)

        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)

        self.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.new_action = self.addAction('New', 'Ctrl+N')
        self.delete_action = self.addAction('Delete', 'Del')

        self.new_action.triggered.connect(self.new_item)
        self.delete_action.triggered.connect(self.delete_item)

    @Slot(bool)
    def new_item(self, checked):
        self.model.insertRows(self.model.rowCount(QModelIndex()), 1, QModelIndex())

    @Slot(bool)
    def delete_item(self, checked):
        if self.currentIndex().isValid():
            self.model.removeRows(self.currentIndex().row(), 1, QModelIndex())
