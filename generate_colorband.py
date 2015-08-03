#!/usr/bin/env python
# XXX this is coming up with nonsense for 'leaves' image: extra colors are added. Apparently there is one pixel of each.


from gimpfu import *
from collections import Counter

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

maxlevels = 32 # 32**3 colorcube -> 32768 max colors before reduction

# XXX use networkx Graph edge annotations to measure connectivity (aids ramp reconstruction)

def analyze(img, drw, ncolors):
    # we don't use this, we just want to make it error early if it's not present,
    # as it is required later.
    from colormath.color_objects import sRGBColor, LabColor
    from networkx import Graph
    g = Graph()
    index = img.layers.index(drw)
    img = pdb.gimp_image_duplicate(img)
    drw = img.layers[index]
    pdb.gimp_posterize(drw, maxlevels)
    #XXX first scale to a reasonable size.. 512x512?
    maxsize= max(img.width, img.height)
    scale = 1.0 if maxsize <= 256 else 256. / maxsize
    pdb.gimp_image_scale(img, int(scale * img.width), int(scale * img.height))
    pdb.gimp_image_convert_indexed(img, 0, 0, ncolors, 0, 0, '')
    pdb.gimp_image_convert_rgb(img)
    ctr = Counter()
    # XXX we could do this MUCH faster with numpy histograms..
    #     1. read the indexed colormap, for RGB values
    #     2. use histogram functions on entire pixel region, getting an index:amount map in one hit.
    havealpha = True if len(drw.get_pixel(0,0)) == 4 else False
    maxx = img.width - 1
    maxy = img.height - 1
    for y in range(img.height):
        for x in range(img.width):
            color=drw.get_pixel(x,y)
            if havealpha and color[-1] == 0:
                continue
            color=color[:3] # remove alpha channel
            for x2,y2 in ((x+1,y),(x,y+1),(x+1,y+1)):
                if x2 > maxx or y2 > maxy:
                    continue
                c = drw.get_pixel(x2,y2)[:3]
                g.add_edge(color, c, w = 1 if (c not in g or color not in g or color not in g[c]) else g[color][c]['w'] + 1)

            ctr[color] += 1
    pdb.gimp_image_delete(img)
        
    return ctr, g

def graph_to_ramps(g, ctr, searchtime = 256):
    from colormath.color_objects import sRGBColor, LabColor, HSLColor
    from colormath.color_conversions import convert_color
    print (len(g.nodes()))
    import math
    import random
    bestfits = {}
    for color in g.nodes():
        best = None
        bestw = 0
        for k in g[color].keys():
            if g[color][k]['w'] > bestw:
                best = k
                bestw = g[color][k]['w']
        bestfits[color] = best
    # now try to sort monotonically -- for example a black color shouldn't follow a white.
    # the main problem here is that all nodes in the graph are connected, with some degree of separation, to another.
    # perhaps we should just try to visualize this instead (blob size == usage, edge width == degree of relation to another color.)
    #
    #
    # ..  or try this: put all the colors in, in order of brightness. now do several rounds of swapping, trying to minimize graph disturbance
    #     (ie. if there are three colors in sequence A B C, and you want to swap D for B, A-B weight must be less than the average of A-D and C-D weight 
    ramps = list(g.nodes())
#    ramps.sort(key = lambda v: sRGBColor(*v).convert_to('lab').lab_l)
    ramps.sort(key = lambda v: (ctr[v], convert_color(sRGBColor(*v), LabColor).lab_l))
    nswapsleft = int(math.sqrt(len(ramps))) * len(ramps) * searchtime
    while nswapsleft:
        # swap from:
        b = random.randint(0, len(ramps) - 1)
        a = b if b == 0 else (b - 1)
        c = b if b == (len(ramps) - 1) else (b + 1)
        # avoid picking immediate neighbours to swap with
        tmp = list(range(0,len(ramps)))
        tb = b
        if b > 0:
            tmp.pop(tb-1)
            tb -= 1
        if b < (len(ramps) - 1):
            tmp.pop(tb+1)
        tmp.pop(tb)
        # XXX will fail on sufficiently small palettes (4 color)
        d = random.choice(tmp)
        da = d if d == 0 else (d - 1)
        dc = d if d == (len(ramps) - 1) else (d + 1)
        existingbw = (g[ramps[a]].get(ramps[b], {'w':0})['w'] + g[ramps[c]].get(ramps[b], {'w':0})['w']) / 2.0
        existingdw = (g[ramps[d]].get(ramps[da], {'w':0})['w'] + g[ramps[c]].get(ramps[dc], {'w':0})['w']) / 2.0
        neww = (g[ramps[a]].get(ramps[d], {'w':0})['w'] + g[ramps[c]].get(ramps[d], {'w':0})['w']) / 2.0
        # add weighting by pixel count
        existingbw *= (ctr[ramps[a]] * ctr[ramps[b]] * ctr[ramps[c]])
        existingdw *= (ctr[ramps[da]] * ctr[ramps[d]] * ctr[ramps[dc]])
        neww *= (ctr[ramps[a]] * ctr[ramps[d]] * ctr[ramps[c]])
        
        # add weighting by hue diff (saturation gets 20% weight (360 * .2 = 72)
        # overall, the maximum possible downweighting is to 1 / ( (359 + 72) / 45 == 9.5 + 1 == 10.5)
        ahsl = convert_color(sRGBColor(*ramps[a]), HSLColor)
        bhsl = convert_color(sRGBColor(*ramps[b]), HSLColor)
        chsl = convert_color(sRGBColor(*ramps[c]), HSLColor)
        dhsl = convert_color(sRGBColor(*ramps[d]), HSLColor)
        dahsl = convert_color(sRGBColor(*ramps[da]), HSLColor)
        dchsl = convert_color(sRGBColor(*ramps[dc]), HSLColor)
        abdiff = abs(ahsl.hsl_h - bhsl.hsl_h) + (abs(ahsl.hsl_s - bhsl.hsl_s) * 72. )
        bcdiff = abs(bhsl.hsl_h - chsl.hsl_h) + (abs(bhsl.hsl_s - chsl.hsl_s) * 72. )
        ddadiff = abs(dhsl.hsl_h - dahsl.hsl_h) + (abs(dhsl.hsl_s - dahsl.hsl_s) * 72. )
        ddcdiff = abs(dhsl.hsl_h - dchsl.hsl_h) + (abs(dhsl.hsl_s - dchsl.hsl_s) * 72. )
        dadiff = abs(dhsl.hsl_h - ahsl.hsl_h) + (abs(dhsl.hsl_s - ahsl.hsl_s) * 72. )
        dcdiff = abs(dhsl.hsl_h - chsl.hsl_h) + (abs(dhsl.hsl_s - chsl.hsl_s) * 72. )
        # 0..360 -> 0..8 (increased difference reduces weight by a factor of up to 9)
        abdiff /= 45; bcdiff /= 45; ddadiff /= 45; ddcdiff /= 45; dadiff /= 45; dcdiff /= 45
        abdiff += 1.0; bcdiff += 1.0; ddadiff += 1.0; ddcdiff += 1.0; dadiff += 1.0; dcdiff += 1.0
        existingbw *= 1./abdiff
        existingbw *= 1./bcdiff
        existingdw *= 1./ddadiff
        existingdw *= 1./ddcdiff
        neww *= 1./dadiff
        neww *= 1./dcdiff
        if max(existingbw, existingdw, neww) == neww:
            # do swap
            x = ramps[b]
            y = ramps[d]
            ramps[b] = y
            ramps[d] = x
        nswapsleft -= 1
    return ramps

def norm(ctr):
    maxv = max(ctr.values());
    fac = min(40, maxv / min(ctr.values()))
    _norm = Counter({k:int(round(max((v/float(maxv)) * fac, 1))) for k,v in ctr.items()})
    return _norm

def render(ctr, ncolors, scale, ordered):
    print (ctr)
#    from colormath.color_objects import sRGBColor
    # detect grayscale / tone scale -- 30 shades 
#    tonetest = set (int(sRGBColor(*v[0]).convert_to('lab').lab_l / 100.0 * ncolors) for v in ctr.items())
#    print (tonetest)
#    if len(tonetest) == len(ctr):
#        print ("Tone detected")
#        ordered = sorted(ctr.items(), key = lambda v:sRGBColor(*v[0]).convert_to('lab').lab_l)
#    else:
#        #sort by approximate hue, then by l.
#        ordered = sorted(ctr.items(), key = lambda v:(int(sRGBColor(*v[0]).convert_to('hsl').hsl_h / 20.0), sRGBColor(*v[0]).convert_to('lab').lab_l))
#        # ideally we would use k-means to find 18 'hue clusters' rather than just roughly quantizing here.
#    print('')
#    print(ordered)
#    
#    ramps = graph_to_ramps(graph)
#    ordered = [(v, ctr[v]) for v in ramps]
#
#    print(ordered)
    
    width = sum(v[1] for v in ordered)
    layertype = RGB_IMAGE if len(ordered[0][0]) == 3 else RGBA_IMAGE
    image = pdb.gimp_image_new(width, 1 , RGB)
    pdb.gimp_image_undo_group_start(image)
    # X add new layer with given width
    layer = pdb.gimp_layer_new(image, width, 1, layertype, 'color analysis', 100, 0)
    pdb.gimp_image_add_layer(image, layer, -1)
    index = 0
    for col, n in ordered:
        for i in range(n):
#            print(index, 1, col)
            layer.set_pixel(index, 0, col)
            index+=1
    pdb.gimp_image_scale(image, image.width*scale, 32*scale)
    pdb.gimp_image_undo_group_end(image)
    return image

def colorband (image, drawable, ncolors, scale):
    print ('bar', image, 'foo', drawable)
    ctr, graph = analyze (image, drawable, ncolors)
    normalized = norm(ctr)
    
    ramps = graph_to_ramps(graph, normalized)
    ordered = [(v, normalized[v]) for v in ramps]
    # create temp image
    tmpi = pdb.gimp_image_new(len(ordered), 1 , INDEXED)
#    layer = pdb.gimp_layer_new(image, width, 1, INDEXED_IMAGE, 'color analysis', 100, 0)
    tmpi.colormap = "".join("%c%c%c" % v[0] for v in ordered)
    cmap = tmpi.colormap
    #heinous hack!
    pdb.plug_in_colormap_remap(tmpi, drawable, len(cmap) / 3, [0] * (len(cmap) / 3), run_mode=0)
    cmap = tmpi.colormap
    
    newordering = [(ord(cmap[i]), ord(cmap[i+1]), ord(cmap[i+2])) for i in range(0,len(cmap), 3)]
    ordered = [(v, normalized[v]) for v in newordering]
    del image
    newimg = render(normalized, ncolors, scale, ordered)
    pdb.gimp_display_new (newimg)
    #XXX bring up a dialog allowing manual reordering
    # similar to 'colormap rearrange'. Hell, we could cheat and actually use colormap rearrange on a temp image. (run_mode = 0)
    #
    # cmap = tmpi.colormap
    # pdb.plug_in_colormap_remap(tmpi, tmpi.layers[0], len(cmap), [0] * (len(cmap) / 3), run_mode=0)
    # cmap = tmpi.colormap
    # newordering = [(int(cmap[i]), int(cmap[i+1]), int(cmap[i+2])) for i in range(0,len(cmap), 3)]
    # 


register(
    proc_name="python-fu-create-colorband",
    blurb="Generate proportionate colorband",
    help="Analyze image color usage, reduce to 16 key colors and create a colorband visualization of the histogram",
    author="David Gowers",
    copyright="David Gowers",
    date="2013",
    label="Generate proportionate colorband",
    imagetypes="*",
    params=[(PF_IMAGE, "image", "image", None),
            (PF_DRAWABLE, "drawable", "drawable", None),
            (PF_INT, "ncolors", "ncolors", 16),
            (PF_INT, "scale", "scale", 1)],
    results=[],
    function=colorband,
    menu="<Image>/Colors/Info",
    domain=("gimp20-python", gimp.locale_directory)
    )

main()
