#!/usr/bin/env python

from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

class Rect(tuple):
    def __contains__ (self, v):
        return ((self[0] <= v[0]) and (self[2] >= v[0]) and
                (self[1] <= v[1]) and (self[3] >= v[1]))

def split_rectangles_to_layers(image, drawable, copy):
    layer = drawable or image.layers[-1]
    func = (lambda :pdb.gimp_edit_copy(layer)) if copy else (lambda: pdb.gimp_edit_cut(layer))
    known_rects = []
    sel = image.selection
    pdb.gimp_progress_init("Detecting rectangles", None)
    for y in range(layer.offsets[1], layer.offsets[1] + layer.height):
        for x in range(layer.offsets[0], layer.offsets[0] + layer.width):
           pair = (x,y)
           # no overlaps, no immediate adjacencies.
           if any(pair in r for r in known_rects) or any((x-1,y) in r for r in known_rects) or any((x,y-1) in r for r in known_rects) or any((x+1,y) in r for r in known_rects) or any((x,y+1) in r for r in known_rects):
               continue
           # SLOW
           px = sel.get_pixel(x,y)[0]
           if px != 0:
               x1, y1 = x, y
               px2 = 0
               exit = False
               for y2 in range(y1, layer.offsets[1] + layer.height):
                  px2 = sel.get_pixel(x1,y2)[0]
                  
                  if px2 == 0:
                      exit = True
                      y2 -= 1
                  for x2 in range(x1, layer.offsets[0] + layer.width):
                      pair2 = (x2,y2)
                      if any(pair2 in r for r in known_rects):
                          break
                      px2 = sel.get_pixel(x2,y2)[0]
                      if px2 == 0:
                          x2 -= 1
                          break
                  if exit:
                      break
               known_rects.append(Rect((x,y, x2, y2)))
        row = y - layer.offsets[1]
        pdb.gimp_progress_update(.9 * (row / float(layer.height)))
    pdb.gimp_image_undo_group_start(image)
    pdb.gimp_context_set_feather(0)
    nrects = float(len(known_rects))
    for i, rect in enumerate(known_rects):
        pdb.gimp_progress_set_text('Extracting #%d rect: %r' % (i, rect))
        print('Extracting #%d rect: %r' % (i, rect))
        pdb.gimp_image_select_rectangle(image, 2, rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
        if copy:
            pdb.gimp_edit_copy(layer)
        else:
            pdb.gimp_edit_cut(layer)
        fsel=pdb.gimp_edit_paste(layer, 0)
        pdb.gimp_floating_sel_to_layer(fsel)
        image.layers[0].name = 'Rect #%d' % i
        pdb.gimp_progress_update(.9 + (.1 * (i/nrects)))
    
    pdb.gimp_progress_end()
    pdb.gimp_image_undo_group_end(image)

register(
    proc_name="python-fu-split-rectangles-to-layers",
    blurb="Split non-overlapping rectangles in the selection into separate layers.",
    help=("xyz"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2012"),
    label=("Rectangle selections to layers"),
    imagetypes=(""),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_BOOL, "copy", "_Copy rather than cut", 0),
            ],
    results=[],
    function=split_rectangles_to_layers,
    menu=("<Image>/Select/"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
