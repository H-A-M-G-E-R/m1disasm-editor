def convert_palette(idxs, fp, transparent=True):
    with open(fp, 'rb') as pal_file:
        converted_pal = []
        i = 0
        for idx in idxs:
            if i & 3 == 0:
                if transparent:
                    converted_pal += [0x00000000]
                elif len(converted_pal) == 0:
                    pal_file.seek(idx*3)
                    converted_pal.append(int.from_bytes(pal_file.read(3), 'big') + 0xFF000000)
                else:
                    converted_pal += [converted_pal[0]]
            else:
                pal_file.seek(idx*3)
                converted_pal.append(int.from_bytes(pal_file.read(3), 'big') + 0xFF000000)
            i += 1
    return converted_pal

def put_palette_strings(strings, pal=[0x0F]*0x20):
    for string in strings:
        for i in range(len(string['data'])):
            pal[string['start']+i] = string['data'][i]

    return pal
