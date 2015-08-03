#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

def tmsutag(image, drawable):
    filename = image.filename
    if not filename:
        return # currently only tag xcfs, I think.. anyway, we obviously can't tag a file that isn't saved to disk yet.
    from subprocess import call
    call(['tag','+',filename])
    # XXX maybe force regen of fingerprint?

register(
    proc_name="python-fu-tmsutags",
    blurb="Invoke interactive TMSU tagger for this document.",
    help=("fill in later"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("_Tag..."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            ],
    results=[],
    function=tmsutag,
    menu=("<Image>/Edit"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
