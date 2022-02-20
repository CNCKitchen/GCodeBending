# -*- coding: utf-8 -*-
"""
Created on Wed Jan 12 10:10:14 2022

@author: stefa
"""

from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter
from typing import ClassVar
from spline import Spline
import numpy as np
import re


@dataclass
class Point2D:
    x: float
    y: float

@dataclass
class GCodeLine:
    x: float
    y: float
    z: float
    e: float
    f: int

    gcode_format: ClassVar[re.Pattern] = (
        re.compile('(?i)^[gG][0-3](?:\s'
                   '+x(?P<x>-?[0-9.]{1,15})|\s'
                   '+y(?P<y>-?[0-9.]{1,15})|\s'
                   '+z(?P<z>-?[0-9.]{1,15})|\s'
                   '+e(?P<e>-?[0-9.]{1,15})|\s'
                   '+f(?P<f>-?[0-9.]{1,15}))*')
    )

    @classmethod
    def from_gcode(cls, line: str):
        line_entries = cls.gcode_format.match(line)
        if line_entries:
            return cls(*line_entries.groups())


def main(in_file, out_file, spline, layer_height, warning_angle,
         xy_precision=4, z_precision=3, e_precision=5):

    lastPosition = Point2D(0, 0)
    currentZ = 0.0
    lastZ = 0.0
    currentLayer = 0
    relativeMode = False

    with open(in_file, "r") as gcodeFile, open(out_file, "w+") as outputFile:
        def writeLine(G, X, Y, Z, E=None, F=None):
            output = f'G{G} X{X:.{xy_precision}f} Y{Y:.{xy_precision}f} Z{Z:.{z_precision}f}'
            if E is not None:
                output += f" E{E:.{e_precision}f}"
            if F is not None:
                output += f" F{F}"
            outputFile.write(output + '\n')

        print('Processing: (press CTRL+C to abort)')
        start = perf_counter()
        for index, currentLine in enumerate(gcodeFile):
            if index % 1000 == 0: # track progress
                print(f"[{timedelta(seconds=perf_counter()-start)}]: line {index}\r", end='')
            if currentLine[0] == ";":   #if NOT a comment
                outputFile.write(currentLine)
                continue
            if currentLine.startswith("G91"):    #filter relative commands
                relativeMode = True
                outputFile.write(currentLine)
                continue
            if currentLine.startswith("G90 "):   #set absolute mode
                relativeMode = False
                outputFile.write(currentLine)
                continue
            if relativeMode: #if in relative mode don't do anything
                outputFile.write(currentLine)
                continue
            currentLineCommands = GCodeLine.from_gcode(currentLine)
            if currentLineCommands is not None: #if current comannd is a valid gcode
                if currentLineCommands.z is not None: #if there is a z height in the command
                    currentZ = float(currentLineCommands.z)
                
                if currentLineCommands.x is None or currentLineCommands.y is None: #if command does not contain x and y movement it#s probably not a print move
                    if currentLineCommands.z is not None: #if there is only z movement (e.g. z-hop)
                        outputFile.write(f"G91\nG1 Z{currentZ - lastZ}")
                        if currentLineCommands.f is not None:
                            outputFile.write(f" F{currentLineCommands.f}")
                        outputFile.write("\nG90\n")
                        lastZ = currentZ
                        continue
                    outputFile.write(currentLine)
                    continue
                currentPosition = Point2D(float(currentLineCommands.x), float(currentLineCommands.y))
                midpointX = lastPosition.x + (currentPosition.x - lastPosition.x) / 2  #look for midpoint
                
                distToSpline = midpointX - spline.X[0]
                
                #Correct the z-height if the spline gets followed
                correctedZHeight = spline.projected_length(currentZ)

                angleSplineThisLayer = spline.inclination_angle(correctedZHeight)
                angleLastLayer = spline.inclination_angle(correctedZHeight - layer_height)
                heightDifference = np.sin(angleSplineThisLayer - angleLastLayer) * distToSpline * -1 # layer height difference
                transformedGCode = Point2D(*spline.normal_point(currentPosition.x, correctedZHeight))

                #Check if a move is below Z = 0
                if float(transformedGCode.x) <= 0.0: 
                    print("Warning! Movement below build platform. Check your spline!")
                
                #Detect unplausible moves
                if transformedGCode.x < 0 or np.abs(transformedGCode.x - currentZ) > 50:
                    print(f"Warning! Possibly unplausible move detected on height {currentZ} mm!")
                    outputFile.write(currentLine)
                    continue
                #Check for self intersection
                if (layer_height + heightDifference) < 0:
                    print(f"ERROR! Self intersection on height {currentZ} mm! Check your spline!")
                    
                #Check the angle of the printed layer and warn if it's above the machine limit
                if angleSplineThisLayer > np.radians(warning_angle):
                    print(f"Warning! Spline angle is {np.degrees(angleSplineThisLayer)}, at height  {currentZ} mm! Check your spline!")
                                                    
                if currentLineCommands.e is not None: #if this is a line with extrusion
                    """if float(currentLineCommands.e) < 0.0:
                        print("Retraction")"""
                    extrusionAmount = float(currentLineCommands.e) * ((layer_height + heightDifference)/layer_height)
                    #outputFile.write(";was" + currentLineCommands.e + " is" + str(extrusionAmount) + " diff" + str(int(((layer_height + heightDifference)/layer_height)*100)) + "\n")
                else:
                    extrusionAmount = None
                writeLine(1,transformedGCode.y, currentPosition.y, transformedGCode.x, extrusionAmount, None)
                lastPosition = currentPosition
                lastZ = currentZ
            else:
                outputFile.write(currentLine)

    print("\nGCode bending finished!")
    print(f"Processed {index} lines in {timedelta(seconds=perf_counter()-start)}")

if __name__ == "__main__":
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument("in_file", help="input file name (*.gcode)")
    parser.add_argument("-o", "--out_file", help="output filename, default 'BENT_{in_file}'")
    parser.add_argument("-x", "--x_values", default=(125, 95), nargs="*", type=float,
                        help=("x values that define the spline, space-separated (e.g. '125 50 33')."
                              " First should be in the center of your part."))
    parser.add_argument("-z", "--z_values", default=(0, 140), nargs="*", type=float,
                        help=("corresponding z values that define the spline, space-separated."
                              " First should be 0 (e.g. '0 80 140')."))
    parser.add_argument("-l", "--layer_height", default=0.3, type=float,
                        help="layer height of the sliced gcode [mm].")
    parser.add_argument("-a", "--warning_angle", default=30, type=float,
                        help="Maximum angle [degrees] printable with your setup")
    parser.add_argument("-b", "--bend_angle", default=-30, type=float,
                        help="Angle [degrees] of the spline at the top point")
    parser.add_argument("-d", "--discretization_length", default=0.01, type=float,
                        help="Discretization length for the spline length lookup table")
    parser.add_argument("-s", "--skip_plot", action="store_true",
                        help="flag to skip plotting of the spline")
    parser.add_argument("--xy_precision", type=int, default=4,
                        help="Decimals of precision to round x/y values to.")
    parser.add_argument("--z_precision", type=int, default=3,
                        help="Decimals of precision to round z (height) values to.")
    parser.add_argument("--e_precision", type=int, default=5,
                        help="Decimals of precision to round extrusion amounts to.")
    parser.add_argument("--printer_dims", nargs=2, default=(200, 200), type=float,
                        help="printer width and height [mm], space-separated.")

    args = parser.parse_args()

    spline = Spline(args.x_values, args.z_values, args.discretization_length,
                    args.bend_angle)
    if not args.skip_plot:
        print("Press Q to close the plot and continue")
        spline.plot(printer_dims=args.printer_dims)

    out_file = args.out_file or f"BENT_{args.in_file}"

    main(args.in_file, out_file, spline, args.layer_height, args.warning_angle,
         args.xy_precision, args.z_precision, args.e_precision)
