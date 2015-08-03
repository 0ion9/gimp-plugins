#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

TRANSFER_NO_NAMES, TRANSFER_FROM_ACTIVE_PALETTE, TRANSFER_FROM_PARASITE = range(3)
PARASITE_NAME = 'palette-color-names'
STARTINDEX_PARASITE_NAME = 'palette-in-colormap-start-index'
image2layertype = {INDEXED: INDEXED_IMAGE, RGB: RGB_IMAGE}
NEW_PALETTE, OVERWRITE_PALETTE, OVERWRITE_PALETTE_CUSTOM_TARGET = 0, 1, 2

def _store_names(palettename, layer):
    image = layer.image
    image.disable_undo()
    ncolors = pdb.gimp_palette_get_info(palettename)
    names = [pdb.gimp_palette_entry_get_name(palettename, i) for i in range(ncolors)]
    parasite = gimp.Parasite(PARASITE_NAME, PARASITE_PERSISTENT, "\n".join(names))
    layer.parasite_attach(parasite)
    image.enable_undo()

def _read_names(layer):
    ncolors = layer.width * layer.height
    p = layer.parasite_find(PARASITE_NAME)
    if not p:
        return (['Untitled'] * ncolors)
    names = p.data.splitlines()
    if len(names) < ncolors:
        # always provide the same number of names as there are colors.
        names.extend(['Untitled'] * (ncolors - len(names)))
    
    return names

def _read_colors(layer):
    image = layer.image
    colors = []
    if image.base_type != INDEXED:
        for y in range(layer.height):
            for x in range(layer.width):
                # rgba or rgb format?
                colors.append(layer.get_pixel(x, y))
    else:
        colormap = []
        for j in range(len(image.colormap) / 3):
            r, g, b = image.colormap[j * 3:j * 3 + 3]
            colors.append((ord(r), ord(g), ord(b), 255))
        for y in range(layer.height):
            for x in range(layer.width):
                colors.append(colormap[layer.get_pixel(x,y)])
    return colors


def _store_colors(palettename, colors, destimg = None):
    from math import sqrt
    w, h = len(colors), 1
    columns = pdb.gimp_palette_get_columns(palettename) or int(sqrt(w))
    if (w % columns) == 0:
        # palette fits exactly in a rectangle
        w, h = columns, w // columns
    else:
        columns = 1
    image = destimg

    layer = None
    if not destimg:
        img_type = INDEXED
        if len(colors) > 256:
            img_type = RGB
        image = pdb.gimp_image_new(w, h , RGB)
    pdb.gimp_image_undo_group_start(image)
    if image.base_type not in (INDEXED, RGB):
        raise ValueError("Cannot write colors to unsupported image type %d" % image.type)
    layer_type = image2layertype[image.base_type]
    layer = pdb.gimp_layer_new(image, w, h, layer_type, palettename, 100, 0)
    pdb.gimp_image_add_layer(image, layer, -1)
    if image.base_type == INDEXED:
        colormap = "".join(['%c%c%c' % color[:-1] for color in colors])
        now_rgb = False
        if image.colormap and (len(image.colormap) + len(colormap)) > (256 * 3):
            # remove any 'start index' parasites on existing images.
            # needs more testing.
            pdb.gimp_image_convert_rgb(image)
            for lyr in image.layers:
                p = lyr.parasite_find(STARTINDEX_PARASITE_NAME)
                if p:
                    lyr.parasite_detach(STARTINDEX_PARASITE_NAME)
            now_rgb = True
        if not now_rgb:
            startindex = 0
            if image.colormap:
                startindex = len(image.colormap) / 3
                image.colormap = image.colormap + colormap
                parasite = gimp.Parasite(STARTINDEX_PARASITE_NAME, PARASITE_PERSISTENT, str(startindex))
                layer.parasite_attach(parasite)
            else:
                image.colormap = colormap
            for i, color in enumerate(colors):
                layer.set_pixel(i % w, i // w, [startindex + i])
    if image.base_type == RGB:
        for i, color in enumerate(colors):
            layer.set_pixel(i % w, i // w, color[:-1])
    if not (layer.width == image.width and layer.height == image.height):
        miny = 0
        for thislayer in image.layers:
            if thislayer == layer or thislayer == image.layers[-1]:
                continue
            miny = max (miny, thislayer.offsets[1] + thislayer.height)
        pdb.gimp_layer_set_offsets(layer, 0, miny)
    pdb.gimp_image_resize_to_layers(image)
    pdb.gimp_image_undo_group_end(image)
    return image, layer


def palette_to_layer_pixels(palette, dest_image, create_new_image):
    palette = pdb.gimp_context_get_palette()
    colors = pdb.gimp_palette_get_colors(palette)[1]
    if not dest_image:
        create_new_image = True
    image, layer = _store_colors(palette, colors, dest_image if not create_new_image else None)
    _store_names(palette, layer)
#    names = [pdb.gimp_palette_entry_get_name(palette, i) for i in range(len(colors))]
#    parasite = gimp.Parasite(PARASITE_NAME, PARASITE_PERSISTENT, "\n".join(names))
#    layer.parasite_attach(parasite)
    # And attach info about color names, as a parasite.
    if create_new_image:
        pdb.gimp_display_new(image)

def layer_pixels_to_palette(image, layer, mode, palette = None):
    palette = palette or pdb.gimp_context_get_palette()
    name = layer.name.rstrip()
    nentries = layer.width * layer.height
    if nentries > 16384:
        raise ValueError("This layer probably isn't an ordered palette:"
                         " npixels=%d" % (nentries, len(layers)))
    colors = _read_colors(layer)
    names = _read_names(layer)
    if mode == NEW_PALETTE:
        palette = pdb.gimp_palette_new(name)
        columns = min(32, layer.width)
        pdb.gimp_palette_set_columns(palette, columns)
        for c, n in zip(colors, names):
            pdb.gimp_palette_add_entry(palette, n, c)
    elif mode in (OVERWRITE_PALETTE, OVERWRITE_PALETTE_CUSTOM_TARGET):
        if mode != OVERWRITE_PALETTE_CUSTOM_TARGET:
            palette = name
        ncolors = pdb.gimp_palette_get_info(palette)
        if ncolors < nentries:
            for i in range(nentries - ncolors):
                pdb.gimp_palette_add_entry(palette, '_', (0, 0, 0, 0))
        for i, cn in enumerate(zip(colors, names)):
            c, n = cn
            pdb.gimp_palette_entry_set_name(palette, i, n)
            pdb.gimp_palette_entry_set_color(palette, i, c)


def all_layer_pixels_to_palettes(image, drawable, mode):
    if mode == 1:
        mode = OVERWRITE_PALETTE
    for layer in image.layers:
        p = layer.parasite_find(PARASITE_NAME)
        if p:
            layer_pixels_to_palette(layer.image, layer, mode, layer.name)


register(
    proc_name="python-fu-palette-to-layer-pixels",
    blurb="Palette to layer pixels",
    help=("Create a layer from the active palette, with one pixel per entry.\n"
         "\nStores the color names as an layer parasite named %s, with names separated by newlines.") % PARASITE_NAME,
    author="David Gowers",
    copyright="David Gowers",
    date="2012",
    label="Palette to layer pixels",
    imagetypes="",
    params=[(PF_PALETTE, "tpalette", "Palette", "Default"),
            (PF_IMAGE, "image", "Destination _Image", None),
            (PF_BOOL, "create_new_image", "Add to new image", False)],
    results=[],
    function=palette_to_layer_pixels, 
    menu="<Palettes>", 
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-all-layer-pixels-to-palettes",
    blurb="Convert every palette-store layer in the image to pixels",
    help=("Create or replaces the content of ordered palettes, according to all palette-store layers.\n"
         "\nPalette-store layers are layers where there exists a layer parasite named %s, and one pixel in the layer per palette color."
         "\nNote that layer_pixels_to_palette mode 2 (Overwrite custom target palette) is not available.") % PARASITE_NAME,
    author="David Gowers",
    copyright="David Gowers",
    date="2012",
    label="All layer pixels to palettes",
    imagetypes="",
    params=[(PF_IMAGE, "image", "Image", None),
            (PF_LAYER, "drawable", "Drawable", None),
            (PF_OPTION, "Mode", "Transfer mode", 0,
                        (_("New palette (according to layer name)"), 
                         _("Overwrite palette"),
                         )),

            ],
    results=[],
    function=all_layer_pixels_to_palettes,
    menu="<Image>/Image", 
    domain=("gimp20-python", gimp.locale_directory)
    )


register(
    proc_name="python-fu-layer-pixels-to-palette",
    blurb="Layer pixels to palette",
    help=("Create an ordered palette from the active layer.\n"
          "Order is left-to-right, top-to-bottom.\n"
          "Names will be taken from a layer parasite named %s if it exists" % PARASITE_NAME),
    author="David Gowers",
    copyright="David Gowers",
    date=("2012"),
    label=("Layer pixels to palette"),
    imagetypes=(""),
    params=[
            (PF_IMAGE, "Image", "_Image", None),
            (PF_LAYER, "layer", "_Layer", None),
            (PF_OPTION, "Mode", "Transfer mode", 0,
                        (_("New palette (according to layer name)"), 
                         _("Overwrite palette"),
                         _("Overwrite palette(custom target palette)"))),
            (PF_PALETTE, "palette", "Target palette (when mode=Custom Target)", "Default"),
            ],
    results=[],
    function=layer_pixels_to_palette,
    menu=("<Layers>"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
