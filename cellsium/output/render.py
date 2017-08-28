import cv2
import numpy as np

from . import Output
from ..random import RRF
from scipy.ndimage.interpolation import rotate
from scipy.interpolate import interp1d
from tunable import Tunable
from .. import Width, Height, Calibration, um_to_pixel, pixel_to_um

from .plot import MicrometerPerCm


def noise_attempt(times=5, m=10, n=512, r=None):
    def make_rand(n, r):
        return interp1d(np.linspace(0, n, num=n), np.array([next(r) for _ in range(n)]), kind='cubic')

    def make_square(array):
        return np.tile(array, len(array)).reshape((len(array), len(array)))

    def make_it(n, m, r):
        return make_square(make_rand(m, r)(np.linspace(0, m, n)))

    two_n = 2*n

    the_sum = make_it(two_n, m, r)

    for _ in range(times):
        the_sum += rotate(make_it(two_n, m, r), angle=360.0*next(r), reshape=False)

    the_sum /= times

    the_sum = the_sum[n//2:two_n-n//2, n//2:two_n-n//2]
    return the_sum


def gaussian(array, dst=None, sigma=1.0):
    return cv2.GaussianBlur(array, (0, 0), sigmaX=um_to_pixel(sigma), dst=dst)


class LuminanceBackground(Tunable):
    default = 0.17


class LuminanceCell(Tunable):
    default = 0.075


def add_if_uneven(value, add=1):
    if (value % 2) == 0:
        return value
    else:
        return value + add


def new_canvas(dtype=np.float32):
    width, height = int(um_to_pixel(Width.value)), int(um_to_pixel(Height.value))
    # evenize
    width, height = add_if_uneven(width), add_if_uneven(height)
    canvas = np.zeros((height, width), dtype=dtype)
    return canvas


class OpenCVimshow(Tunable):
    default = False


from matplotlib.path import Path
from matplotlib.patches import PathPatch

def prepare_patch(coordinates, **kwargs):
    actions = [Path.MOVETO] + [Path.LINETO] * (len(coordinates) - 1)

    if 'closed' in kwargs:
        if kwargs['closed']:
            actions.append(Path.CLOSEPOLY)

            coordinates = np.r_[coordinates, [[0, 0]]]
        del kwargs['closed']

    patch = PathPatch(Path(coordinates, actions), **kwargs)
    #gca.add_patch()
    return patch

from matplotlib import pyplot


def scale_points_relative(points, scale_points=1.0):
    if scale_points == 1.0:
        return points

    ma, mi = points.max(axis=0), points.min(axis=0)
    shift = mi - (ma - mi) * 0.5
    points = (scale_points * (points - shift)) + shift
    return points


def render_on_canvas_cv2(canvas, array_of_points, scale_points=1.0):
    for points in array_of_points:
        points = scale_points_relative(points, scale_points)
        cv2.fillPoly(canvas, points[np.newaxis].astype(np.int32), 1.0)

    return canvas


def render_on_canvas_matplotlib(canvas, array_of_points, scale_points=1.0, oversample=1):
    dpi = 100.0
    fig = pyplot.figure(frameon=False, dpi=dpi, figsize=(oversample * canvas.shape[1] / dpi, oversample * canvas.shape[0] / dpi))

    ax = fig.add_axes([0, 0, 1, 1])
    for points in array_of_points:
        points = scale_points_relative(points, scale_points)
        ax.add_patch(prepare_patch(points, edgecolor='black', facecolor='white', closed=True, linewidth=oversample*0.25))

    plt = ax.imshow(canvas, cmap='gray')

    ax.axis('off')

    plt.axes.get_xaxis().set_visible(False)
    plt.axes.get_yaxis().set_visible(False)

    fig.canvas.draw()

    canvas_data = np.fromstring(fig.canvas.tostring_rgb(), dtype=np.uint8).reshape(
        fig.canvas.get_width_height()[::-1] + (3,))[:, :, 0]
    canvas_data = canvas_data.astype(np.float32) / canvas_data.max()

    pyplot.close(fig.number)

    if oversample != 1:
        cv2.resize(canvas_data, dst=canvas_data, dsize=canvas.shape[::-1], interpolation=cv2.INTER_AREA)

    return canvas_data


class PlainRenderer(Output):
    def __init__(self):
        super(PlainRenderer, self).__init__()

    def new_canvas(self):
        return new_canvas()

    def output(self, world):
        canvas = self.new_canvas()

        array_of_points = []

        for cell in world.cells:
            points = um_to_pixel(cell.points_on_canvas())
            # flip y, to have (0,0) bottom left
            points[:, 1] = canvas.shape[0] - points[:, 1]

            array_of_points.append(points)

        # canvas = render_on_canvas_cv2(canvas, array_of_points)
        canvas = render_on_canvas_matplotlib(canvas, array_of_points)

        return canvas

    def convert(self, image):
        return (np.clip(image, 0, 1) * 255).astype(np.uint8)

    def write(self, world, file_name):
        cv2.imwrite(file_name, self.convert(self.output(world)))

    def display(self, world):

        image = self.output(world)

        if OpenCVimshow.value:
            cv2.imshow(self.__class__.__name__, self.convert(image))
            cv2.waitKey()
        else:
            from matplotlib import pyplot

            pyplot.ion()

            if getattr(self, 'fig', None) is None:
                self.fig = pyplot.figure(
                    figsize=(Width.value / MicrometerPerCm.value / 2.51, Height.value / MicrometerPerCm.value / 2.51)
                )

            if getattr(self, 'ax', None) is None:
                self.ax = self.fig.add_subplot(111)

            self.ax.clear()

            self.ax.imshow(image, cmap='gray')

            pyplot.tight_layout()
            pyplot.show()
            self.fig.canvas.draw()
            self.fig.canvas.flush_events()


class FluorescenceRenderer(PlainRenderer):
    def __init__(self):
        super(FluorescenceRenderer, self).__init__()
        canvas = self.new_canvas()

        self.random_noise = RRF.new(np.random.normal, 0.0, 0.15, canvas.shape)

    def output(self, world):
        canvas = self.new_canvas()

        int_background = 1.0

        int_cell = 350.0 * int_background

        # for cell in self.cells:
        #     points = um_to_pixel(cell.points_on_canvas())
        #     cv2.fillPoly(canvas, points[np.newaxis].astype(np.int32), 1.0)

        emitter_size = (17, 17)

        emitter = np.zeros(emitter_size)
        emitter[emitter_size[0]//2, emitter_size[1]//2] = 1.0

        emitter = cv2.GaussianBlur(emitter, emitter_size, 2.5, 2.5)

        canvas = next(self.random_noise)
        p_canvas = np.pad(canvas, emitter_size, mode='reflect')

        # this weird construction is necessary for a sequence of reproducible randomness
        class SeqOfPairsOfUniform(object):
            __slots__ = 'x0', 'x1', 'y0', 'y1'

            def __init__(self):
                self.x0, self.x1, self.y0, self.y1 = 0, 0, 0, 0

            def set_bounds(self, x0, x1, y0, y1):
                self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1

            def next(self):
                return np.random.uniform(self.x0, self.x1), np.random.uniform(self.y0, self.y1)

        sopou = SeqOfPairsOfUniform()
        sopou_gen = RRF.new(sopou.next)

        heterogeneity = RRF.new(np.random.uniform, 0, 1)

        for cell in world.cells:
            points = um_to_pixel(cell.points_on_canvas())
            #
            points[:, 1] = canvas.shape[0] - points[:, 1]

            pts = points[np.newaxis].astype(np.int32)

            if points[:, 0].min() < 0 or points[:, 0].max() > canvas.shape[1]:
                continue

            if points[:, 1].min() < 0 or points[:, 1].max() > canvas.shape[0]:
                continue

            if next(heterogeneity) > 0.7:
                brightness = int_cell * 0.5
            else:
                brightness = int_cell

            int_countdown = brightness * (cv2.contourArea(pts) / 500.0)

            sopou.set_bounds(points[:, 0].min(), points[:, 0].max(), points[:, 1].min(), points[:, 1].max())

            while int_countdown > 0:
                x, y = next(sopou_gen)

                result = cv2.pointPolygonTest(pts, (x, y), measureDist=False)
                if result > 0.0:
                    target = p_canvas[int(y)+emitter_size[1]//2:int(y)+3*emitter_size[1]//2, int(x)+emitter_size[0]//2:int(x)+3*emitter_size[0]//2]
                    target += emitter[:target.shape[0], :target.shape[1]]
                    int_countdown -= 1

        canvas = p_canvas[emitter_size[0]:-emitter_size[0], emitter_size[1]:-emitter_size[1]]

        gaussian(canvas, dst=canvas, sigma=0.025)

        return canvas

"""
            cell_canvas_black = new_canvas()

            for cell in world.cells:
                inner_canvas = new_canvas()

                points = um_to_pixel(cell.points_on_canvas())
                # flip y, to have (0,0) bottom left
                points[:, 1] = canvas.shape[0] - points[:, 1]

                inner_canvas = render_on_canvas_matplotlib(inner_canvas, [points])

                gaussian(inner_canvas, dst=inner_canvas, sigma=0.75)

                cell_canvas_black += inner_canvas
"""


class PhaseContrastRendererOld(PlainRenderer):
    def output(self, world):
        cell_canvas = super(PhaseContrastRendererOld, self).output(world)

        canvas = LuminanceBackground.value * np.ones_like(cell_canvas)

        cell_mask = cell_canvas.copy()

        cell_canvas_black = gaussian(cell_canvas, sigma=0.75)

        #cell_canvas_black = cell_canvas_black - cell_canvas

        gaussian(cell_canvas, dst=cell_canvas, sigma=0.6)
        cell_canvas *= 0.9

        cell_canvas_black -= cell_canvas
        cell_canvas_black *= (1-cell_mask)

        # gaussian(canvas, dst=canvas, sigma=0.03)

        canvas = (1-cell_canvas) * canvas + LuminanceCell.value * cell_canvas

        canvas -= 0.50 * cell_canvas_black

        canvas += 0.5 * (1-cell_mask) * cell_canvas

        canvas -= 0.045*cell_mask

        gaussian(canvas, dst=canvas, sigma=0.05)

        return canvas


class PhaseContrastRenderer(PlainRenderer):
    def output(self, world):
        cell_canvas = super(PhaseContrastRenderer, self).output(world)

        background = LuminanceBackground.value * np.ones_like(cell_canvas)

        cell_halo = 0.5 * gaussian(cell_canvas, sigma=0.75)

        background_w_halo = background + cell_halo

        cell_canvas = gaussian(cell_canvas, sigma=0.05)

        halo_glow_in_cells = 0.4 * gaussian(cell_canvas, 0.1) * gaussian(cell_halo * (1 - cell_canvas), sigma=0.05)

        result = (
            background_w_halo * (1 - cell_canvas)
            + cell_canvas * LuminanceCell.value
        ) + halo_glow_in_cells

        result = gaussian(result, dst=result, sigma=0.075)

        return result


class UnevenIlluminationAdditiveFactor(Tunable):
    default = 0.02

class UnevenIlluminationMultiplicativeFactor(Tunable):
    default = 0.05
    default = 0.25


class UnevenIlluminationPhaseContrast(PhaseContrastRenderer):
    def __init__(self):
        super(UnevenIlluminationPhaseContrast, self).__init__()

        self.random_complex_noise = RRF.new(np.random.uniform, 0, 1)
        self.uneven_illumination = None
        self.create_uneven_illumination()

    def new_uneven_illumination(self):
        empty = self.new_canvas()
        return noise_attempt(
            times=5,
            m=10,
            n=max(empty.shape),
            r=self.random_complex_noise)[:empty.shape[0], :empty.shape[1]]

    def create_uneven_illumination(self):
        self.uneven_illumination = self.new_uneven_illumination()

    def output(self, world):
        canvas = super(UnevenIlluminationPhaseContrast, self).output(world)

        canvas = (
            (canvas * (1.0 + UnevenIlluminationMultiplicativeFactor.value * self.uneven_illumination))
            + UnevenIlluminationAdditiveFactor.value * self.uneven_illumination
        )

        return canvas


class NoisyUnevenIlluminationPhaseContrast(PhaseContrastRenderer):
    def __init__(self):
        super(NoisyUnevenIlluminationPhaseContrast, self).__init__()

        empty = self.new_canvas()

        self.product_noise = RRF.new(np.random.normal, 1.0, 0.002, empty.shape)
        self.sum_noise = RRF.new(np.random.normal, 0.0, 0.002, empty.shape)

    def output(self, world):
        canvas = super(NoisyUnevenIlluminationPhaseContrast, self).output(world)

        product_noise = next(self.product_noise)
        sum_noise = next(self.sum_noise)

        canvas = canvas * product_noise + sum_noise

        return canvas


from imagej_tiff_meta import TiffWriter


class TiffOutput(Output):

    channels = [NoisyUnevenIlluminationPhaseContrast, FluorescenceRenderer]

    def __init__(self):
        self.channels = [c() for c in self.channels]
        self.images = []
        self.current = -1
        self.writer = None

    def output(self, world):
        return [c.output(world) for c in self.channels]

    def __del__(self):
        stack = []
        for stacklet in self.images:
            stacklet = np.concatenate([image[np.newaxis] for image in stacklet], axis=0)
            stack.append(stacklet[np.newaxis, np.newaxis])

        result = np.concatenate(stack)

        output_type = np.float32

        if output_type in (np.uint8, np.uint16):

            for c in range(result.shape[2]):
                result[:, 0, c, :, :] -= result[:, 0, c, :, :].min()
                result[:, 0, c, :, :] /= result[:, 0, c, :, :].max()

            result *= 2**(8*np.dtype(output_type).itemsize) - 1

        result = result.astype(output_type)

        self.writer.save(result)

    def write(self, world, file_name):
        if self.writer is None:
            self.writer = TiffWriter(file_name)

        self.current += 1

        stacklet = self.output(world)

        self.images.append(stacklet)

        for cell in world.cells:
            points = um_to_pixel(cell.points_on_canvas())
            # flip y, to have (0,0) bottom left
            canvas = stacklet[0]
            points[:, 1] = canvas.shape[0] - points[:, 1]

            for c, _ in enumerate(self.channels):
                self.writer.add_roi(points, c=c, z=0, t=self.current)
