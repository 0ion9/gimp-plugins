#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

KEEP, DISCARD = 0, 1
SHELL, REGEX = 0, 1
RENAME, IGNORE = 0, 1
PRI_RNS, PRI_NRS, PRI_SRN, PRI_NSR = 0, 1, 2, 3
ACTIVEGROUP, ALL = 0, 1

def _tosort(layerlist, parent = None, depth = 0):
    """Returns a list of lists of layers to sort, depth-first"""
    layers = []
    thisgroup = []
    for l in layerlist:
        if pdb.gimp_item_is_group(l):
            layers.extend(_tosort(l.children, l, depth + 1))
        else:
            thisgroup.append(l)
    layers.append((depth, parent, list(thisgroup)))
    layers.sort(key=lambda k: k[0], reverse=True)
    return layers


def _applysort(image, layers):
    for l in reversed(layers):
        print('L=', l)
        pdb.gimp_image_raise_item_to_top(image, l)


def _affected_layers(image, scope):
    if scope == ACTIVEGROUP:
        if not pdb.gimp_item_is_group(image.active_layer):
            return []
        layers = _tosort(image.active_layer.children, image.active_layer)
    else:
        layers = _tosort(image.layers, None)
    return layers



def matches(drawable,  pattern, custom):
    """Returns whether drawable matches the filter.
    
    Parameters
    -----------
    drawable   drawable to be checked
    pattern    compiled regexp
    custom     compiled CustomMatch object, specifying other criteria like layer mode, alpha channelness or opacity
    """
    if not pattern.match(drawable.name):
        return False
#    if not custom.matches(drawable):
#        return False
    return True
    

def compile_pattern(patterntype, pattern):
    import re
    if patterntype == SHELL:
        import fnmatch
        pattern = fnmatch.translate(pattern)
    pattern = re.compile(pattern)
    return pattern

_sort_key = {
    PRI_RNS: (0, 1, 2),
    PRI_NRS: (1, 0, 2),
    PRI_SRN: (2, 0, 1),
    PRI_NSR: (1, 2, 0),
    }


def sort_key(priority, *args):
    return tuple([args[v] for v in _sort_key[priority]])

#XXX select_channels?

# Custom criteria aren't implemented yet.
def select_layers(image, drawable, action, patterntype, pattern): #, custom):
    import re
    pdb.gimp_image_undo_group_start(image)
    old = list(image.layers)
    pattern = compile_pattern(patterntype, pattern)
    for l in old:
        m = matches(l, pattern, None)
        if action == DISCARD:
            m = not m
        if m is not True:
            image.remove_layer(l)
    
    pdb.gimp_progress_end()
    pdb.gimp_image_undo_group_end(image)

# this one is intended more for automation.
def rename_layers(image, drawable, action, patterntype, pattern, separator, names, topdown):
    if not drawable:
        pdb.gimp_message('HELLO!?!?!')
    names = names.strip().split(separator)
    pattern = compile_pattern(patterntype, pattern)
    matching_layers = []
    for l in image.layers:
        m = matches(l, pattern, None)
        if action == IGNORE:
            m = not m
        if m:
            matching_layers.append(l)
    if len(names) != len(matching_layers):
        pdb.message('not proceeding with rename, number of names is different from number of matching layers.')
        return
    pdb.gimp_image_undo_group_start(image)
    if not topdown:
        matching_layers.reverse()
    for l, name in zip(matching_layers, names):
        l.name = name
    pdb.gimp_image_undo_group_end(image)


def sort_layers(image, drawable, scope, patterntype, pattern, priority, reverse):
    if not drawable:
        drawable = image.active_drawable
    pattern = compile_pattern(patterntype, pattern)
    # scope is either 'current group' or 'entire image'
    todo = _affected_layers(image, scope)
    pdb.gimp_image_undo_group_start(image)
    for depth, parent, layers in todo:
        presort = [(l, sort_key(priority, pattern.findall(l.name), l.name, l.width * l.height)) for l in layers]
        _applysort(image, [l for l, key in sorted(presort, reverse=reverse)])
    pdb.gimp_image_undo_group_end(image)

def swap_names(image, drawable, otherlayer):
    if not drawable:
        pdb.gimp_message('HELLO!?!?!')
    if drawable == otherlayer:
        return
    pdb.gimp_image_undo_group_start(image)
    name1 = drawable.name
    name2 = otherlayer.name
    drawable.name = '______TEMP'
    otherlayer.name = name1
    drawable.name = name2
    pdb.gimp_image_undo_group_end(image)


# XXX support changing visibility and locked state etc too (action=chain, etc)
register(
    proc_name="python-fu-select-layers",
    blurb="Remove/keep layers that do / don't conform to a specified criteria",
    help=("Remove/keep layers that do / don't conform to a specified criteria"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Select Layers.."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_OPTION, "action", "Action:", 0,
              (_("Keep"),
               _("Discard"))),
            (PF_OPTION, "patterntype", "Pattern Type:", 0,
              (_("Shell pattern"),
               _("Python Regexp"))),
            (PF_STRING, "pattern", "Pattern:", "*"),
            ],
    results=[],
    function=select_layers,
    menu=("<Image>/Layer/"),
    domain=("gimp20-python", gimp.locale_directory)
    )


register(
    proc_name="python-fu-rename-layers",
    blurb="Rename layers that do / don't conform to a specified criteria",
    help=("Rename layers that do / don't conform to a specified criteria"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Rename Layers.."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_OPTION, "action", "Action", 0,
              (_("Rename"),
               _("Ignore"))),
            (PF_OPTION, "patterntype", "Pattern Type:", 0,
              (_("Shell pattern"),
               _("Python Regexp"))),
            (PF_STRING, "pattern", "Pattern", "*"),
            (PF_STRING, "separator", "Separator character", ","),
            (PF_STRING, "names", "Names", ","),
            (PF_BOOL, "topdown", "Top-down", 1),
            ],
    results=[],
    function=rename_layers,
    menu=("<Image>/Layer/"),
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-sort-layers",
    blurb="Sort layers by name/size/regexp|glob-pattern)",
    help=("Sort layers by name/size/regexp|glob-pattern)"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Sort Layers.."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_OPTION, "scope", "Scope", 0,
              (_("Current group (recursively)"),
               _("All layers (recursively)"))),
            (PF_OPTION, "patterntype", "Pattern Type", 0,
              (_("Shell pattern"),
               _("Python Regexp"))),
            (PF_STRING, "pattern", "Pattern", "*"),
            (PF_OPTION, "priority", "Sort key priority", 0,
              (_("regexp, name, size"),
               _("name, regexp, size"),
               _("size, regexp, name"),
               _("name, size, regexp"))),
            (PF_BOOL, "reverse", "Reverse sort", 1),
            ],
    results=[],
    function=sort_layers,
    menu=("<Image>/Layer/"),
    domain=("gimp20-python", gimp.locale_directory)
    )


register(
    proc_name="python-fu-swap-layer-names",
    blurb="Swap the names of two layers",
    help=("Swap the names of two layers"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Swap layer names.."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image",       "Input image", None),
            (PF_DRAWABLE, "drawable", "Input drawable", None),
            (PF_LAYER, "otherlayer", "_Other layer", None),
            ],
    results=[],
    function=swap_names,
    menu=("<Image>/Layer/"),
    domain=("gimp20-python", gimp.locale_directory)
    )



main()
