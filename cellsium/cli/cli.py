import argparse

import numpy as np

from time import time
from tunable import Tunable, TunableSelectable

from .. import Width, Height, Calibration
from ..random import RRF

from ..simulation.placement import PlacementSimulation

from ..simulation.simulator import *

from ..output.all import *

from ..parameters import CellParameterGenerator, Seed, NewCellCount

from . import Cell

from . import new_cell

class BoundariesFile(Tunable):
    default = ""


def h_to_s(hours):
    return hours * 60.0 * 60.0


def s_to_h(seconds):
    return seconds / (60.0 * 60.0)


class SimulationDuration(Tunable):
    default = 12.0


class SimulationOutputInterval(Tunable):
    default = 0.25


class SimulationTimestep(Tunable):
    default = 1.0 / 60.0





def add_boundaries_from_dxf(file_name, simulator):
    import ezdxf

    dxf = ezdxf.readfile(file_name)

    for item in dxf.modelspace():
        points = None
        if item.dxftype() == 'LWPOLYLINE':
            points = np.array(list(item.get_points()))[:, :2]
            points = points / 32 * 40
        elif item.dxftype() == 'POLYLINE':
            points = np.array(list(item.points()))
        else:
            print("Warning, unknown type", item.dxftype())

        simulator.add_boundary(points)



def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-o', '--output-file', dest='output', default=None)

    TunableSelectable.setup_and_parse(parser)

    args = parser.parse_args()

    RRF.seed(Seed.value)

    cpg = CellParameterGenerator()

    simulator = Simulator()
    ps = PlacementSimulation()

    simulator.sub_simulators += [ps]

    if BoundariesFile.value != '':
        add_boundaries_from_dxf(BoundariesFile.value, simulator)

    for _ in range(NewCellCount.value):
        simulator.add(new_cell(cpg, Cell))

    output = Output()

    simulation_time = 0.0

    last_output = 0.0

    total_before = time()

    time_step = h_to_s(SimulationTimestep.value)

    x = JsonPickleSerializer()
    intv = 0

    while simulation_time < h_to_s(SimulationDuration.value) or SimulationDuration.value < 0:
        before = time()

        simulator.step(time_step)

        #for cell in simulator.simulation.world.cells:
        #    print(cell.length)

        simulation_time += time_step
        after = time()
        print("Timestep took %.2fs, virtual time: %.2f" % (after - before, s_to_h(simulation_time)))

        if (simulation_time - last_output) > h_to_s(SimulationOutputInterval.value) and SimulationOutputInterval.value > 0:
            last_output = simulation_time
            # output.display(simulator.simulation.world)
            output.write(simulator.simulation.world, 'test.tif')
            x.write(simulator.simulation.world, 'frame%03d.json' % (intv,))
            intv+=1

    total_after = time()
    print("Whole simulation took %.2fs" % (total_after - total_before))

    if args.output:
        output.write(simulator.simulation.world, args.output)
    else:
        try:
            output.display(simulator.simulation.world)
        except RuntimeError:
            print("Display not possible")
