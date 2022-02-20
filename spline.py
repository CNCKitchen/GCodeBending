from scipy.interpolate import CubicSpline
from functools import lru_cache, wraps
import matplotlib.pyplot as plt
import numpy as np

class Spline:
    def __init__(self, X, Z, discretization_length=0.01, bend_angle=-30):
        self.X, self.Z = X, Z
        bc_type = ((1, 0), (1, np.radians(bend_angle)))
        self._spline = CubicSpline(self.Z, self.X, bc_type=bc_type)
        self.discretization_length = discretization_length

        self._create_lookup_table()
        # lines will often be at the same height as other lines
        #  -> may as well cache computations so they can be reused
        self.x_at = lru_cache(maxsize=128)(self.x_at)
        self.projected_length = lru_cache(maxsize=8)(self.projected_length)
        self.inclination_angle = lru_cache(maxsize=32)(self.inclination_angle)

    def _create_lookup_table(self):
        # start with evenly spaced heights
        # one extra length at the bottom simplifies later results
        heights = np.arange(self.Z[0] - self.discretization_length,
                            self.Z[-1], self.discretization_length)
        # determine actual height differences due to spline bending
        x_values = self._spline(heights)
        height_deltas = np.sqrt(np.diff(x_values)**2
                                + self.discretization_length**2)
        # redetermine heights using the deltas
        # set initial value to 0
        height_deltas[0] = 0
        self._lookup = height_deltas.cumsum()

    def projected_length(self, z):
        """ Returns the length of height 'z' projected along the spline. """
        try:
            # use the position of the first lookup match, assuming there is one
            return (np.where(z <= self._lookup)[0][0]
                    * self.discretization_length)
        except IndexError as e: # there wasn't one
            raise IndexError(f"{z} mm outside defined spline range") from e

    @wraps(CubicSpline.__call__)
    def x_at(self, *args, **kwargs):
        return self._spline(*args, **kwargs)

    def inclination_angle(self, z):
        return np.arctan(self.x_at(z, 1))

    def normal_point(self, x, z):
        """ Calculates the normal of a point on the spline. """
        distance = x - self.X[0]
        derivative = self.x_at(z, 1)

        angle = np.arctan(derivative) + np.pi / 2
        return (
            z + distance * np.cos(angle),
            self.x_at(z) + distance * np.sin(angle)
        )

    def plot(self, spacing=1, printer_dims=(200, 200),
             ax=None, figsize=(6.5, 4), show=True):
        z_values = np.arange(self.Z[0], self.Z[-1], spacing)
        x_values = self._spline(z_values)
        ax = ax or plt.subplots(figsize=figsize)[1]
        ax.plot(self.X, self.Z, 'o', label='data')
        ax.plot(x_values, z_values, label='S')
        ax.set_xlim(0, printer_dims[0])
        ax.set_ylim(0, printer_dims[1])
        ax.set_aspect('equal', adjustable='box')
        if show:
            plt.pause(0.5)
