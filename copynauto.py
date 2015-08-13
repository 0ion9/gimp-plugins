#!/usr/bin/env python
#
#
# XXX 'paste to file and delete' action
#   ... or maybe instead 'copy to file' (ie put into new image, export. Using the same naming template of course.)
#          probably with a interactive (input a simple id string for that clip) and noninteractive variant.


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
#      layerpath_multiple
#                  Equivalent to layerpath if the image contains more than one layer, otherwise
#                  expands to an empty string.
#      basename_layerpath  
#                  Equivalent to {basename}:{layerpath} , unless basename exactly matches layerpath.
#                  In that case, it just expands to the equivalent of {basename}
#      alpha       'A' if the source drawable has an alpha channel, 'A*' if it has a layer mask, '' otherwise
#      type        'RGB', 'Y', or 'I', according to the type of the source drawable
#      nchildren   The number of children of the drawable, if it is a layer group, otherwise ''
#      size        Equivalent to {width}x{height}
#      isize       {source image width}x{source image height}. Note that this refers to the entire image, not the clipping area.
#      width       Width of the source area (NOT drawable width)
#      height      Height of the source area (NOT drawable height)
#      where       Equivalent to [[{isize}+{offsets}]]
#                  if a 'where' tag is found in the name of a buffer that is being pasted, and the image dimensions match this image,
#                  the clipping will be pasted at the specified offsets.
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

BUFFER_NAME_TEMPLATE = '{basename_layerpath} {where}'

# EXPORT_NAME_TEMPLATE is just like BUFFER_NAME_TEMPLATE, except for the
# following :
#
#  * characters are more strictly sanitized - all '/'s become '_'s, for example.
#    By default, shell special characters !#$^&*()[]| are also converted to _'s,
#    as are spaces -- see EXPORTED_NAME_EDITS below.
#  * it should include an extension, which will determine the export file type.
#    .png is recommended, unless you are dealing with truly gigantic clippings.
#    .webp, .jpg, and .ora are also supported.
#    Be aware that .jpg doesn't support alpha channel, and .webp plugin currently doesn't handle alpha channel,
#    so both of these will be flattened during export.
#

EXPORT_NAME_TEMPLATE = '{layerpath_multiple}.png'

# Where to place exported clippings.
# '' or '.' -> current directory.
# This directory will automatically be created if it doesn't exist.
#
# It will usually be a relative path, for example clippings/.
# Though you can set it to an absolute path if you want all your clippings going to the exact same place.
#

EXPORT_DIRECTORY = ''

# MODE should be either LIFO or FIFO.
# In LIFO mode, the last item you copied is the first to be pasted (the 'queue' empties from the end)
# In FIFO mode, the first item you copied is the first to be pasted (the 'queue' empties from the start)

MODE = LIFO

# PASTED_NAME_EDITS specifies a list of (python_regexp, replacement) pairs that are applied to the name of a pasted buffer before
# setting the layer name.

PASTED_NAME_EDITS = [('\[\[(.+)\]\]', ''),
                     (' +$','')]

EXPORTED_NAME_EDITS = [('\[\[(.+)\]\]', ''),
                      (' +$',''),
                      ('/+','_'),
                      ('[ !#$^&*()[\]|]+','_')]

EXPORT_WEBP_QUALITY = 92
EXPORT_JPG_QUALITY = 92

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
      layerpath_multiple
                  Equivalent to layerpath if the image contains more than one layer, otherwise
                  expands to an empty string.
      basename_layerpath  
                  Equivalent to {basename}:{layerpath} , unless basename exactly matches layerpath.
                  In that case, it just expands to the equivalent of {basename}
      alpha       'A' if the source drawable has an alpha channel, 'A*' if it has a layer mask, '' otherwise
      type        'RGB', 'Y', or 'I', according to the type of the source drawable
      nchildren   The number of children of the drawable, if it is a layer group, otherwise ''
      size        Equivalent to {width}x{height}
      isize       {source image width}x{source image height}. Note that this refers to the entire image, not the clipping area.
      width       Width of the source area (NOT drawable width)
      height      Height of the source area (NOT drawable height)
      where       Equivalent to [[{isize}+{offsets}]]
                  if a 'where' tag is found in the name of a buffer that is being pasted, and the image dimensions match this image,
                  the clipping will be pasted at the specified offsets.
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
    isize = '%dx%d' % (image.width, image.height)
    where = '[[%s+%s]]' % (isize, offsets)
    layerpath_multiple = '' if len(image.layers) == 1 else layerpath
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
                isize=isize,
                where=where,
                width=width,
                height=height,
                size=size,
                offsets=offsets,
                offsetx=offsetx,
                offsety=offsety,
                ismask=ismask,
                layerpath_multiple=layerpath_multiple)
    newtemplate = _subst_preprocess(template, data)
    try:
         return newtemplate.format(**data)
    except error:
         return 'Error expanding %r. Template may be invalid.'

def _apply_regexp_substitutions(s, replacements):
    import re
    final = s
    for src, repl in replacements:
        final = re.sub(src, repl, final)
    return final

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

def _numbered_filename(path, digits=2):
    from itertools import count
    if digits < 1 or digits > 100:
        raise ValueError('Invalid number of digits %r' % digits)
    format = '%0' + str(digits) + 'd'
    if not os.path.exists(path):
        return path
    base, ext = _splitext(path)
    for i in count(1):
        # arbitrary bailout at 16M items, to prevent looping forever (count is an infinite iterator)
        if i >= 0xffffff:
            raise ValueError('Reached bailout at %d without finding a free filename' % i)
        thistry = base + (format % i) + ext
        if not os.path.exists(thistry):
            return thistry
    raise ValueError('You should never reach this line')


def _dashjoin(lhs, rhs):
    if not rhs:
        return lhs
    if not lhs:
        return rhs
    return '%s-%s' % (lhs.rstrip('-'), rhs.lstrip('-'))

def _export(image, path):
    _, ext = _splitext(path)
    ext = ext.lower()
    params = (image, image.layers[0], path, path)
    if ext == '.png':
        pdb.file_png_save_defaults(*params)
        return True
    elif ext == '.ora':
        pdb.file_openraster_save(*params)
        return True
    elif ext == '.webp':
        pdb.file_webp_save(*params, EXPORT_WEBP_QUALITY)
        return True
    elif ext in ('.jpg','.jpeg'):
        pdb.file_jpg_save(*params, EXPORT_JPG_QUALITY / 100., 0.0, 1, 1, "Exported by Copynaut", 1, 1, 0, 0)
        return True
    return False

def exportn(image, drawable, suffix, visible = False):
    if not drawable:
        drawable = image.active_drawable
    if not image.filename:
        pdb.gimp_message('Image must be saved on disk before exporting clippings.')
        return
    dest = _expand_template(image, drawable, EXPORT_NAME_TEMPLATE)
    dest = _apply_regexp_substitutions(dest, EXPORTED_NAME_EDITS)
    if visible:
        bname = pdb.gimp_edit_named_copy_visible(image, '_' + dest)
    else:
        bname = pdb.gimp_edit_named_copy(drawable, '_' + dest)
    # paste as new image (This doesn't automatically create a view, thankfully)
    newimg = pdb.gimp_edit_named_paste_as_new(bname)
    # XXX perform extra processing -- border or flattening
    #
    # The following code puts parts together as follows:
    #     $EXPORTDIR/$FNAME-$DEST-$SUFFIX$EXT
    #
    # to determine the final export path.
    #
    suffix = _expand_template(image, drawable, suffix)
    suffix = _apply_regexp_substitutions(suffix, EXPORTED_NAME_EDITS)
    destbase, ext = _splitext(dest)
    if destbase.startswith('.'):
        # when dest is eg '.png', because for example layerpath_multiple expands to '' since there is only one layer,
        # this can happen
        #
        # XXX note that this will probably also pick up a normal name that starts with '.', like '.foobar.png'.
        # so don't use names starting with . for now.
        ext = destbase
        destbase = ''
    fnamebase = os.path.splitext(image.filename)[0]
    if not os.path.isabs(EXPORT_DIRECTORY):
        basedir = os.path.join(EXPORT_DIRECTORY, os.path.dirname(fnamebase))
    else:
        basedir = EXPORT_DIRECTORY
    path = os.path.join(basedir, _dashjoin(fnamebase, destbase))
    if suffix:
        path = _dashjoin(path, suffix)
    path = path + ext
    pathdir = os.path.dirname(path)
    if not os.path.exists(pathdir):
        os.makedirs(pathdir)
    # get a filename that doesn't already exist on disk
    path = _numbered_filename(path)
    if os.path.exists(path):
        # now we're using _numbered_filename, this branch should only be entered if there is a race condition
        # (the output file didn't exist when _numbered_filename() ran, but has been created in the meantime)
        pdb.gimp_message('Won\'t overwrite existing image %s' % path)
        pdb.gimp_image_delete(newimg)
        pdb.gimp_buffer_delete(bname)
        return
    e = ext.lower()
    export_ok = _export(newimg, path)
    if not export_ok:
        pdb.gimp_message('%r file format currently not supported!' % e)
    pdb.gimp_image_delete(newimg)
    pdb.gimp_buffer_delete(bname)

def _pastenandremove(image, drawable, mode, pasteinto):
    import re
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
    # detect [[IWIDTHxIHEIGHT+OX,OY]]
    destx, desty = None, None
    srcinfo = re.findall('\[\[([0-9]+)x([0-9]+)+([0-9]+),([0-9]+)\]\]', this)
    if srcinfo:
        _sw, _sh, _sx, _sy = [ int(v) for v in srcinfo[-1]]
        if _sw == image.width and _sh == image.height:
            destx = _sx
            desty = _sy
    print('original buffer name: %r' % this)
    final = _apply_regexp_substitutions(this, PASTED_NAME_EDITS)
    print('final buffer name: %r' % final)
    pdb.gimp_image_undo_group_start(image)
    fsel = pdb.gimp_edit_named_paste(drawable, this, pasteinto)
    pdb.gimp_floating_sel_to_layer(fsel)
    newlayer = image.active_layer
    if destx is not None:
        newlayer.set_offsets(destx, desty)
    pdb.gimp_item_set_name(newlayer, final)
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

register(
    proc_name="python-fu-exportclipping",
    blurb="Export current selection to file",
    help=(""),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("Export _Clipping"),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "image", None),
            (PF_LAYER, "drawable", "drawable", None),
            (PF_STRING, "suffix", "_Suffix", ''),
            (PF_BOOL, "visible", "_Visible", False)
            ],
    results=[],
    function=exportn,
    menu=("<Image>/Edit"),
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
