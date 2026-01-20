from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import *
from src.pal_utils import convert_palette, put_palette_strings
from src.twobpp import gfx_2_qimage
from src.metatile_edit_window import MetatileEditWindow
from src.room_edit_window import RoomEditWindow
from src.map_edit_window import MapEditWindow
from src.palette_edit_window import PaletteEditWindow
from src.to_asm import palettes_2_asm, room_2_bytes, room_ptrs_and_incbins, global_objs_2_asm
import copy, base64, json, os.path, subprocess, tempfile

class MainWindow(QMainWindow):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)

        self.open_folder(folder_path)

        self.file_menu = QMenu('File')
        self.save_action = self.file_menu.addAction('Save...')
        self.save_action.setShortcut('Ctrl+S')
        self.save_action.triggered.connect(self.save_triggered)

        self.tools_menu = QMenu('Tools')
        self.show_mt_edit_action = self.tools_menu.addAction('Metatile editor')
        self.show_mt_edit_action.triggered.connect(self.show_mt_edit_triggered)
        self.show_room_edit_action = self.tools_menu.addAction('Room editor')
        self.show_room_edit_action.triggered.connect(self.show_room_edit_triggered)
        self.show_map_edit_action = self.tools_menu.addAction('Map editor')
        self.show_map_edit_action.triggered.connect(self.show_map_edit_triggered)
        self.show_palette_edit_action = self.tools_menu.addAction('Palette editor')
        self.show_palette_edit_action.triggered.connect(self.show_palette_edit_triggered)

        self.menuBar().addMenu(self.file_menu)
        self.menuBar().addMenu(self.tools_menu)

        self.area_select = QComboBox(self)
        for area in self.area_names:
            self.area_select.addItem(area)
        self.current_area = self.area_names[0]
        a = self.current_area

        self.setCentralWidget(self.area_select)

        self.metatile_edit_window = MetatileEditWindow(self.gfx[a], self.pals[a], self.metatile_data[a], self)
        #self.metatile_edit_window.show()

        self.room_edit_window = RoomEditWindow(self.gfx[a], self.pals[a], self.metatile_data[a], self.rooms_data[a], self.local_obj_types, self)
        self.room_edit_window.show()

        self.map_edit_window = MapEditWindow(self.gfx[a], self.pals[a], self.metatile_data[a], self.rooms_data[a], self.global_obj_data[a], self.global_obj_types, self.world_map, self)
        self.map_edit_window.show()

        self.palette_edit_window = PaletteEditWindow(self.pals[a], self)
        self.palette_edit_window.show()

        self.area_select.currentTextChanged.connect(self.area_changed)

        self.metatile_edit_window.mt_edit.edited.connect(self.metatile_edited)
        self.room_edit_window.room_edit.edited.connect(self.map_edit_window.room_edited)
        self.room_edit_window.new_room_added.connect(self.map_edit_window.new_room_added)

        self.palette_edit_window.palette_scene.changed.connect(self.palette_changed)

    @Slot(str)
    def area_changed(self, area):
        self.current_area = area
        self.metatile_edit_window.area_changed(self.gfx[area], self.pals[area], self.metatile_data[area])
        self.room_edit_window.area_changed(self.gfx[area], self.pals[area], self.metatile_data[area], self.rooms_data[area])
        self.map_edit_window.area_changed(self.gfx[area], self.pals[area], self.metatile_data[area], self.rooms_data[area], self.global_obj_data[area])
        self.palette_edit_window.area_changed(self.pals[area])

    @Slot(int, int)
    def metatile_edited(self, mt_idx, corner):
        self.room_edit_window.metatile_edited(mt_idx, corner)
        self.map_edit_window.metatile_edited(mt_idx)

    @Slot(int)
    def palette_changed(self, pal):
        self.metatile_edit_window.colors_changed(self.pals[self.current_area])
        self.room_edit_window.colors_changed(self.pals[self.current_area])
        self.map_edit_window.colors_changed(self.pals[self.current_area])

    def open_folder(self, folder_path):
        self.folder_path = folder_path

        with open(os.path.join(folder_path, 'area_names.json'), 'r') as f:
            self.area_names = json.load(f)

        with open(os.path.join(folder_path, 'local_obj_types.json'), 'r') as f:
            self.local_obj_types = json.load(f)

        with open(os.path.join(folder_path, 'global_obj_types.json'), 'r') as f:
            self.global_obj_types = json.load(f)

        with open(os.path.join(folder_path, 'world_map.bin'), 'rb') as f:
            self.world_map = [int(b) for b in f.read()]

        self.gfx = {}
        self.pals = {}
        self.metatile_data = {}
        self.rooms_data = {}
        self.global_obj_data = {}
        for area in self.area_names:
            with open(os.path.join(folder_path, f'{area}/bg.chr'), 'rb') as f:
                self.gfx[area] = bytearray(f.read())

            with open(os.path.join(folder_path, f'{area}/palettes.json'), 'r') as f:
                self.pals[area] = json.load(f)

            with open(os.path.join(folder_path, f'{area}/metatiles.bin'), 'rb') as f:
                self.metatile_data[area] = [int.from_bytes(f.read(1), 'little') for _ in range(0xFF*4)]+[0xFF]*4

            with open(os.path.join(folder_path, f'{area}/rooms.json'), 'r') as f:
                raw_rooms = json.load(f)

            with open(os.path.join(folder_path, f'{area}/global_objs.json'), 'r') as f:
                raw_global_objs = json.load(f)

            # Convert data into something that can be used by the editor
            self.rooms_data[area] = copy.deepcopy(raw_rooms)
            for room in self.rooms_data[area]:
                room['tilemap'] = [int(b) for b in base64.b64decode(room['tilemap'])]
                room['attrs'] = [int(b) for b in base64.b64decode(room['attrs'])]
                obj_lists = []
                for obj in room['objs']:
                    obj_list = []
                    for prop_name, prop in obj.items():
                        obj_list.append([prop_name, prop])
                    obj_lists.append(obj_list)
                room['objs'] = obj_lists

            obj_lists = []
            for obj in raw_global_objs:
                obj_list = []
                for prop_name, prop in obj.items():
                    obj_list.append([prop_name, prop])
                obj_lists.append(obj_list)
            self.global_obj_data[area] = obj_lists

    @Slot(bool)
    def save_triggered(self, checked):
        #with open(os.path.join(self.folder_path, 'area_names.json'), 'w') as f:
        #    json.dump(self.area_names, f, indent=4)

        #with open(os.path.join(self.folder_path, 'local_obj_types.json'), 'w') as f:
        #    json.dump(self.local_obj_types, f, indent=4)

        #with open(os.path.join(self.folder_path, 'global_obj_types.json'), 'w') as f:
        #    json.dump(self.global_obj_types, f, indent=4)

        with open(os.path.join(self.folder_path, 'world_map.bin'), 'wb') as f:
            f.write(bytearray(self.world_map))

        for area in self.area_names:
            #with open(os.path.join(self.folder_path, f'{area}/bg.chr'), 'wb') as f:
            #    f.write(bytearray(self.gfx[area]))

            with open(os.path.join(self.folder_path, f'{area}/palettes.json'), 'w') as f:
                json.dump(self.pals[area], f, indent=1)

            with open(os.path.join(self.folder_path, f'{area}/metatiles.bin'), 'wb') as f:
                f.write(bytearray(self.metatile_data[area][:0xFF*4]))

            # Convert back to base64 and dict
            rooms = copy.deepcopy(self.rooms_data[area])
            for room in rooms:
                room['tilemap'] = str(base64.b64encode(bytearray(room['tilemap'])), 'utf8')
                room['attrs'] = str(base64.b64encode(bytearray(room['attrs'])), 'utf8')
                obj_dicts = []
                for obj in room['objs']:
                    obj_dict = {}
                    for prop_name, prop in obj:
                        obj_dict[prop_name] = prop
                    obj_dicts.append(obj_dict)
                room['objs'] = obj_dicts

            global_objs = []
            for obj in self.global_obj_data[area]:
                obj_dict = {}
                for prop_name, prop in obj:
                    obj_dict[prop_name] = prop
                global_objs.append(obj_dict)

            with open(os.path.join(self.folder_path, f'{area}/rooms.json'), 'w') as f:
                json.dump(rooms, f, indent=1)

            with open(os.path.join(self.folder_path, f'{area}/global_objs.json'), 'w') as f:
                json.dump(global_objs, f, indent=1)

            # Export ASM and compressed rooms
            with open(os.path.join(self.folder_path, f'{area}/palettes.asm'), 'w') as f:
                f.write(palettes_2_asm(self.pals[area]))

            for i, room in enumerate(rooms):
                f = tempfile.NamedTemporaryFile(delete_on_close=False)
                f.write(room_2_bytes(room, self.local_obj_types))
                f.close()
                subprocess.run(f'./lzsa -f 1 -r {f.name} {os.path.join(self.folder_path, f'{area}/rooms/{i:02X}.bin')}', shell=True)

            with open(os.path.join(self.folder_path, f'{area}/rooms.asm'), 'w') as f:
                f.write(room_ptrs_and_incbins(area, len(rooms)))

            with open(os.path.join(self.folder_path, f'{area}/global_objs.asm'), 'w') as f:
                f.write(global_objs_2_asm(global_objs, self.global_obj_types))

    @Slot(bool)
    def show_mt_edit_triggered(self, checked):
        self.metatile_edit_window.show()

    @Slot(bool)
    def show_room_edit_triggered(self, checked):
        self.room_edit_window.show()

    @Slot(bool)
    def show_map_edit_triggered(self, checked):
        self.map_edit_window.show()

    @Slot(bool)
    def show_palette_edit_triggered(self, checked):
        self.palette_edit_window.show()
