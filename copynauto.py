#!/usr/bin/env python

## Constants used in configuration (do not modify)

LIFO = 0
FIFO = -1

## Configuration (do modify) ##

# BUFFER_NAME_TEMPLATE determines the naming of the named-buffers created.
#
# The following variable expansions can be used
# (info is taken from the _expand_template docstring below):
#
#      basename    The basename of the file, excluding the extension
#      ext         The extension of the file, including '.'
#                  Includes special handling so that double-extensions like foo.xcf.bz2 are handled correctly
#      path	   The full path to the file, excluding extension.
#      realpath    The full path to the file, excluding extension, with all symlinks resolved.
#      mpixels	   The number of mpixels contained in the buffer, rounded to one decimal place.
#      kpixels	   The number of kpixels contained in the buffer, rounded to one decimal place.
#      layername   The name of the source layer
#      layerpath   The full path to the source layer within the source file,
#                  separated by '/'s.
#                  If the source layer is a layer group, this will end with a '/' character.
#      basename_layerpath  
#                  Equivalent to {basename}:{layerpath} , unless basename exactly matches layerpath.
#                  In that case, it just expands to the equivalent of {basename}
#      alpha       'A' if the source drawable has an alpha channel, 'A*' if it has a layer mask, '' otherwise
#      type        'RGB', 'Y', or 'I', according to the type of the source drawable
#      nchildren   The number of children of the drawable, if it is a layer group, otherwise ''
#      size        Equivalent to {width}x{height}
#      width       Width of the source area (NOT drawable width)
#      height      Height of the source area (NOT drawable height)
#      offsets     Equivalent to {offsetx},{offsety}
#      offsetx     X offset of the drawable in the source image
#      offsety     Y offset of the drawable in the source image
#      ismask      'M' if the source drawable is a layer mask
#
# It is expanded using the standard Python str.format() template, so all str.format() formatting codes are supported.
# It should be noted however that mpixels and kpixels are strings, not floats, so requesting further precision will not work.
#
# Additionally, substitution formatting is supported for string-type variables
# (basename, ext, path, realpath, mpixels, kpixels, layername, layerpath, basename_layerpath, alpha, type,
#  size, offsets, ismask).
#
# Substitution formatting looks like '{basename_layerpath/pattern/replacement}', and is equivalent to 
# basename_layerpath.replace('pattern', 'replacement') in Python terms. 
# Any literal forward slashes ('/') in pattern or replacement must be escaped using /'.
#
# Multiple substitutions may be performed like this: {basename_layerpath/p1/r1/p2/r2/p3/r3}
#
# Note that substitutions are performed left-to-right as they are found. This means, for example, that given basename = 'foobar',
# '{basename/foo/o/o/bar}' results in an output 'barbar' (foobar -> obar -> barbar)
#
#

BUFFER_NAME_TEMPLATE = '{basename_layerpath/e6copy-/e6d-/d/foo}'

# MODE should be either LIFO or FIFO.
# In LIFO mode, the last item you copied is the first to be pasted (the 'queue' empties from the end)
# In FIFO mode, the first item you copied is the first to be pasted (the 'queue' empties from the start)

MODE = LIFO

## configuration ends ##



import os
from gimpfu import *

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

def _splitext(path):
    """os.path.splitext variant that detects single-file-compressor extensions.
    (eg. foo.tar.(gz|bz2|bzip2|xz))
    
    os.path.splitext('foo.tar.gz') returns ('foo.tar', '.gz'), whereas 
    splitext returns ('foo', '.tar.gz')
    """
    directory, basename = os.path.split(path)
    basename, ext = os.path.splitext(basename)
    if '.' in basename and ext in ('.xz','.gz','.bzip2','.bz2'):
        basename, _ext = os.path.splitext(basename)
        ext = _ext + ext
    return os.path.join(directory, basename), ext

def _item_get_hierarchy(item):
    h = [item]
    parent = item
    while parent:
        parent = pdb.gimp_item_get_parent(parent)
        if parent:
            h.insert(0, parent)
    return h
    

def _escape(layername):
    return layername.replace('/','\\/')

def _get_layer_path(item):
    """Return a 'layer path' for the given GimpItem.
    
    Layer paths describe the hierarchy within which a layer resides, in the same way as
    /home/me/myfiles/picture.jpg describes the hierarchy within which picture.jpg resides on your hard drive.
    
    Slashes in layer names are escaped -- a literal '/' becomes '\/'.
    
    The returned path looks like 'LayerGroup/SubGroup/LayerName'
    
    If the given item is a layer group, the returned path will end with /.
    """
    tmp = '/'.join([_escape(v.name) for v in _item_get_hierarchy(item)])
    if pdb.gimp_item_is_group(item):
        tmp = tmp + '/'
    return tmp
    

def _subst_preprocess(format_str, data):
    """Applies replacements specified in format_str to keys in data.
    
    Returns new format string (with non-standard replacement specifiers removed).
    
    Format:
     {SPEC/str/repl[/str/repl...]}
    
    Literal /'s and }'s must be escaped using \.
    """
    replacements = []
    import re
    from itertools import groupby
    def add_repls(match):
        name = match.expand('\\1')
        data = match.expand('\\2')
        data = data.replace('\\}', '}')
        pairs = re.split(r'(?!<[\\])/', data)
        if len(pairs) % 2:
            raise ValueError('Incomplete substitution in %r' % ('%s/%s' % (name, data)))
        for s, r in [list([v2 for k2,v2 in v]) for k, v in  groupby(enumerate(pairs), lambda i: i[0] // 2)]:
            replacements.append((name, s,r))
        return '{%s}' % name
    result = re.sub('[{]([^/]+)/((?:[^}]|\\[}])+)[}]', add_repls, format_str)
    for name, pattern, replacement in replacements:
        data[name] = data[name].replace(pattern, replacement)
    return result


def _expand_template(image, drawable, template):
    """Expand the string template, returning the semi-final name of the buffer
    (*semi*-final because GIMP may still generate a #n suffix if multiple of the name occurs)
    
    Templates may use the following keys:
    
      basename    The basename of the file, excluding the extension
      ext         The extension of the file, including '.'
                  Includes special handling so that double-extensions like foo.xcf.bz2 are handled correctly
      path	  The full path to the file, excluding extension.
      realpath    The full path to the file, excluding extension, with all symlinks resolved.
      mpixels	  The number of mpixels contained in the buffer, rounded to one decimal place.
      kpixels	  The number of kpixels contained in the buffer, rounded to one decimal place.
      layername   The name of the source layer
      layerpath   The full path to the source layer within the source file.
      basename_layerpath  
                  Equivalent to {basename}:{layerpath} , unless basename exactly matches layerpath.
                  In that case, it just expands to the equivalent of {basename}
      alpha       'A' if the source drawable has an alpha channel, 'A*' if it has a layer mask, '' otherwise
      type        'RGB', 'Y', or 'I', according to the type of the source drawable
      nchildren   The number of children of the drawable, if it is a layer group, otherwise ''
      size        Equivalent to {width}x{height}
      width       Width of the source area (NOT drawable width)
      height      Height of the source area (NOT drawable height)
      offsets     Equivalent to {offsetx},{offsety}
      offsetx     X offset of the drawable in the source image
      offsety     Y offset of the drawable in the source image
      ismask      'M' if the source drawable is a layer mask

    
    """
    filename = image.filename or '<none>'
    _basename = os.path.basename(filename)
    layername = drawable.name
    layerpath = _get_layer_path(drawable)
    path, ext = _splitext(filename)
    mpixels = '<you should never see this>'
    kpixels = mpixels
    if 'mpixels' in template or 'kpixels' in template:
         nonempty, x1, y1, x2, y2 = pdb.gimp_drawable_mask_bounds(drawable)
         w = x2 - x1
         h = y2 - y1
         pixels = w * h
         kpixels = '%.1f' % (pixels / 1024.)
         mpixels = '%.1f' % (pixels / 1048576.)
    basename = os.path.basename(path)
    if _basename != layerpath:
         basename_layerpath = basename + ':' + layerpath
    else:
         basename_layerpath = basename
    
    alpha = 'A' if drawable.has_alpha else ''
    if drawable.mask:
        alpha += '*'
    _type = '<unknown type>'
    if drawable.type in (RGB_IMAGE, RGBA_IMAGE):
         _type = 'RGB'
    elif drawable.type in (GRAY_IMAGE, GRAYA_IMAGE):
         _type = 'Y'
    elif drawable.type in (INDEXED_IMAGE, INDEXEDA_IMAGE):
         _type = 'I'
    nchildren = ''
    if pdb.gimp_item_is_group(drawable):
        nchildren = len(drawable.children)
    width = '<you should never see this>'
    height = width
    size = width
    if 'width' in template or 'height' in template or 'size' in template:
        x1, y1, x2, y2 = drawable.mask_bounds
        width = x2 - x1
        height = y2 - y1
        size = '%dx%d' % (width, height)
    offsetx, offsety = drawable.offsets
    offsets = '%d,%d' % (offsetx, offsety)
    ismask = 'M' if drawable.is_layer_mask else ''
    data = dict(path=path, 
                ext=ext,
                basename=basename,
                realpath=_splitext(os.path.realpath(filename))[0],
                mpixels=mpixels,
                kpixels=kpixels,
                layername=layername,
                layerpath=layerpath,
                basename_layerpath=basename_layerpath,
                image=image,
                drawable=drawable,
                type=_type,
                alpha=alpha,
                nchildren=nchildren,
                width=width,
                height=height,
                size=size,
                offsets=offsets,
                offsetx=offsetx,
                offsety=offsety,
                ismask=ismask)
    newtemplate = _subst_preprocess(template, data)
    try:
         return newtemplate.format(**data)
    except error:
         return 'Error expanding %r. Template may be invalid.'


def _copyn(image, drawable, visible = False):
    # ugh, why is drawable usually None????
    if not drawable:
        drawable = image.active_drawable
    used = _expand_template(image, drawable, BUFFER_NAME_TEMPLATE)
    print('I,D:', image, drawable)
    if visible:
        pdb.gimp_edit_named_copy_visible(image, used)
    else:
        pdb.gimp_edit_named_copy(drawable, used)


def _pastenandremove(image, drawable, mode, pasteinto):
    # ugh, why is drawable usually None????
    if not drawable:
        drawable = image.active_drawable

    pasteinto = 1 if pasteinto else 0
    # if this is a layer group, pick an arbitrary layer to paste 'onto', we reorder later anyway
    if pdb.gimp_item_is_group(drawable):
        parent = drawable
        drawable = [l for l in image.layers if not pdb.gimp_item_is_group(l)][0]
    else:
        parent = pdb.gimp_item_get_parent(drawable)
    _, buffers = pdb.gimp_buffers_get_list('')
    if not buffers:
        return
    this = buffers[mode]
    pdb.gimp_image_undo_group_start(image)
    fsel = pdb.gimp_edit_named_paste(drawable, this, pasteinto)
    pdb.gimp_floating_sel_to_layer(fsel)
    newlayer = image.active_layer
    pdb.gimp_item_set_name(newlayer, this)
    if parent:
        pdb.gimp_image_reorder_item(image, newlayer, parent, 0)
    pdb.gimp_image_undo_group_end(image)
    pdb.gimp_buffer_delete(this)


def copynauto(image, drawable):
    _copyn(image, drawable)
    
def copynvauto(image, drawable):
    _copyn(image, drawable, True)

def pastenandremove(image, drawable):
    _pastenandremove(image, drawable, MODE, 0)

def pastenallandremove(image, drawable):
    _, buffers = pdb.gimp_buffers_get_list('')
    pdb.gimp_image_undo_group_start(image)
    for i, _ in enumerate(buffers):
        _pastenandremove(image, drawable, MODE, 0)
    pdb.gimp_image_undo_group_end(image)

import sys

pluginfilename = os.path.basename(sys.argv[0])
helpmsg = "Modify %r in your plug-ins directory to configure templating"

register(
    proc_name="python-fu-copynauto",
    blurb="Copy Named, with name generated automatically from template",
    help=helpmsg,
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Cop_y autonamed"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=copynauto,
    menu=("<Image>/Edit/Buffer"), 
    domain=("gimp20-python", gimp.locale_directory)
    )

# XXX untested

register(
    proc_name="python-fu-copynvauto",
    blurb="Copy Named Visible, with name generated automatically from template",
    help=helpmsg,
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Copy autonamed V_isible"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=copynvauto,
    menu=("<Image>/Edit/Buffer"), 
    domain=("gimp20-python", gimp.locale_directory)
    )

register(
    proc_name="python-fu-pastenandremove",
    blurb="Paste latest Named buffer as new layer, and remove it from the list of buffers",
    help=("Note that it currently isn't possible to paste as a new channel."),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Paste Latest Named and _Remove"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=pastenandremove,
    menu=("<Image>/Edit/Buffer"), 
    domain=("gimp20-python", gimp.locale_directory)
    )

# XXX untested

register(
    proc_name="python-fu-pastenallandremove",
    blurb="Paste all Named buffers as new layers, and remove them from the list of buffers.",
    help=("Note that it currently isn't possible to paste as new channels."),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Paste a_ll Named Buffers and Remove"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            ],
    results=[],
    function=pastenallandremove,
    menu=("<Image>/Edit/Buffer"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
