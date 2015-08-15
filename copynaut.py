#!/usr/bin/env python
# Copynaut

## Configuration ##

# BUFFER_NAME_TEMPLATE determines the naming of the named-buffers created.
#
# The following variable expansions can be used
# (info is taken from the _expand_template docstring below):
#
#      basename    The basename of the file, excluding the extension
#      ext         The extension of the file, including '.'
#                  Includes special handling so that double-extensions like foo.xcf.bz2 are handled correctly
#      path        The full path to the file, excluding extension.
#      realpath    The full path to the file, excluding extension, with all symlinks resolved.
#      mpixels     The number of mpixels contained in the buffer, rounded to one decimal place.
#      kpixels     The number of kpixels contained in the buffer, rounded to one decimal place.
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

# EXPORT_NAME_TEMPLATE is just like BUFFER_NAME_TEMPLATE, except for the
# following :
#
#  * characters are more strictly sanitized - all '/'s become '_'s, for example.
#    By default, shell special characters !#$^&*()[]| are also converted to _'s,
#    as are spaces -- see EXPORTED_NAME_EDITS below.
#  * it should include an extension, which will determine the export file type.
#    .png is recommended, unless you are dealing with truly gigantic clippings.
#    .webp, .jpg, and .ora are also supported.
#    Be aware that .jpg doesn't support alpha channel; areas that weren't included in your clipping, but within its bounding box,
#    will show up (since their color is preserved and the alpha is ignored.)
#
#    .webp is currently not recommended as the webp plugin ignores run-mode, which forces you to interact with its dialog every time you do an export.
#    If you use a version of gimp-webp plugin newer than August 14 2015, this bug is fixed (see https://github.com/nathan-osman/gimp-webp/issues/1)
#
#

# EXPORT_DIRECTORY:
# Where to place exported clippings.
# '' or '.' -> current directory.
# This directory will automatically be created if it doesn't exist.
#
# It will usually be a relative path, for example clippings/.
# Though you can set it to an absolute path if you want all your clippings going to the exact same place.
#

# MODE should be either LIFO or FIFO.
# In LIFO mode, the last item you copied is the first to be pasted (the 'queue' empties from the end)
# In FIFO mode, the first item you copied is the first to be pasted (the 'queue' empties from the start)

# PASTED_NAME_EDITS specifies a list of (python_regexp, replacement) pairs that are applied to the name of a pasted buffer before
# setting the layer name.

PASTED_NAME_EDITS = [('00_remove_double_bracketed', ('\[\[(.+)\]\]', '', 0)),
                     ('01_remove_trailing_spaces', (' +$','', 0))]

EXPORTED_NAME_EDITS = [('00_remove_double_bracketed',('\[\[(.+)\]\]', '', 0)),
                      ('01_remove_trailing_spaces', (' +$','', 0)),
                      ('02_slashes_to_underscores', ('/+','_', 0)),
                      ('03_shell_to_underscores', ('[ !#$^&*()[\]|;]+','_', 0))]

## configuration ends ##

import os
import re
from gimpfu import *
from collections import namedtuple

# XXX name edits are not handled via config-file yet
Config = namedtuple('Config', 'stack export')
StackConfig = namedtuple('StackConfig', 'read_index name_template name_edits')
ExportConfig = namedtuple('ExportConfig', 'name_template name_edits directory webp_args jpeg_args')

_DEFAULT_CONFIG = """
[clipping stack]
mode = last-in-first-out
name template = {basename_layerpath} {where}
[clipping name edits]
00_remove_doublebracketed_expressions = ;\[\[(.+)\]\];
01_remove_trailing_spaces = / +$/
[export]
name template = {layerpath_multiple}.png
directory =
webp quality = 92
jpeg quality = 92
[export name edits]
00_remove_doublebracketed_expressions = /\[\[(.+)\]\]/
01_remove_trailing_spaces = / +$/
02_slashes_to_underscore = ;/+;_
03_shellcharacters_to_underscore = ,[ !#$^&*;()[\]|]+,_
"""

_config_cache = None
_re_flagmap = {v.lower(): getattr(re, v) for v in [f for f in dir(re) if (not f == 'T') and len(f) == 1 and f.isupper()]}

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

def _split_regex_replacement(expression):
    """Split a regex-replacement expression into a (regexp, repl, flags) tuple

    Format is based on sed syntax:

    <SEPARATOR>regexp<SEPARATOR>repl[SEPARATOR[flags]]

    SEPARATOR being a single character; If it occurs in regexp, repl,
    or flags, it should be escaped with '\'

    flags include AILMSXU , as described in the 're' module's documentation,
    and also 'G' (which is a no-op, included for sed compatibility).
    They are case-insensitive.
    """
    sep = re.escape(expression[0])
    if sep == '\\':
        raise ValueError('Separator cannot be \\')
    parts = re.split(r'(?<!\\)%s' % sep, expression[1:])
    if len(parts) < 2:
        raise ValueError('Replacement string missing in %r' % expression)
    elif len(parts) > 3:
        raise ValueError('Replacement spec %r not understood')
    regex, replacement = parts[0], parts[1]
    flags = 0
    if len(parts) == 3:
        for flag in parts[-1]:
            flag = flag.upper()
            # basic sed compatibility
            if flag == 'G':
                continue
            try:
                flags |= getattr(re, flag)
            except AttributeError:
                raise ValueError('Unknown regexp flag %r' % flag)
    return (regex, replacement, flags)

# XXX we don't parse regexp replacements from config file yet, still using internal constants.
# XXX we ignore extra_search_path for now.. Might look in same directory
#     as source file, for config file, in the future.

def _serialize_regex_repl(tup):
    regex, repl, flags = tup
    schr = None
    for bestchr in '/;,':
        if not (bestchr in regex or bestchr in repl):
            schr = bestchr
    if not schr:
        sep = 33
        schr = chr(sep)
        while bestchr in regex or bestchr in repl:
            sep += 1
            # can't use backslash
            if sep == 92:
                sep += 1
            if sep > 128:
                break
            schr = chr(sep)
        if sep >= 128:
            raise ValueError('HALP')
    flagchrs = "".join(sorted([c for c, v in _re_flagmap.items() if flags & v]))
    return schr + schr.join([regex, repl, flagchrs])


def _load_config(extra_search_path):
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    # python2 uses 'ConfigParser' module name
    # and has no read_string method
    from ConfigParser import RawConfigParser
    from StringIO import StringIO
    parser = RawConfigParser()
    parser.readfp(StringIO(_DEFAULT_CONFIG))
    parser.read((os.path.join(gimp.directory, 'copynaut', 'config.ini'),))

    c = parser
    cstack = lambda k: c.get('clipping stack', k)
    cexport = lambda k: c.get('export', k)
    s_mode = cstack('mode').lower()
    read_index = None
    if s_mode in ('last-in-first-out', 'lifo'):
        read_index = 0
    elif s_mode in ('first-in-first-out', 'fifo'):
        read_index = -1
    else:
        raise ValueError('Unknown value for clipping stack mode: %r' % s_mode)
    s_template = cstack('name template')
    e_template = cexport('name template')
    e_directory = os.path.expanduser(cexport('directory'))
    e_webp_args = (int(cexport('webp quality')), )
    e_jpeg_args = (float(cexport('jpeg quality')) / 100., 0.0, 1, 1, "Exported by Copynaut", 1, 1, 0, 0 )
    stackc = StackConfig(read_index, s_template, PASTED_NAME_EDITS)
    exportc = ExportConfig(e_template, EXPORTED_NAME_EDITS, e_directory, e_webp_args, e_jpeg_args)
    data = Config(stackc, exportc)
    _config_cache = data
    return _config_cache

def _save_config(cfg, filename):
    c = RawConfigParser()
    cstack = lambda k,v: c.set('clipping stack', k, v)
    cexport = lambda k,v: c.set('export', k, v)
    for k, v in (('webp quality', cfg.export.webp_args),
                 ('jpeg quality', int(cfg.export.jpeg_args * 100)),
                 ('name template', cfg.export.name_template),
                 ('directory', cfg.export.directory)):
        c.set('export', k, v)

    for k, v in (('mode', 'last-in-first-out' if cfg.stack.read_index == 0 else 'first-in-first-out'),
                 ('name template', cfg.stack.name_template)):
        c.set('clipping stack', k, v)

    for k, v in cfg.export.name_edits:
        c.set('export name edits', k, _serialize_regex_repl(v))

    for k, v in cfg.stack.name_edits:
        c.set('clipping name edits', k, _serialize_regex_repl(v))

    c.write(filename)

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
      path    The full path to the file, excluding extension.
      realpath    The full path to the file, excluding extension, with all symlinks resolved.
      mpixels     The number of mpixels contained in the buffer, rounded to one decimal place.
      kpixels     The number of kpixels contained in the buffer, rounded to one decimal place.
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
    for name, v in replacements:
        src, repl, flags = v
        final = re.sub(src, repl, final, flags=flags)
    return final

def _copyn(image, drawable, visible = False):
    # ugh, why is drawable usually None????
    if not drawable:
        drawable = image.active_drawable
    conf = _load_config(image.filename)
    used = _expand_template(image, drawable, conf.stack.name_template)
    print('I,D:', image, drawable)
    if visible:
        pdb.gimp_edit_named_copy_visible(image, used)
    else:
        pdb.gimp_edit_named_copy(drawable, used)

def _numbered_filename(path, digits=2):
    from itertools import count
    if digits < 1 or digits > 100:
        raise ValueError('Invalid number of digits %r' % digits)
    format = '-%0' + str(digits) + 'd'
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
    conf = _load_config(image.filename)
    if ext == '.png':
        pdb.file_png_save_defaults(*params)
        return True
    elif ext == '.ora':
        pdb.file_openraster_save(*params)
        return True
    elif ext == '.webp':
        params = params + conf.export.webp_args
        pdb.file_webp_save(*params)
        return True
    elif ext in ('.jpg','.jpeg'):
        params = params + + conf.export.jpeg_args
        pdb.file_jpeg_save(*params)
        return True
    return False

def exportn(image, drawable, suffix, visible = False):
    if not drawable:
        drawable = image.active_drawable
    if not image.filename:
        pdb.gimp_message('Image must be saved on disk before exporting clippings.')
        return
    conf = _load_config(image.filename)
    dest = _expand_template(image, drawable, conf.export.name_template)
    dest = _apply_regexp_substitutions(dest, conf.export.name_edits)
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
    suffix = _apply_regexp_substitutions(suffix, conf.export.name_edits)
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
    if not os.path.isabs(conf.export.directory):
        basedir = os.path.join(conf.export.directory, os.path.dirname(fnamebase))
    else:
        basedir = conf.export.directory
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

def _pastenandremove(image, drawable, read_index, pasteinto):
    import re
    # ugh, why is drawable usually None????
    if not drawable:
        drawable = image.active_drawable
    conf = _load_config(image.filename)
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
    this = buffers[read_index]
    # detect [[IWIDTHxIHEIGHT+OX,OY]]
    destx, desty = None, None
    srcinfo = re.findall('\[\[([0-9]+)x([0-9]+)+([0-9]+),([0-9]+)\]\]', this)
    if srcinfo:
        _sw, _sh, _sx, _sy = [ int(v) for v in srcinfo[-1]]
        if _sw == image.width and _sh == image.height:
            destx = _sx
            desty = _sy
    print('original buffer name: %r' % this)
    final = _apply_regexp_substitutions(this, conf.stack.name_edits)
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
    conf = _load_config(image.filename)
    _pastenandremove(image, drawable, conf.stack.read_index, 0)

def pastenallandremove(image, drawable):
    _, buffers = pdb.gimp_buffers_get_list('')
    conf = _load_config(image.filename)
    pdb.gimp_image_undo_group_start(image)
    for i, _ in enumerate(buffers):
        _pastenandremove(image, drawable, conf.stack.read_index, 0)
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