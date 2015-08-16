#!/usr/bin/env python
# Convert Selection to path via potrace
# Requires:
#  * potrace (typical package name on Linux = 'potrace')
#  * plumbum (for Python 2) (typical package name on Linux = 'python-potrace' or 'python2-potrace')
#    If your distro supports both Python2 and Python3, make sure that the package you are installing is for Python2.

from gimpfu import *
from plumbum.cmd import potrace

gettext.install("gimp20-python", gimp.locale_directory, unicode=True)

POSTSTEP_NO, POSTSTEP_TOSEL = 0, 1
POSTSTEP_MAX = POSTSTEP_TOSEL

def _potrace_add_args(cmd, turdsize, smoothness, optimizecurves, optimtolerance, quantize):
#    print ('ARGS:', cmd, turdsize, smoothness, optimizecurves, optimtolerance, quantize)
    cmd = cmd['--turdsize', str(turdsize), '--alphamax', str(smoothness)]
    if not optimizecurves:
        cmd = cmd['--longcurve']
    else:
        cmd = cmd['--opttolerance', '%.3f' % optimtolerance]
    cmd = cmd['-u', str(quantize)]
#    print ('cmd', cmd)
    return cmd

def potraceit(image, drawable, turdsize, smoothness, optimizecurves,
              optimtolerance, quantize, poststep, aa, feathering, 
              featherrad):
    import tempfile
    pdb.gimp_image_undo_group_start(image)
    with tempfile.NamedTemporaryFile(prefix='potg') as f:
        pdb.file_pgm_save(image, image.selection, f.name, f.name, 1)
        # white regions in selectionmask == selected,
        # whereas potrace traces black regions.
        cmd = potrace['-b', 'gimppath', '-i', f.name, '-o', '-', '--invert']
        cmd = _potrace_add_args(cmd, turdsize, smoothness, optimizecurves, optimtolerance, quantize)
        output = cmd()
        # ugh. Potential 'utf8 character size != byte size' issues here.
        # As long as potrace doesn't output any non-ascii characters it'll be ok.
        pdb.gimp_vectors_import_from_string(image, output, len(output), True, True)
        f.close()
    if poststep == POSTSTEP_TOSEL:
        pdb.gimp_context_push()
        pdb.gimp_context_set_antialias(aa)
        pdb.gimp_context_set_feather(feathering)
        pdb.gimp_context_set_feather_radius(featherrad, featherrad)
        pdb.gimp_image_select_item(image, CHANNEL_OP_REPLACE, image.vectors[0])
        pdb.gimp_context_pop()
    # XXX support merging with the previous active vectors?
    elif not (POSTSTEP_NO <= poststep <= POSTSTEP_MAX):
        raise RuntimeError('Unrecognized postprocessing id %r' % poststep)
    pdb.gimp_image_undo_group_end(image)

register(
    proc_name="python-fu-selection-to-path",
    blurb="Potrace the selection, producing a clean SVG path",
    help=("Generally produces much cleaner results than autotrace (the algorithm implemented internally in GIMP)"),
    author="David Gowers",
    copyright="David Gowers",
    date=("2015"),
    label=("_Potrace..."),
    imagetypes=("*"),
    params=[
            (PF_IMAGE, "image", "_Image", None),
            (PF_LAYER, "drawable", "_Drawable", None),
            (PF_INT, "turdsize", "Noise removal scale", 1),
            (PF_FLOAT, "smoothness", "Smoothness (0..1.4)", 0.9),
            (PF_BOOL, "optimizecurves", "Optimize long curves", True),
            (PF_FLOAT, "optimtolerance", "Optimization tolerance", 0.2),
            (PF_INT, "quantize", "Quantization (1/Nth of a pixel)", 10),
            (PF_OPTION, "poststep", "After importing path, take action:", 0,
            (_('Nothing'),
             _('Load into selection')
            )),
            (PF_BOOL, "aa", "Post: _Antialias", True),
            (PF_BOOL, "feather", "Post: _Feather", False),
            (PF_FLOAT, "featherrad", "Post: Feather _Radius", 5.0)
            ],
    results=[],
    function=potraceit,
    menu=("<Image>/Select"), 
    domain=("gimp20-python", gimp.locale_directory)
    )


main()
