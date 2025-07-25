import base64, json, subprocess

def palettes_2_asm(palettes):
    unique_pals = []
    for pal_i, pal in enumerate(palettes):
        used_pal_i = -1
        for i, (used_pal, pal_idxs) in enumerate(unique_pals):
            if pal == used_pal:
                used_pal_i = i
                break
        if used_pal_i >= 0:
            unique_pals[used_pal_i][1].append(pal_i)
        else:
            unique_pals.append([pal, [pal_i]])

    asm = ''
    for pal, pal_idxs in unique_pals:
        for pal_i in pal_idxs:
            asm += f'Palette{pal_i:02X}:\n'
        for string in pal:
            asm += f'    PPUString $3F{string['start']:02X}, \\\n'
            asm += f'        ${', $'.join(f'{color:02X}' for color in string['data'])}\n'
        asm += '    PPUStringEnd\n\n'

    return asm

def obj_2_bytes(obj, obj_types):
    out = []
    for byte_i, types_in_byte in enumerate(obj_types[obj['obj_type']]['props']):
        b = obj_types[obj['obj_type']]['type'] if byte_i == 0 else 0
        for prop_name, info in types_in_byte.items():
            if prop_name == 'x' or prop_name == 'y':
                b |= ((obj[prop_name] & 0xFF) >> (8 - info['len'])) << info['shifts']
            else:
                b |= obj[prop_name] << info['shifts']
        out.append(b)
    return out

def room_2_bytes(room, obj_types):
    out = bytearray(base64.b64decode(room['tilemap']))

    attrs = base64.b64decode(room['attrs'])
    converted_attrs = []
    for row in range(0, 0x10, 2):
        for col in range(0, 0x10, 2):
            i = col+row*0x10
            converted_attrs.append(attrs[i] | (attrs[i+1] << 2) | (attrs[i+0x10] << 4) | (attrs[i+0x11] << 6))

    out.extend(converted_attrs)
    for obj in room['objs']:
        out.extend(obj_2_bytes(obj, obj_types))

    out.append(0xFF)
    return out

def room_ptrs_and_incbins(area, room_count):
    asm = 'RmPtrTbl:\n'
    for i in range(room_count):
        asm += f'    .word Room{i:02X}\n'
    asm += '\n'
    for i in range(room_count):
        asm += f'Room{i:02X}: .incbin "data/{area}/rooms/{i:02X}.bin"\n'
    return asm

def global_objs_2_asm(objs, obj_types):
    same_room = {}
    for obj in objs:
        if (obj['x']//0x100, obj['y']//0x100) in same_room:
            same_room[(obj['x']//0x100, obj['y']//0x100)].append(obj)
        else:
            same_room[(obj['x']//0x100, obj['y']//0x100)] = [obj]
    
    same_row = {}
    for col, row in same_room:
        if row in same_row:
            same_row[row].append(col)
        else:
            same_row[row] = [col]
    same_row_list = [[row, cols] for row, cols in same_row.items()]

    # Sort so objects spawn correctly
    same_row_list.sort(key=lambda pair: pair[0])
    for row, cols in same_row_list:
        cols.sort()

    asm = 'SpecItmsTbl:\n'
    for row_i, (row, cols) in enumerate(same_row_list):
        asm += f'@y{row:02X}:\n'
        asm += f'    .byte ${row:02X}\n'
        if row_i == len(same_row_list)-1:
            asm += '    .word $FFFF\n'
        else:
            asm += f'    .word @y{same_row_list[row_i+1][0]:02X}\n'
        for col_i, col in enumerate(cols):
            asm += f'    @@x{col:02X}:\n'
            if col_i == len(cols)-1:
                asm += f'        .byte ${col:02X}, $FF\n'
            else:
                asm += f'        .byte ${col:02X}, @@x{cols[col_i+1]:02X} - @@x{col:02X}\n'
            for obj in same_room[(col, row)]:
                asm += f'        .byte ${', $'.join(f'{b:02X}' for b in obj_2_bytes(obj, obj_types))}\n'
            asm += '        .byte $00\n'

    return asm
