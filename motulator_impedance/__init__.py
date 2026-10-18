"""
Mechanical impedance of machine drives and output admittance of grid converters.

The impedances are measured from motulator simulations by frequency sweeps: the
system is simulated to its operating point, small-signal excitations are injected one
frequency at a time, and the response is computed with the discrete Fourier
transform. The package has a module for each system type::

    from motulator_impedance import drive, grid

"""

from motulator_impedance import drive, grid

__all__ = ["drive", "grid"]
