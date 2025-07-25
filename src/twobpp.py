import numpy as np
from PySide6.QtGui import QImage

def gfx_2_qimage(gfx, palette, width=0x10, idxs=None, pal_per_tile=None):
    if pal_per_tile == None:
        pal_per_tile = [0]*(len(gfx)//0x10)

    tiles = []
    for n, i in enumerate(range(len(gfx)//0x10) if idxs == None else idxs):
        tile = convert_tile_from_bitplanes(gfx[i*0x10:i*0x10+0x10])
        tiles.append(tile + np.full((8, 8), pal_per_tile[n]*4, dtype=np.uint8))
    while len(tiles) % width != 0:
        tiles.append(np.zeros((8, 8), dtype=np.uint8))
    rows = []
    for row_i in range(len(tiles)//width):
        rows.append(np.concatenate(tiles[row_i*width:row_i*width+width], 1))

    image = QImage(np.ravel(np.concatenate(rows, 0)), width*8, len(tiles)//width*8, QImage.Format_Indexed8)
    image.setColorTable(palette)
    return image

''' Modified From SpriteSomething (https://github.com/Artheau/SpriteSomething) '''
def add_to_canvas_from_spritemap(canvas, tilemaps, graphics):
    # expects:
    #  a dictionary of spritemap entries
    #  a bytearray or list of bytes of 2bpp graphics

    for tilemap in reversed(tilemaps):
        x_offset = tilemap['x']
        y_offset = tilemap['y']
        index = tilemap['tile']
        palette = tilemap['palette']
        priority = tilemap['bg_priority']
        h_flip = tilemap['h_flip']
        v_flip = tilemap['v_flip']

        def draw_tile_to_canvas(new_x_offset, new_y_offset, new_index):
            tile_to_write = convert_tile_from_bitplanes(graphics[new_index*16+0x1000:new_index*16+0x1010])
            if h_flip:
                tile_to_write = np.fliplr(tile_to_write)
            if v_flip:
                tile_to_write = np.flipud(tile_to_write)
            for (i, j), value in np.ndenumerate(tile_to_write):
                if value != 0:  # if not transparent
                    canvas[(new_x_offset + j, new_y_offset + i)] = palette * 4 + int(value)

        draw_tile_to_canvas(x_offset, y_offset, index)

def bounding_box(canvas):
    '''Returns the minimum bounding box centered at the middle without cropping a single pixel'''
    if canvas.keys():
        x_min = min([x for (x, y) in canvas.keys()])
        x_max = max([x for (x, y) in canvas.keys()]) + 1
        y_min = min([y for (x, y) in canvas.keys()])
        y_max = max([y for (x, y) in canvas.keys()]) + 1

        return (max(abs(x_min), abs(x_max)), max(abs(y_min), abs(y_max)))
    else:
        return (0, 0)

def to_qimage(canvas, left, top, right, bottom):
    '''Returns a QImage cropped by a bounding box'''
    image = QImage(right-left, bottom-top, QImage.Format_Indexed8)
    image.fill(0) # fill image with transparency

    # add the palette
    image.setColorTable(palette)

    # add the pixels
    if canvas.keys():
        for (i, j), value in canvas.items():
            image.setPixel(i-left, j-top, value)

    return image

def convert_tile_from_bitplanes(raw_tile):
    # See https://www.nesdev.org/wiki/PPU_pattern_tables for the format
    # an attempt to make this ugly process mildly efficient

    # axes 1 and 0 are the rows and columns of the image, respectively
    # numpy has the axes swapped
    tile = np.zeros((8, 1, 2), dtype=np.uint8)

    tile[:, 0, 0] = raw_tile[0:8] # bitplane 0
    tile[:, 0, 1] = raw_tile[8:16] # bitplane 1

    tile_bits = np.unpackbits(tile, axis=1, bitorder='big') # decompose the bitplanes to rows
    fixed_bits = np.packbits(tile_bits, axis=2, bitorder='little') # combine the bitplanes
    returnvalue = fixed_bits.reshape(8, 8)
    return returnvalue

if __name__ == '__main__':
    import base64, json
    from pal_utils import convert_palette, put_palette_strings

    for area in ('brinstar', 'norfair', 'tourian', 'kraid', 'ridley'):
        with open(f'data/{area}/bg.chr', 'rb') as f:
            gfx = bytearray(f.read())

        with open(f'data/{area}/palettes.json', 'r') as f:
            pals = json.load(f)

        pal = convert_palette(put_palette_strings(pals[0]), 'data/palette.pal')

        '''
        image = gfx_2_qimage(gfx, pal)
        image.save(f'test_{area}.png')
        '''

        '''
        with open(f'data/{area}/metatiles.bin', 'rb') as f:
            metatiles = [int.from_bytes(f.read(1), 'little') for _ in range(0xFF*4)]+[0xFF]*4

        idxs = []
        for row in range(0x10):
            for col in range(0x10):
                idxs.extend(metatiles[(row*0x10+col)*4:(row*0x10+col)*4+2])
            for col in range(0x10):
                idxs.extend(metatiles[(row*0x10+col)*4+2:(row*0x10+col)*4+4])

        image = gfx_2_qimage(gfx, pal, width=0x20, idxs=idxs, pal_per_tile=[1]*0x100)
        image.save(f'test_{area}.png')
        '''

        with open(f'data/{area}/metatiles.bin', 'rb') as f:
            metatiles = [int.from_bytes(f.read(1), 'little') for _ in range(0xFF*4)]+[0xFF]*4

        with open(f'data/{area}/rooms.json', 'r') as f:
            rooms = json.load(f)

        for room_i, room in enumerate(rooms):
            tilemap = bytearray(base64.b64decode(room['tilemap']))
            attrs = bytearray(base64.b64decode(room['attrs']))
            idxs = []
            new_attrs = []
            for row in range(0xF):
                for col in range(0x10):
                    idxs.extend(metatiles[tilemap[row*0x10+col]*4:tilemap[row*0x10+col]*4+2])
                    new_attrs.append(attrs[row*0x10+col])
                    new_attrs.append(attrs[row*0x10+col])
                for col in range(0x10):
                    idxs.extend(metatiles[tilemap[row*0x10+col]*4+2:tilemap[row*0x10+col]*4+4])
                    new_attrs.append(attrs[row*0x10+col])
                    new_attrs.append(attrs[row*0x10+col])

            image = gfx_2_qimage(gfx, pal, width=0x20, idxs=idxs, pal_per_tile=new_attrs)
            image.save(f'test/room_{area}_{room_i}.png')
