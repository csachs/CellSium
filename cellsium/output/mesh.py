import numpy as np
from stl import mesh
from tunable import Tunable

from . import Output


class MeshCellScaleFactor(Tunable):
    default = 1.0


class MeshOutput(Output):
    def __init__(self):
        super().__init__()

    def output(self, world, **kwargs):
        meshes = []

        # for boundary in world.boundaries:
        #     pass

        scale_props = ('width', 'length')

        for cell in world.cells:
            backup = {}

            if MeshCellScaleFactor.value != 1.0:
                for sp in scale_props:
                    if hasattr(cell, sp):
                        value = getattr(cell, sp)
                        backup[sp] = value
                        setattr(cell, sp, value * MeshCellScaleFactor.value)

            vertices, triangles = cell.points3d_on_canvas()

            for k, v in backup.items():
                setattr(cell, k, v)

            meshes.append(dict(vertices=vertices, triangles=triangles))

        return meshes

    def write(self, world, file_name, **kwargs):
        meshes = self.output(world)

        stl_meshes = []

        for single_mesh in meshes:
            vertices, triangles = single_mesh['vertices'], single_mesh['triangles']
            data = mesh.Mesh(np.zeros(len(triangles), dtype=mesh.Mesh.dtype))
            for i, tri in enumerate(triangles):
                data.vectors[i, :] = vertices[tri, :]

            stl_meshes.append(data)

        result_mesh = mesh.Mesh(
            np.concatenate([single_mesh.data for single_mesh in stl_meshes])
        )
        result_mesh.save(file_name)

    def display(self, world, **kwargs):
        # ax = fig.add_subplot(111, projection='3d')
        # ax.scatter(vertices[:, 0], vertices[:, 1], vertices[:, 2])
        # ax.set_aspect('equal', 'datalim')
        raise RuntimeError('Unsupported')
