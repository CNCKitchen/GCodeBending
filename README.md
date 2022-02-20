# GCodeBending
 This is a quick and dirty Python code to deform GCode so that it follows a defined spline.
# Requirements
- GCode needs to be sliced with relative extrusions activated, preferably in PrusaSlicer
- You need enough clearance around your nozzle to print significant angles
- The model can't be too large in the X dimension, otherwise you'll get self intersections
# Usage
- Place your part preferably in the middle of your print plate with known center X coordinates
- Place the sliced GCode in the same directory as the Python script
- Run `bend_gcode.py` in your Terminal/Command Prompt
    - Run `python3 bend_gcode.py --help` to see the available options (or `py bend_gcode.py --help`)
    - Pass in your gcode file name as the first argument
    - Set `-l` or `--layer_height` to your slicing layer height.
      Important, because you don't set it correctly you'll get under- or over extrusions
    - Set `-a` or `--warning_angle` to the maximum angle your system can print at due to clearances
    - Define your spline with `-x`/`--x_values` and `-z`/`--z_values`, with at least two points.
        - The first x-coordinate should be in the center of your part
        - The first z-coordinate should be 0 (at the print bed)
        - The last z-coordinate should be at or above the highest z-coordinate in your GCode
        - `-b`/`--bend_angle` determines the angle of the spline at the last coordinate
