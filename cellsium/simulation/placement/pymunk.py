import numpy as np
from tunable import Tunable

from .base import (
    PhysicalPlacement,
    PlacementSimulation,
    PlacementSimulationSimplification,
)

try:
    import pymunkoptions

    pymunkoptions.options['debug'] = False
except ImportError:
    pymunkoptions = None  # PyMunk 6.0.0 has removed pymunkoptions
# noinspection PyPep8
import pymunk


class ChipmunkPlacementRadius(Tunable):
    default = 0.05


class Chipmunk(PhysicalPlacement, PlacementSimulation, PlacementSimulation.Default):

    verbose = False

    def __init__(self):
        self.space = pymunk.Space(threaded=False)

        # self.space.threads = 2
        self.space.iterations = 100

        self.space.gravity = 0, 0

        self.boundary_bodies = []
        self.boundary_segments = []

        super().__init__()

    def add_boundary(self, coordinates):
        coordinates = np.array(coordinates)

        boundary_body = pymunk.Body(body_type=pymunk.Body.STATIC)

        boundary_segments = []

        for start, stop in zip(coordinates, coordinates[1:]):
            self.boundaries.append([start, stop])
            segment = pymunk.Segment(boundary_body, start.tolist(), stop.tolist(), 0.0)
            boundary_segments.append(segment)

        self.space.add(boundary_body, *boundary_segments)

        self.boundary_bodies.append(boundary_body)
        self.boundary_segments.append(boundary_segments)

    def add(self, cell):
        body = pymunk.Body(1.0, 1.0)
        body.position = pymunk.Vec2d(cell.position[0], cell.position[1])
        body.angle = cell.angle

        if PlacementSimulationSimplification.value == 2:
            shapes = tuple(
                pymunk.Circle(body, radius, offset=offset)
                for radius, offset in cell.get_approximation_circles()
            )
        else:
            points = cell.raw_points(
                simplify=PlacementSimulationSimplification.value == 1
            )

            poly = pymunk.Poly(body, points.tolist())
            poly.unsafe_set_radius(ChipmunkPlacementRadius.value)

            shapes = (poly,)

        self.cell_bodies[cell] = body
        self.cell_shapes[cell] = shapes

        self.space.add(body, *shapes)

    def remove(self, cell):
        self.space.remove(self.cell_bodies[cell], *self.cell_shapes[cell])

        del self.cell_bodies[cell]
        del self.cell_shapes[cell]

    def clear(self):
        super().clear()

        for boundary_body, boundary_segments in zip(
            self.boundary_bodies, self.boundary_segments
        ):
            self.space.remove(boundary_body)
            self.space.remove(*boundary_segments)

        self.boundary_bodies.clear()
        self.boundary_segments.clear()

    def step(self, timestep):
        if len(self.cell_bodies) == 0:
            return

        resolution = 0.1 * 10
        times = timestep / resolution
        last = self.inner_step(
            time_step=resolution, iterations=int(times), epsilon=1e-12
        )
        _ = last

    def inner_step(self, time_step=0.1, iterations=9999, converge=True, epsilon=0.1):
        converging = False

        first_positions = self._get_positions()[:, :2]

        look_back = 0
        look_back_threshold = 5

        convergence_check = convergence_check_interval = 15

        if converge:
            before_positions = first_positions.copy()

            for _ in range(iterations):
                self.space.step(time_step)

                convergence_check -= 1

                if convergence_check > 0:
                    continue

                convergence_check = convergence_check_interval

                after_positions = self._get_positions()[:, :2]

                dist = (
                    self._mean_distance(before_positions, after_positions)
                    * time_step
                    * convergence_check_interval
                )

                before_positions[:] = after_positions

                if dist < epsilon:
                    look_back += 1
                    if look_back > look_back_threshold:
                        break
                else:
                    look_back = 0

                if look_back > look_back_threshold:
                    break

                if False or self.verbose:
                    print(_, dist)

                if not converging:
                    if dist > 0:
                        converging = True
                else:
                    if dist < epsilon:
                        break

                before_positions[:] = after_positions
        else:
            for _ in range(iterations):
                self.space.step(time_step)

        after_positions = self._get_positions()[:, :2]

        for cell, body in self.cell_bodies.items():
            cell.position = [body.position[0], body.position[1]]
            cell.angle = body.angle

        return self._total_distance(first_positions, after_positions)
