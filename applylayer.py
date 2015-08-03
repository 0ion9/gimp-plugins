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

    
def applylayer(image, drawable):
    # ugh, why is drawable usually None????
    if not drawable:
        drawable = image.active_layer
    # 1. Duplicate this layer/group (recursively)
    # 2. Move this down (so it is in the position the non-duplicate was in before)
    # 3. Merge Down the duplicate
    # 4. Clear original layer content
    # 5. Reactivate the original layer
    pdb.gimp_image_undo_group_start(image)
    origindex = pdb.gimp_image_get_item_position(image, drawable)
    sel = None
    if pdb.gimp_selection_bounds(image)[0] != 0:
        sel = pdb.gimp_selection_save(image)
    parent = pdb.gimp_item_get_parent(drawable)
    dupe = pdb.gimp_layer_copy(drawable, 0)
    pdb.gimp_image_insert_layer(image, dupe, parent, origindex+1)
    pdb.gimp_image_merge_down(image, dupe, CLIP_TO_BOTTOM_LAYER)
    pdb.gimp_selection_none(image)
    for layer in _item_get_clearable(drawable):
        pdb.gimp_edit_clear(layer)
    if sel:
        pdb.gimp_image_select_item(sel)
        pdb.gimp_item_delete(sel)
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


main()
