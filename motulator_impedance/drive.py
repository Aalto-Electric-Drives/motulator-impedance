"""
Mechanical impedance of machine drives.

The mechanical impedance ``Z_M = -Delta tau_M/Delta w_M`` describes the dynamics of
the machine and its control system, as seen from the shaft [#Har2023]_. It is
measured from simulations by a frequency sweep: the rotor speed is imposed, and
small-signal speed excitations are superimposed on it one frequency at a time.

References
----------
.. [#Har2023] Hartikainen, Tiitinen, Laine, Hinkkanen, "Identification of
   mechanical impedance of an electric machine drive for drivetrain design," Proc.
   IEEE IEMDC, 2023, https://doi.org/10.1109/IEMDC55163.2023.10238992

"""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from functools import partial

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator
from motulator.common.utils import set_style
from motulator.drive.control.im import VectorControlSystem, VHzControlSystem
from motulator.drive.model import Drive, ExternalRotorSpeed
from scipy.integrate import trapezoid

from motulator_impedance._sweep import (
    dft,
    empty_array,
    evaluation_points,
    run_frequency_sweep,
    sampling_period,
    simulate,
)

DriveControlSystem = VectorControlSystem | VHzControlSystem


# %%
@dataclass
class MeasurementCfg:
    """
    Configuration of the mechanical impedance measurement.

    Parameters
    ----------
    abs_w_e : float
        Magnitude of the rotor speed excitation (mechanical rad/s) at the first
        frequency.
    freqs : ndarray, optional
        Excitation frequencies (Hz), defaults to 100 logarithmically spaced frequencies
        from 1 Hz to 1 kHz.
    amplitude_multiplier : float, optional
        Excitation magnitude at the last frequency relative to the first one, defaults
        to 5. The magnitude changes linearly over the frequency array. Use 1 for a
        constant magnitude.
    t0 : float, optional
        Simulation time (s) for reaching the operating point, defaults to 1.0.
    t1 : float, optional
        Additional simulation time (s) for reaching the sinusoidal steady state during
        signal injection, defaults to 0.5.
    N_eval : int, optional
        Number of evenly spaced data points the solver should return for each
        integration interval, i.e., for each sampling period or, if carrier comparison
        is used, for each switching interval, defaults to 10. More points are used at
        high excitation frequencies, so that each excitation period has at least 10
        points.
    n_periods_excitation : int, optional
        Number of excitation signal periods used in calculating the DFT, defaults to 4.
        At least 3 are needed if `use_window` is True.
    multiprocess : bool, optional
        If True, the frequencies are simulated in parallel using all available CPU
        cores, defaults to True. The model and the control system are copied to the
        worker processes, which can require pickling them. Lambda functions and nested
        functions (e.g., as references) cannot be pickled, but module-level functions
        can.
    use_window : bool, optional
        Whether to use window function for calculating DFT, defaults to True.

    """

    abs_w_e: float
    freqs: np.ndarray = field(default_factory=lambda: np.geomspace(1, 1e3, 100))
    amplitude_multiplier: float = 5.0
    t0: float = 1.0
    t1: float = 0.5
    N_eval: int = 10
    n_periods_excitation: int = 4
    multiprocess: bool = True
    use_window: bool = True


@dataclass
class MechanicalImpedance:
    """
    Measured mechanical impedance.

    Contains fields for the excitation frequency `f_e`, the mechanical impedance `Z_M`,
    and the operating-point rotor speed `w_M0` and electromagnetic torque `tau_M0`. The
    results can be saved, e.g., by ``scipy.io.savemat(path, dataclasses.asdict(res))``.

    """

    f_e: np.ndarray = field(default_factory=empty_array)
    Z_M: np.ndarray = field(default_factory=empty_array)
    w_M0: float = 0.0
    tau_M0: float = 0.0


@dataclass
class _SpeedExcitation:
    """Rotor speed ``w_M0 + abs_w_e*cos(2*pi*f_e*t)`` (mechanical rad/s)."""

    w_M0: float
    abs_w_e: float
    f_e: float

    def __call__(self, t: float) -> float:
        return self.w_M0 + self.abs_w_e * np.cos(2 * np.pi * self.f_e * t)


# %%
def _operating_point(
    mdl: Drive, ctrl: DriveControlSystem, cfg: MeasurementCfg
) -> tuple[Drive, DriveControlSystem, MechanicalImpedance, float]:
    """Simulate the system to the operating point, giving also the sampling period."""
    if not isinstance(mdl.mechanics, ExternalRotorSpeed):
        raise TypeError("The rotor speed must be imposed by ExternalRotorSpeed")
    mdl, ctrl = deepcopy(mdl), deepcopy(ctrl)
    res = simulate(mdl, ctrl, cfg.t0, cfg.N_eval)

    # Torque averaged over the last sampling period, whose end point is the final
    # state (not included in the results if N_eval is given)
    k = res.mdl.t >= res.ctrl.t[-1]
    t = np.append(res.mdl.t[k], mdl.t0)
    tau_M = np.append(res.mdl.machine.tau_M[k], mdl.machine.out.tau_M)
    tau_M0 = trapezoid(tau_M, t) / (t[-1] - t[0])
    operating_point = MechanicalImpedance(
        w_M0=mdl.mechanics.meas_speed(), tau_M0=float(tau_M0)
    )
    return mdl, ctrl, operating_point, sampling_period(res)


def _measure_at_frequency(
    cfg: MeasurementCfg,
    mdl0: Drive,
    ctrl0: DriveControlSystem,
    w_M0: float,
    T_s: float,
    excitation: tuple[float, float],
) -> complex:
    """Compute the mechanical impedance at a single frequency."""
    f_e, abs_w_e = excitation
    mdl, ctrl = deepcopy(mdl0), deepcopy(ctrl0)
    mdl.mechanics.set_external_rotor_speed(_SpeedExcitation(w_M0, abs_w_e, f_e))
    T = cfg.n_periods_excitation / f_e
    N_eval = evaluation_points(cfg.N_eval, f_e, T_s)
    res = simulate(mdl, ctrl, mdl.t0 + cfg.t1 + T, N_eval, f_e)
    t, w = res.mdl.t, cfg.use_window
    tau_M = dft(t, res.mdl.machine.tau_M, f_e, T, w)
    w_M = dft(t, res.mdl.mechanics.w_M, f_e, T, w)
    return -tau_M / w_M


# %%
def measure_mechanical_impedance(
    mdl: Drive, ctrl: DriveControlSystem, cfg: MeasurementCfg
) -> MechanicalImpedance:
    """
    Measure the mechanical impedance.

    The rotor speed is imposed by the `ExternalRotorSpeed` model of `mdl`, i.e., no
    mechanical system is used. The system is first simulated to the operating point,
    given by the rotor speed and the references of the control system. Then,
    small-signal speed excitations are injected and the impedance is computed from the
    electromagnetic torque response at each excitation frequency.

    Parameters
    ----------
    mdl : Drive
        Continuous-time system model, whose mechanics is `ExternalRotorSpeed`.
    ctrl : VectorControlSystem | VHzControlSystem
        Discrete-time control system.
    cfg : MeasurementCfg
        Measurement configuration.

    Returns
    -------
    MechanicalImpedance
        Mechanical impedance and the operating point.

    Notes
    -----
    The mechanical impedance is passive at the frequencies where its real part is
    nonnegative, i.e., its phase is within ±90°. Combined with any passive mechanical
    system, a drive whose mechanical impedance is passive at all frequencies is stable.

    """
    mdl0, ctrl0, res, T_s = _operating_point(mdl, ctrl, cfg)
    n_freqs = np.size(cfg.freqs)
    amplitudes = cfg.abs_w_e * np.linspace(1.0, cfg.amplitude_multiplier, n_freqs)
    excitations = list(zip(cfg.freqs, amplitudes, strict=True))
    task = partial(_measure_at_frequency, cfg, mdl0, ctrl0, res.w_M0, T_s)
    res.Z_M = np.array(run_frequency_sweep(task, excitations, cfg.multiprocess))
    res.f_e = np.array(cfg.freqs, dtype=float)  # A copy, independent of cfg
    return res


# %%
def plot_mechanical_impedance(
    res: MechanicalImpedance | Mapping[str, MechanicalImpedance], latex: bool = False
) -> None:
    """
    Plot the magnitude and phase of the mechanical impedance.

    The passivity limits of the phase, -90° and 90°, are shown as dashed lines on the
    side of the phase values.

    Parameters
    ----------
    res : MechanicalImpedance | Mapping[str, MechanicalImpedance]
        Mechanical impedance, or several results by their legend labels.
    latex : bool, optional
        Use latex for plots, defaults to False.

    """
    set_style(latex)
    results = res if isinstance(res, Mapping) else {"": res}
    _, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    phases = []
    for label, res_k in results.items():
        phases.append(np.angle(res_k.Z_M, deg=True))
        ax1.loglog(res_k.f_e, np.abs(res_k.Z_M), label=label)
        ax2.semilogx(res_k.f_e, phases[-1], label=label)
    for limit in (-90, 90):
        if np.any(limit * np.concatenate(phases) > 0):
            ax2.axhline(limit, linestyle="--", color="k", linewidth=1)
    ax1.set_ylabel(r"$|Z_\mathrm{M}|$ (Nm/(rad/s))")
    ax2.set_ylabel(r"$\angle Z_\mathrm{M}$ (deg)")
    # Ticks at multiples of 15° for the ranges that include -90° or 90°
    ax2.yaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1.5, 3, 4.5, 9]))
    ax2.set_xlabel("Frequency (Hz)")
    ax2.margins(x=0)
    if isinstance(res, Mapping):
        ax1.legend()
    plt.show()
