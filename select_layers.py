#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

KEEP, DISCARD = 0, 1
SHELL, REGEX = 0, 1


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
    

#XXX select_channels?

# Custom criteria aren't implemented yet.
def select_layers(image, drawable, action, patterntype, pattern): #, custom):
    import re
    pdb.gimp_image_undo_group_start(image)
    old = list(image.layers)
    if patterntype == SHELL:
        import fnmatch
        pattern = fnmatch.translate(pattern)
    pattern = re.compile(pattern)
    for l in old:
        m = matches(l, pattern, None)
        if action == DISCARD:
            m = not m
        if m is not True:
            image.remove_layer(l)
    
    pdb.gimp_progress_end()
    pdb.gimp_image_undo_group_end(image)

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


main()
