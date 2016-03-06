GIMP-Python plugins
====================

This repository contains GIMP-Python plugins. 

Assuming you have a working GIMP (2.8+) with Python support,
you can install them by simply copying them to your GIMP plug-ins directory. The files INSTALL / INSTALL.txt contain more details.

Plugin synopses
================

* *applylayer* : Iteratively 'apply paint' - merges down the content in a layer/group and then clears the content in it (without actually removing the layers themselves)
* *backgroundify* : Add a background color/pattern to (part of) one or all layers. Also, quickly add a layer with given name + mode + opacity.
* *copynaut* : Fast interface to automatically-named GIMP Named Buffers, for collaging. Quickly accumulate a set of clippings and then dispense them. Also a similar interface to quickly export the selected area, or a set of areas, to file.
* *generate_colorband* : Color analysis. Attempts to find and intelligently group N colors representing the layer, producing a 'color band' similar to the output of Smooth Palette. Really SLOW.
* *palette_to_layer_pixels* : Allows editing palettes via image color operators like Curves, by.. transferring them into and out of layers.
* *sel2path* : High quality selection->path conversion via PoTrace. Typically much more accurate than GIMP's built in Selection To Path function, which uses AutoTrace instead.
* *select_layers* : 'Grep' for layers. Removes layers that do/don't match a glob or Python regexp pattern, or intersect with the selection mask.
* *split_rectangles* : Given an input layer containing isolated rectangular areas within a transparent 'sea', extract all such rectangles as layers. Slow.
