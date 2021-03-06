#!/usr/bin/env python

import os
from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

def _item_get_clearable(item):
    if not pdb.gimp_item_is_group(item):
        return [item]
    items = []
    for member in item.children:
        items.extend(_item_get_clearable(member))
    return items


# XXX maybe a way to apply only the selected pixels (leaving the others) would be useful?

def applylayer(image, drawable):
    # ugh, why is drawable usually None????
    if not drawable:
        drawable = image.active_layer

    parent = pdb.gimp_item_get_parent(drawable)
    if parent and len(parent.children) == 1:
        # don't try to merge down when there is no layer below to merge onto.
        pdb.gimp_message("Won't apply paint from layer %r, no layer below to apply paint to." % drawable.name)
        return
    pdb.gimp_image_undo_group_start(image)
    origindex = pdb.gimp_image_get_item_position(image, drawable)
    sel = None
    if pdb.gimp_selection_bounds(image)[0] != 0:
        sel = pdb.gimp_selection_save(image)
    hadlayermask = drawable.mask
    # Masks have to be applied before the merge->duplicate process can work correctly
    if hadlayermask:
        pdb.gimp_layer_apply_mask(drawable, MASK_APPLY)
    dupe = pdb.gimp_layer_copy(drawable, 0)
    pdb.gimp_image_insert_layer(image, dupe, parent, origindex+1)
    if hadlayermask:
        pdb.gimp_layer_create_mask(dupe, ADD_WHITE_MASK)
    image.merge_down(dupe, CLIP_TO_BOTTOM_LAYER)
    pdb.gimp_selection_none(image)
    for layer in _item_get_clearable(drawable):
        pdb.gimp_edit_clear(layer)
    if sel:
        pdb.gimp_image_select_item(sel)
        pdb.gimp_item_delete(sel)
    image.active_layer = drawable
    pdb.gimp_image_undo_group_end(image)

def applyparentlayer(image, drawable):
    pdb.gimp_image_undo_group_start(image)
    if not drawable:
        drawable = image.active_layer
    parent = pdb.gimp_item_get_parent(drawable)
    if parent:
        applylayer(image, parent)
    image.active_layer = drawable
    pdb.gimp_image_undo_group_end(image)

def applygrandparentlayer(image, drawable):
    pdb.gimp_image_undo_group_start(image)
    if not drawable:
        drawable = image.active_layer
    parent = pdb.gimp_item_get_parent(drawable)
    if parent:
        applyparentlayer(image, parent)
    image.active_layer = drawable
    pdb.gimp_image_undo_group_end(image)

def wraplayer(image, drawable):
    pdb.gimp_image_undo_group_start(image)
    if not drawable:
        drawable = image.active_layer
    parent = pdb.gimp_item_get_parent(drawable)
    origindex = pdb.gimp_image_get_item_position(image, drawable)
    newname = drawable.name + '+'
    group = pdb.gimp_layer_group_new(image)
    pdb.gimp_image_insert_layer(image, group, parent, origindex)
    group.name = newname
    pdb.gimp_image_reorder_item(image, drawable, group, 0)
    image.active_layer = drawable
    pdb.gimp_image_undo_group_end(image)

register(
    proc_name="python-fu-applylayer",
    blurb="Apply Layer (merge all content down, clear all member layers, but do not remove layers)",
    help=".",
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Appl_y"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=applylayer,
    menu=("<Image>/Layer"),
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-applyparentlayer",
    blurb="Apply Parent Layer (merge all content in parent layer down, clear all member layers, but do not remove layers)",
    help=".",
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Apply paren_t"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=applyparentlayer,
    menu=("<Image>/Layer"),
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-applygrandparentlayer",
    blurb="Apply Grandparent Layer (merge all content in grandparent layer down, clear all member layers, but do not remove layers)",
    help=".",
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Apply _Grandparent"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=applygrandparentlayer,
    menu=("<Image>/Layer"),
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-wraplayer",
    blurb="Wrap a layer with a similarly-named layer group.",
    help="Wrap a layer with a similarly-named layer group.",
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("_Wrap with new group"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=wraplayer,
    menu=("<Image>/Layer/Stack"),
    domain=("gimp20-python", gimp.locale_directory)
    )



main()
