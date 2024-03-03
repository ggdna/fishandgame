##############################################################################
# copped from https://github.com/nsfmc/swatch/blob/master/swatch/__init__.py
# installation didn't work for me
##############################################################################

import logging
import struct
import os


def parse_chunk(fd):
    chunk_type = fd.read(2)
    while chunk_type:
        if chunk_type == b'\x00\x01':
            # a single color
            logging.debug("[swatch.parser] parse_chunk saw single color")
            o = dict_for_chunk(fd)
            yield o

        elif chunk_type == b'\xC0\x01':
            # folder/palate
            logging.debug("[swatch.parser] parse_chunk saw folder")
            o = dict_for_chunk(fd)
            o['swatches'] = [x for x in colors(fd)]
            yield o

        elif chunk_type == b'\xC0\x02':
            # this signals the end of a folder
            logging.debug("[swatch.parser] parse_chunk saw end of folder")
            assert fd.read(4) == b'\x00\x00\x00\x00'
            pass

        else:
            # the file is malformed?
            logging.debug("[swatch.parser] parse_chunk got malformed ase file")
            assert chunk_type in [
                b'\xC0\x01', b'\x00\x01', b'\xC0\x02', b'\x00\x02']
            pass

        chunk_type = fd.read(2)


def colors(fd):
    chunk_type = fd.read(2)
    while chunk_type in [b'\x00\x01', b'\x00\x02']:
        d = dict_for_chunk(fd)
        yield d
        chunk_type = fd.read(2)
    fd.seek(-2, os.SEEK_CUR)


def dict_for_chunk(fd):
    chunk_length = struct.unpack(">I", fd.read(4))[0]
    data = fd.read(chunk_length)

    title_length = (struct.unpack(">H", data[:2])[0]) * 2
    title = data[2:2 + title_length].decode("utf-16be").strip('\0')
    color_data = data[2 + title_length:]

    output = {
        'name': str(title),
        'type': 'Color Group'  # default to color group
    }

    if color_data:
        fmt = {b'RGB': '!fff', b'Gray': '!f', b'CMYK': '!ffff', b'LAB': '!fff'}
        color_mode = struct.unpack("!4s", color_data[:4])[0].strip()
        color_values = list(struct.unpack(fmt[color_mode], color_data[4:-2]))

        color_types = ['Global', 'Spot', 'Process']
        swatch_type_index = struct.unpack(">h", color_data[-2:])[0]
        swatch_type = color_types[swatch_type_index]

        output.update({
            'data': {
                'mode': color_mode.decode('utf-8'),
                'values': color_values
            },
            'type': str(swatch_type)
        })

    return output

def parse(filename):
    """parses a .ase file and returns a list of colors and color groups

    `swatch.parse` reads in an ase file and converts it to a list of colors and
    palettes. colors are simple dicts of the form

    ```json
    {
        'name': u'color name',
        'type': u'Process',
        'data': {
            'mode': u'RGB',
            'values': [1.0, 1.0, 1.0]
        }
    }
    ```

    the values provided vary between color mode. For all color modes, the
    value is always a list of floats.

    RGB: three floats between [0,1]  corresponding to RGB.
    CMYK: four floats between [0,1] inclusive, corresponding to CMYK.
    Gray: one float between [0,1] with 1 being white, 0 being black.
    LAB: three floats. The first L, is ranged from 0,1. Both A and B are
    floats ranging from [-128.0,127.0]. I believe illustrator just crops
    these to whole values, though.

    Palettes (née Color Groups in Adobe Parlance) are also dicts, but they have an
    attribute named `swatches` which contains a list of colors contained within
    the palette.

    ```json
    {
        'name': u'accent colors',
        'type': u'Color Group',
        'swatches': [
            {color}, {color}, ..., {color}
        ]
    }
    ```

    Because Adobe Illustrator lets swatches exist either inside and outside
    of palettes, the output of swatch.parse is a list that may contain
    swatches and palettes, i.e. [ swatch* palette* ]

    Here's an example with a light grey swatch followed by a color group containing three

        >>> import swatch
        >>> swatch.parse("example.ase")
        [{'data': {'mode': u'Gray', 'values': [0.75]},
          'name': u'Light Grey',
          'type': u'Process'},
         {'name': u'Accent Colors',
          'swatches': [{'data': {'mode': u'CMYK',
             'values': [0.5279774069786072,
              0.24386966228485107,
              1.0,
              0.04303044080734253]},
            'name': u'Green',
            'type': u'Process'},
           {'data': {'mode': u'CMYK',
             'values': [0.6261844635009766,
              0.5890134572982788,
              3.051804378628731e-05,
              3.051804378628731e-05]},
            'name': u'Violet Process Global',
            'type': u'Global'},
           {'data': {'mode': u'LAB', 'values': [0.6000000238418579, -35.0, -5.0]},
            'name': u'Cyan Spot (global)',
            'type': u'Spot'}],
          'type': u'Color Group'}]
    """

    with open(filename, "rb") as data:
        header, v_major, v_minor, chunk_count = struct.unpack("!4sHHI", data.read(12))

        assert header == b"ASEF"
        assert (v_major, v_minor) == (1, 0)

        return [c for c in parse_chunk(data)]