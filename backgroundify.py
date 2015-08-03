#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

BGCOLOR, PATTERN = 0, 1

def without_group_layers(layerlist):
    """Returns a recursively flattened list of layers.
    Group layers are recursed into but not included in results."""
    layers = []
    for l in layerlist:
        if pdb.gimp_item_is_group(l):
            layers.extend(without_group_layers(l.children))
        else:
            layers.append(l)
    return layers

def backgroundify(image, drawable, fillmode, all_layers):
    all_layers = (all_layers == 1)
    # XXX cope with layer groups (they should be unaffected)
    layers = []
    # drawable is set to None for group layers
    base = [drawable if drawable else image.active_layer]
    if all_layers:
        base = list(image.layers)
    layers = without_group_layers(base)
    pdb.gimp_image_undo_group_start(image)
    bfill_mode = (BG_BUCKET_FILL if fillmode == BGCOLOR else PATTERN_BUCKET_FILL)

    for layer in layers:
        pdb.gimp_edit_bucket_fill_full(layer, bfill_mode, BEHIND_MODE, 100.0, 255.0, 0, 1, 0, 0, 0)

    pdb.gimp_image_undo_group_end(image)

register(
    proc_name="python-fu-backgroundify",
    blurb="Add a background color/pattern to current or all layers.",
    help=("Add a background color/pattern to current or all layers. Note that only the selected area is affected."
          " You may filter only the contents of a given layer group, by having it selected before invoking this filter. "),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("_Backgroundify layer(s)..."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_OPTION, "Fillmode", "_Fill mode", 0,
                        (_("Background Color"), 
                         _("Pattern"))),
            (PF_BOOL, "all_layers", "Apply to _all layers", 0),
            ],
    results=[],
    function=backgroundify,
    menu=("<Image>/Layer/Transparency"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
