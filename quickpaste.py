#!/usr/bin/env python

from gimpfu import *
import os

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)



class Rect(tuple):
    def __contains__ (self, v):
        return ((self[0] <= v[0]) and (self[2] >= v[0]) and
                (self[1] <= v[1]) and (self[3] >= v[1]))

# Plan:
#
# * qpaste: customizable base dir
# * qview: customizable base dir + viewer, support viewing groups
# * subexport: new cmd, export layer or all layers in a group to appropriate files
#   * avoid multiply-exporting clones.
# * subimport: new cmd, revert layer or all layers in a group to appropriate files.
#   * avoid multiply-importing clones.
#   * preserve parasite data

def subexport(image, drawable):
    pass

def quick_paste(image, drawable):
    from subprocess import check_output
    print('reading clipboard')
    out = check_output(['xsel','-b','-o']).decode('utf8')
    lines = out.splitlines()
    print('-> %r' % lines)
    pdb.gimp_image_undo_group_start(image)
    for line in lines:
        out = line.replace('file://','')
        print('-> %r' % out)
        if out.startswith('http') or (os.path.exists(out) and os.path.isfile(out)):
            print ('attempting to load %r' % out)
            layer = pdb.gimp_file_load_layer(image, out)
            print ('inserting')
            pdb.gimp_image_insert_layer(image, layer, None, 0)
            print ('setting name = %r' % os.path.relpath(out, '/media/k_exthd/xraciha_mar/'))
            layer.name = os.path.relpath(out,'/media/k_exthd/xraciha_mar/')
    pdb.gimp_image_undo_group_end(image)

def quick_view(image, drawable):
    from subprocess import call
    uri = image.active_layer.name
    if uri.startswith('file://'):
        uri = uri.replace('file://','')
    if not uri.startswith('/'):
        uri = os.path.join('/media/k_exthd/xraciha_mar/', uri)
    if os.path.exists(uri):
        call(['sxiv',uri])

# XXX also quickview_group, using PDB gimp_item_is_group, gimp_item_get_parent

register(
    proc_name="python-fu-quick-paste",
    blurb="Read 1+ paths from the clipboard content, open the image(s) specified and add it/them to the image.",
    help=("xyz"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2014"),
    label=("_QuickPaste"),
    imagetypes=(""),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            ],
    results=[],
    function=quick_paste,
    menu=("<Image>/File"), 
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-quick-view",
    blurb="Attempt to view the uri specified by the layer name, in sxiv",
    help=("xyz"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2014"),
    label=("_QuickView"),
    imagetypes=(""),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            ],
    results=[],
    function=quick_view,
    menu=("<Image>/Layer"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
