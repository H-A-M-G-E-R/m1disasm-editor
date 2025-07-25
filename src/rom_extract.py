import base64, json, romfile

def extract_palette(addr):
    rom.seek(addr)
    palette = []
    while True:
        if rom.read_int(1) == 0: # terminator
            break
        start = rom.read_int(1)
        n = rom.read_int(1) & 0x7F
        if n & 0x40: # fill
            data = [rom.read_int(1)]*(n & 0x3F)
        else: # copy
            data = [rom.read_int(1) for _ in range(n)]
        palette.append({
            'start': start,
            'data': data
        })

    return palette

def extract_structs(addr, n):
    structs = []
    for i in range(n):
        struct = []
        rom.seek(addr+i*2)
        rom.seek((addr&0xFF0000)+rom.read_int(2))

        while True:
            n = rom.read_int(1)
            if n == 0xFF:
                break
            struct.append([n >> 4] + [rom.read_int(1) for _ in range(0x10 if n & 0xF == 0 else n & 0xF)])

        structs.append(struct)

    return structs

def get_num_obj_params(control, types: dict):
    for k, v in types.items():
        if v['type'] == control & 0xF:
            return len(v['props'])-1

def convert_obj_data(obj, types: dict, room_x=0, room_y=0):
    for k, v in types.items():
        if v['type'] == obj[0] & 0xF:
            obj_type = k

    props = {}

    for param_i, param in enumerate(obj):
        for prop_name, info in types[obj_type]['props'][param_i].items():
            prop = (param >> info['shifts']) % (1 << info['len'])
            props[prop_name] = prop

    match obj_type:
        case 'enemy':
            x = props['x']*0x10+0xC
            y = props['y']*0x10+8
        case 'door':
            x = (0xF0, 0x10)[props['dir']]
            y = 0x68
        case 'elevator':
            x = 0x80
            y = 0x83
        case 'pipe_bug_hole':
            x = props['x']*0x10
            y = props['y']*0x10+8
        case 'item':
            x = props['x']*0x10+8
            y = props['y']*0x10+8
        case 'cannon':
            x = props['x']*0x10+7
            y = props['y']*0x10+7
        case 'zebetite':
            x = 0xA0-((props['id']%2)*0x80)
            y = 0x60
        case _:
            x = 0x80
            y = 0x80

    if 'x' in props:
        props.pop('x')
    if 'y' in props:
        props.pop('y')

    data = {
        'obj_type': obj_type,
        'x': x+room_x*0x100,
        'y': y+room_y*0x100
    }

    for prop_name, prop in props.items():
        data[prop_name] = prop

    return data

def extract_room(addr, structs, obj_types: dict):
    rom.seek(addr)
    room_pal = rom.read_int(1)

    tilemap = [0xFF]*0xF0
    attrs = [room_pal]*0x100
    objs = []

    while True:
        pos = rom.read_int(1)
        if pos == 0xFF:
            break
        elif pos == 0xFE:
            continue
        elif pos == 0xFD:
            while True:
                control = rom.read_int(1)
                if control == 0xFF:
                    break

                num_params = get_num_obj_params(control, obj_types)
                objs.append(convert_obj_data([control] + [rom.read_int(1) for _ in range(num_params)], obj_types))
            break
        x_pos = pos & 0xF
        y_pos = pos >> 4
        struct_i = rom.read_int(1)
        pal = rom.read_int(1)

        for row in structs[struct_i]:
            if y_pos >= 0xF:
                break
            x = x_pos + row[0]
            if x < 0x10:
                for macro_i in row[1:]:
                    tilemap[x+y_pos*0x10] = macro_i
                    if pal != room_pal:
                        attrs[x+y_pos*0x10] = pal
                    x += 1
                    if x >= 0x10:
                        break
            y_pos += 1

    return {
        'tilemap': str(base64.b64encode(bytearray(tilemap)), 'utf8'),
        'attrs': str(base64.b64encode(bytearray(attrs)), 'utf8'),
        'objs': objs
    }

def extract_global_objs(addr, obj_types: dict):
    rom.seek(addr)
    objs = []
    obj_i = 0
    while True:
        y = rom.read_int(1)
        next_row_ptr = rom.read_int(2)
        while True:
            x = rom.read_int(1)
            next_col = rom.read_int(1)
            while True:
                control = rom.read_int(1)
                if control == 0:
                    break

                num_params = get_num_obj_params(control, obj_types)
                objs.append(convert_obj_data([control] + [rom.read_int(1) for _ in range(num_params)], obj_types, x, y))
            if next_col == 0xFF:
                break
        if next_row_ptr == 0xFFFF:
            break

    return objs

if __name__ == '__main__':
    rom = romfile.ROMFile('M1.nes')
    local_obj_types = json.load(open('data/local_obj_types.json', 'r'))
    global_obj_types = json.load(open('data/global_obj_types.json', 'r'))

    area_data = [
        ('brinstar', 0x10000, 0x32, 0x2F),
        ('norfair', 0x20000, 0x31, 0x2E),
        ('tourian', 0x30000, 0x20, 0x15),
        ('kraid', 0x40000, 0x27, 0x25),
        ('ridley', 0x50000, 0x1D, 0x2A),
    ]

    rom.seek(0x0A53E)
    with open(f'data/world_map.bin', 'wb') as world_map_file:
        world_map_file.write(rom.read(0x400))

    for area_name, bank, num_structs, num_rooms in area_data:
        palettes = []
        for i in range(0x1C):
            rom.seek(bank+0x9560+i*2)
            palettes.append(extract_palette(bank+rom.read_int(2)))
        with open(f'data/{area_name}/palettes.json', 'w') as json_file:
            json.dump(palettes, json_file, indent=1)
        
        rom.seek(bank+0x959E)
        rom.seek(bank+rom.read_int(2))
        metatiles = bytearray(rom.read(0x40*4))
        metatiles.extend(b'\xFF'*(0xC0*4))
        with open(f'data/{area_name}/metatiles.bin', 'wb') as metatiles_file:
            metatiles_file.write(metatiles)

        rom.seek(bank+0x959C)
        structs = extract_structs(bank+rom.read_int(2), num_structs)

        rom.seek(bank+0x959A)
        room_ptr_tbl = bank+rom.read_int(2)

        rooms = []
        for i in range(num_rooms):
            rom.seek(room_ptr_tbl+i*2)
            rooms.append(extract_room(bank+rom.read_int(2), structs, local_obj_types))
        with open(f'data/{area_name}/rooms.json', 'w') as json_file:
            json.dump(rooms, json_file, indent=1)

        with open(f'data/{area_name}/global_objs.json', 'w') as json_file:
            rom.seek(bank+0x9598)
            json.dump(extract_global_objs(bank+rom.read_int(2), global_obj_types), json_file, indent=1)
