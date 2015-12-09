#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

BGCOLOR, PATTERN = 0, 1
MODES = (
 (_('Normal'), NORMAL_MODE),
 (_('Dissolve'), DISSOLVE_MODE),
 (_('Lighten only'), LIGHTEN_ONLY_MODE),
 (_('Screen'), SCREEN_MODE),
 (_('Dodge'), DODGE_MODE),
 (_('Addition'), ADDITION_MODE),
 (_('Darken Only'), DARKEN_ONLY_MODE),
 (_('Multiply'), MULTIPLY_MODE),
 (_('Burn'), BURN_MODE),
 (_('Overlay'), OVERLAY_MODE),
 (_('Soft Light'), SOFTLIGHT_MODE),
 (_('Hard Light'), HARDLIGHT_MODE),
 (_('Difference'), DIFFERENCE_MODE),
 (_('Subtract'), SUBTRACT_MODE),
 (_('Grain Extract'), GRAIN_EXTRACT_MODE),
 (_('Grain Merge'), GRAIN_MERGE_MODE),
 (_('Divide'), DIVIDE_MODE),
 (_('Hue'), HUE_MODE),
 (_('Saturation'), SATURATION_MODE),
 (_('Color'), COLOR_MODE),
 (_('Value'), VALUE_MODE),
 (_('Behind(?)'), BEHIND_MODE),
)
MODELIST = tuple(v[0] for v in MODES)

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

def new_layer(image, drawable, name, mode, opacity, alpha):
    pdb.gimp_image_undo_group_start(image)
    layertype = image.layers[0].type
    mode = MODES[mode][-1]
    layer = pdb.gimp_layer_new(image, image.width, image.height, layertype, name, opacity, mode)
    pdb.gimp_drawable_fill(layer, WHITE_FILL)
    pdb.gimp_image_insert_layer(image, layer, None, -1)
    if alpha:
        pdb.gimp_layer_add_alpha(layer)
#    else:
#        pdb.gimp_layer_remove_alpha(layer)
    pdb.gimp_image_undo_group_end(image)

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

register(
    proc_name="python-fu-new-layer",
    blurb="Quickly create a new image-sized layer with specified mode and opacity",
    help=("..."),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("_New Layer(quick)..."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_STRING, "name", "_Name", "Layer"),
            (PF_OPTION, "mode", "_Blending mode", 0,
                        MODELIST),
            (PF_SLIDER, "opacity", "_Opacity", 100, (0, 100, 1)),
            (PF_BOOL, "alpha", "Alpha channel", 0),
            ],
    results=[],
    function=new_layer,
    menu=("<Image>/Layer/Stack"),
    domain=("gimp20-python", gimp.locale_directory)
    )



main()
