from math import cos, sin
import numpy as np

from ..geometry import *


class Shape(object):
    @staticmethod
    def defaults():
        return dict()

    def raw_points(self, simplify=False):
        pass

    def get_approximation_circles(self):
        pass


class Shape3D(Shape):
    def raw_points3d(self, steps=32, simplify=False):
        pass


class RodShaped(Shape):

    @staticmethod
    def defaults():
        return dict(length=2.0, width=1.0)

    def rod_raw_points(self, simplify=False):
        diameter = self.width
        radius = diameter / 2.0
        length = self.length - diameter
        half_length = length / 2.0

        upper = line([half_length, radius], [-half_length, radius], times=None if not simplify else 3)
        lower = line([-half_length, -radius], [half_length, -radius], times=None if not simplify else 3)

        circle_left = circle_segment(radius, 90, 270, times=None if not simplify else 5)
        circle_left[:, 0] -= half_length

        circle_right = circle_segment(radius, -90, 90, times=None if not simplify else 5)
        circle_right[:, 0] += half_length

        return lower, circle_right, upper, circle_left

    def raw_points(self, simplify=False):
        lower, circle_right, upper, circle_left = self.rod_raw_points(simplify=simplify)
        return np.r_[lower, circle_right, upper, circle_left]

    def get_approximation_circles(self):
        diameter = self.width
        radius = diameter / 2.0
        length = self.length - diameter
        half_length = length / 2.0

        times = 2*int(length / radius)

        for x in np.linspace(-half_length, half_length, times):
            yield radius, (x, 0)


class BentRod(RodShaped):

    @staticmethod
    def defaults():
        return dict(bend_overall=0.0, bend_upper=0.0, bend_lower=0.0)

    def bend(self, points):
        u_idx, l_idx = points[:, 1] > 0, points[:, 1] < 0

        points[u_idx, :] = parabolic_deformation(points[u_idx, :], self.bend_upper)
        points[l_idx, :] = parabolic_deformation(points[l_idx, :], self.bend_lower)

        points = parabolic_deformation(points, self.bend_overall)

        return points

    def raw_points(self, simplify=False):
        lower, circle_right, upper, circle_left = self.rod_raw_points(simplify=simplify)

        points = np.r_[lower, circle_right, upper, circle_left]

        points = self.bend(points)

        return points

    def raw_points3d(self, steps=16, simplify=False):
        lower, circle_right, upper, circle_left = self.rod_raw_points(simplify=simplify)
        points = np.r_[lower, circle_right, upper, circle_left]

        points, tris = rotate_and_mesh(add_empty_third_dimension(points), steps=steps)

        points = self.bend(points)

        return points, tris

    def get_approximation_circles(self):
        radii = []
        offsets = []
        for radius, offset in super(BentRod, self).get_approximation_circles():
            radii.append(radius)
            offsets.append(offset)
        offsets = np.array(offsets)
        offsets = parabolic_deformation(offsets, self.bend_overall)

        for radius, offset in zip(radii, offsets):
            yield radius, offset


class Coccoid(Shape):

    @staticmethod
    def defaults():
        return dict(length=1.0)

    def raw_points(self, simplify=False):
        radius = self.length / 2

        circle_left = circle_segment(radius, 90, 270, times=None if not simplify else 5)
        circle_right = circle_segment(radius, -90, 90, times=None if not simplify else 5)

        return np.r_[circle_right, circle_left]


class Ellipsoid(Coccoid):

    @staticmethod
    def defaults():
        return dict(length=2.0, width=1.0)

    def raw_points(self, simplify=False):
        points = super(Ellipsoid, self).raw_points()

        a = self.length / 2
        b = self.width / 2

        points[:, 1] *= (b/a)

        return points


class WithPosition(object):

    @staticmethod
    def defaults():
        return dict(position=lambda: [0.0, 0.0])


class WithAngle(object):

    @staticmethod
    def defaults():
        return dict(angle=0.0)


class WithFluorescence(object):
    @staticmethod
    def defaults():
        return dict(fluorescences=lambda: [0.0])


class WithProperDivisionBehavior(object):
    def get_division_positions(self, count=2):
        # must have a length, a position and an angle

        sin_a, cos_a = sin(self.angle), cos(self.angle)

        x, y = self.position

        return [
            [
                float(x + factor * cos_a),
                float(y + factor * sin_a)
            ]
            for factor in np.linspace(-self.length / 2 / 2, self.length / 2 / 2, num=count)
        ]


class AutoMesh3D(Shape3D):
    def points3d_on_canvas(self, steps=16, simplify=False):
        points, triangles = self.raw_points3d(steps=steps, simplify=simplify)

        axis_vector = [[0], [0], [1]]

        position3d = self.position

        return shift(rotate3d(points, self.angle, axis_vector), position3d), triangles

    def raw_points3d(self, steps=16, simplify=False):
        return rotate_and_mesh(add_empty_third_dimension(self.raw_points(simplify=simplify)), steps=steps)


class CellGeometry(WithAngle, WithPosition, AutoMesh3D):
    def points_on_canvas(self):
        return shift(rotate(self.raw_points(), self.angle), self.position)

