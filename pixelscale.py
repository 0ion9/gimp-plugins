#!/usr/bin/env python2

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

def _newsize(oldw, oldh, xfact, yfact):
    return int(round(oldw* xfact)), int(round(oldh * yfact))

def _apply_image(image, xfact, yfact):
    pdb.gimp_image_scale(image, *_newsize(image.width, image.height, xfact, yfact))

def _apply_layer(layer, xfact, yfact):
    pdb.gimp_layer_scale(layer, *((_newsize(layer.width, layer.height, xfact, yfact)) + ( True,)))


# XXX not currently used
def _nn_sampling_matrix(drawable):
    """Guess sampling locations to correctly reduce a (possibly unevenly) NN-upscaled image to 1x scale."""
    #returns two sequences, one for X and one for Y
    # XXX calculate difference from pixel at x - 1 and from y - 1
    # Spots where difference > 0 in both images are virtual-pixel corners
    # Once obvious corners are found by this method,  large runs (eg. if the art is surrounded by blank space) need to be split up into guestimated sampling points.
    # This should be done by using the largest block of fully-determined corners as a pattern.
    # For example, given a run of 34 and a pattern of 3,4,3,4,3,3,4,3,3,4 elsewhere, this latter pattern can be used as guesses of the pixel column/row starts in that
    # 34-run.
    pass

def pixelscale(image, drawable, factor, aspect, reverse, affect):
    xfact = factor
    yfact = factor
    if aspect == 1:
        xfact *= 2
    elif aspect == 2:
        yfact *= 2
    if reverse:
        xfact = 1.0 / xfact
        yfact = 1.0 / yfact
    pdb.gimp_context_push()
    pdb.gimp_context_set_interpolation(INTERPOLATION_NONE)
    pdb.gimp_image_undo_group_start(image)
    func = _apply_layer
    data = [drawable or image.active_layer]
    if affect == 0:
        func = _apply_image
        data = [image]
    elif affect == 2:
        data = image.layers
    elif affect == 3:
        data = [l for layer in image.layers if l.linked]
    for item in data:
        func(item, xfact, yfact)
    pdb.gimp_image_undo_group_end(image)
    pdb.gimp_context_pop()


register(
    proc_name="python-fu-pixelscale",
    blurb="Scale image or layer(s) by an integer factor with nearest-neighbour interpolation",
    help=("Intended to simplify scaling up pixel art for web display."),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Pi_xelScale"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_SLIDER, "factor", "_Scaling factor", 2, (1, 16, 1)),
            (PF_OPTION, "aspect", "Additionally _double", 0, (
             _("Neither W nor H"),
             _("Width"),
             _("Height"))),
            (PF_BOOL, "reverse", "Re_verse operation", False),
            (PF_OPTION, "affect", "_Affect", 0, (
             _("Entire Image"),
             _("Active Layer"),
             _("All Layers"),
             _("Linked Layers"),
            )),
            ],
    results=[],
    function=pixelscale,
    menu=("<Image>/Image"),
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
