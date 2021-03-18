from ..parameters import h_to_s, s_to_h
from .agent import *
from .geometry import *
from .initialization import (
    RandomAngle,
    RandomBentRod,
    RandomPosition,
    RandomWidthLength,
)


class PlacedCell(
    WithLineageHistory,
    WithLineage,
    WithTemporalLineage,
    WithProperDivisionBehavior,
    InitializeWithParameters,
    Copyable,
    Representable,
    WithRandomSequences,
    RandomWidthLength,
    RandomBentRod,
    RandomPosition,
    RandomAngle,
    CellGeometry,
    BentRod,
):
    pass


class SimulatedCell:
    def birth(self, parent=None, ts=None):
        pass

    def grow(self, ts):
        pass

    def divide(self, ts):
        offspring_a, offspring_b = self.copy(), self.copy()

        offspring_a.position, offspring_b.position = self.get_division_positions()

        if isinstance(self, WithLineage):
            offspring_a.parent_id = offspring_b.parent_id = self.id_

        if isinstance(self, WithLineageHistory):
            offspring_a.lineage_history = self.lineage_history[:] + [self.id_]
            offspring_b.lineage_history = self.lineage_history[:] + [self.id_]

        if isinstance(self, WithTemporalLineage):
            now = ts.simulation.time
            offspring_b.birth_time = offspring_a.birth_time = now

        ts.simulator.add(offspring_a)
        ts.simulator.add(offspring_b)

        offspring_a.birth(parent=self, ts=ts)
        offspring_b.birth(parent=self, ts=ts)

        ts.simulator.remove(self)

        return offspring_a, offspring_b

    def step(self, ts):
        self.grow(ts=ts)


# noinspection PyAttributeOutsideInit
class SizerCell(SimulatedCell):
    @staticmethod
    def random_sequences(sequence):
        return dict(division_size=sequence.normal(3.0, 0.25))  # µm

    def birth(self, parent=None, ts=None):
        self.division_size = next(self.random.division_size)
        self.elongation_rate = 1.5

    def grow(self, ts):
        self.length += self.elongation_rate * ts.hours

        if self.length > self.division_size:
            offspring_a, offspring_b = self.divide(ts)
            offspring_a.length = offspring_b.length = self.length / 2


# noinspection PyAttributeOutsideInit
class TimerCell(SimulatedCell):
    @staticmethod
    def random_sequences(sequence):
        return dict(elongation_rate=sequence.normal(1.5, 0.25))  # µm·h⁻¹

    def birth(self, parent=None, ts=None):
        self.elongation_rate = next(self.random.elongation_rate)
        self.division_time = h_to_s(1.0)

    def grow(self, ts):
        self.length += self.elongation_rate * ts.hours

        if ts.time > (self.birth_time + self.division_time):
            offspring_a, offspring_b = self.divide(ts)
            offspring_a.length = offspring_b.length = self.length / 2
