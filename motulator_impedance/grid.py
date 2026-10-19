"""
Output admittance of grid converters.

The output admittance of the converter at the point of common coupling (PCC) is
measured from simulations by a frequency sweep [#Maa2026]_: the PCC voltage is imposed
by a stiff source, and small-signal voltage excitations are injected in the d- and
q-axes one frequency at a time. The admittance is the basis of impedance-based
stability analysis, e.g., through its passivity.

References
----------
.. [#Maa2026] Määttä, Kukkola, Seppänen, Hinkkanen, "Open-source Python tool for grid
   converter output admittance identification," 2026,
   https://arxiv.org/abs/2607.10653

"""

from copy import deepcopy
from dataclasses import dataclass, field
from functools import partial
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
from motulator.common.utils import set_style
from motulator.grid import control, model, utils

from motulator_impedance._sweep import (
    dft,
    empty_array,
    evaluation_points,
    run_frequency_sweep,
    sampling_period,
    simulate,
)


# %%
@dataclass
class MeasurementCfg:
    """
    Configuration of the output admittance measurement.

    Parameters
    ----------
    abs_u_e : float
        Magnitude of the voltage excitation (V) at the first frequency.
    freqs : ndarray, optional
        Excitation frequencies (Hz, in dq-coordinates), defaults to 100 logarithmically
        spaced frequencies from 1 Hz to 10 kHz.
    amplitude_multiplier : float, optional
        Excitation magnitude at the last frequency relative to the first one, defaults
        to 5. The magnitude changes linearly over the frequency array. Use 1 for a
        constant magnitude.
    t0 : float, optional
        Stop time for initial simulating to the operating point (s), defaults to 1.0.
        Should be set large enough to reach steady-state. A time-varying grid
        frequency must be constant over the last `n_periods_init` periods.
    t1 : float, optional
        Additional simulation time for reaching sinusoidal steady-state during signal
        injection (s), defaults to 0.05.
    N_eval : int, optional
        Number of evenly spaced data points the solver should return for each
        integration interval, i.e., for each sampling period or, if carrier comparison
        is used, for each switching interval, defaults to 10. More points are used at
        high excitation frequencies, so that each excitation period has at least 10
        points.
    n_periods_excitation : int, optional
        Number of excitation signal periods used in calculating the DFT, defaults to 4.
        At least 3 are needed if `use_window` is True.
    n_periods_init : int, optional
        Number of fundamental periods to include for calculating operating-point
        vectors, defaults to 1.
    multiprocess : bool, optional
        If True, the frequencies are simulated in parallel using all available CPU
        cores, defaults to True. The model and the control system are copied to the
        worker processes, which can require pickling them. Lambda functions and nested
        functions (e.g., as references) cannot be pickled, but module-level functions
        can. In a script, call the measurement under `if __name__ == "__main__":`,
        as in the examples.
    use_window : bool, optional
        Whether to use window function for calculating DFT, defaults to True.

    """

    abs_u_e: float
    freqs: np.ndarray = field(default_factory=lambda: np.geomspace(1, 10e3, 100))
    amplitude_multiplier: float = 5.0
    t0: float = 1.0
    t1: float = 0.05
    N_eval: int = 10
    n_periods_excitation: int = 4
    n_periods_init: int = 1
    multiprocess: bool = True
    use_window: bool = True


@dataclass
class OutputAdmittance:
    """
    Measured output admittance.

    Contains fields for excitation signal frequency `f_e`, elements of the output
    admittance matrix `[Y_dd, Y_qd; Y_dq, Y_qq]`, and the following operating-point
    vectors (in synchronous coordinates aligned with the PCC voltage): grid current
    `i_g0`, grid voltage `e_g0`, PCC voltage `u_g0` and converter voltage `u_c0`. The
    results can be saved, e.g., by ``scipy.io.savemat(path, dataclasses.asdict(res))``.

    """

    f_e: np.ndarray = field(default_factory=empty_array)
    Y_dd: np.ndarray = field(default_factory=empty_array)
    Y_qd: np.ndarray = field(default_factory=empty_array)
    Y_dq: np.ndarray = field(default_factory=empty_array)
    Y_qq: np.ndarray = field(default_factory=empty_array)
    i_g0: complex = 0j
    e_g0: complex = 0j
    u_g0: complex = 0j
    u_c0: complex = 0j


# %%
def _operating_point(
    mdl: model.GridConverterSystem,
    ctrl: control.GridConverterControlSystem,
    cfg: MeasurementCfg,
) -> tuple[
    model.GridConverterSystem,
    control.GridConverterControlSystem,
    OutputAdmittance,
    float,
]:
    """Simulate the system to the operating point, giving also the sampling period."""
    # Simulate the original system to the operating point, with the grid frequency
    # of the operating point
    w_g = mdl.ac_source.w_g
    w_g = w_g(cfg.t0) if callable(w_g) else w_g
    T_nom = 2 * np.pi / w_g
    t_stop = np.ceil(cfg.t0 / T_nom) * T_nom + cfg.n_periods_init * T_nom
    res = simulate(deepcopy(mdl), deepcopy(ctrl), t_stop, cfg.N_eval)

    # Fundamental-frequency vectors in coordinates aligned with the PCC voltage
    f_nom = w_g * 0.5 / np.pi
    t, filt = res.mdl.t, res.mdl.ac_filter
    T = cfg.n_periods_init / f_nom
    vectors = [
        0.5 * dft(t, x, f_nom, T)
        for x in (filt.i_g_ab, filt.e_g_ab, filt.u_g_ab, filt.u_c_ab)
    ]
    i_g0, e_g0, u_g0, u_c0 = np.exp(-1j * np.angle(vectors[2])) * np.array(vectors)
    operating_point = OutputAdmittance(i_g0=i_g0, e_g0=e_g0, u_g0=u_g0, u_c0=u_c0)

    # The PCC voltage is imposed by a stiff source with signal injection at the
    # operating point: the grid impedance is removed, and the source has the PCC
    # voltage magnitude and the frequency of the operating point. The DC bus is copied
    # together with the converter, since it refers to the converter. The PWM settings
    # are kept.
    ac_filter = deepcopy(mdl.ac_filter)
    ac_filter.L_g, ac_filter.R_g = 0.0, 0.0
    ac_source = model.ThreePhaseSourceWithSignalInjection(w_g=w_g, e_g=np.abs(u_g0))
    converter, dc_bus = deepcopy((mdl.converter, mdl.dc_bus))
    mdl_inj = model.GridConverterSystem(
        converter, ac_filter, ac_source, dc_bus=dc_bus, single_update=mdl.single_update
    )
    mdl_inj.pwm, mdl_inj.delay = deepcopy(mdl.pwm), deepcopy(mdl.delay)
    ctrl_inj = deepcopy(ctrl)
    simulate(mdl_inj, ctrl_inj, t_stop, cfg.N_eval)

    return mdl_inj, ctrl_inj, operating_point, sampling_period(res)


def _measure_at_frequency(
    cfg: MeasurementCfg,
    mdl0: model.GridConverterSystem,
    ctrl0: control.GridConverterControlSystem,
    T_s: float,
    excitation: tuple[float, float],
) -> np.ndarray:
    """Compute the output admittance matrix at a single frequency."""
    f_e, abs_u_e = excitation
    N_eval = evaluation_points(cfg.N_eval, f_e, T_s)
    U, I = np.zeros((2, 2), complex), np.zeros((2, 2), complex)  # noqa: E741
    # Inject the excitation in the d- and q-axes, one at a time
    for k, u_e in enumerate((abs_u_e, 1j * abs_u_e)):
        mdl, ctrl = deepcopy(mdl0), deepcopy(ctrl0)
        source = mdl.ac_source
        assert isinstance(source, model.ThreePhaseSourceWithSignalInjection)
        source.f_e, source.u_e = f_e, u_e
        t_stop = mdl.t0 + cfg.t1 + cfg.n_periods_excitation / f_e
        res = simulate(mdl, ctrl, t_stop, N_eval, f_e)
        # Voltage and current in synchronous coordinates
        exp_j_theta_g = res.mdl.ac_source.exp_j_theta_g
        u_g = np.conj(exp_j_theta_g) * res.mdl.ac_filter.u_g_ab
        i_g = np.conj(exp_j_theta_g) * res.mdl.ac_filter.i_g_ab
        t, T, w = res.mdl.t, cfg.n_periods_excitation / f_e, cfg.use_window
        U[:, k] = dft(t, u_g.real, f_e, T, w), dft(t, u_g.imag, f_e, T, w)
        I[:, k] = dft(t, i_g.real, f_e, T, w), dft(t, i_g.imag, f_e, T, w)
    return -I @ np.linalg.inv(U)


# %%
def measure_output_admittance(
    mdl: model.GridConverterSystem,
    ctrl: control.GridConverterControlSystem,
    cfg: MeasurementCfg,
) -> OutputAdmittance:
    """
    Measure the output admittance of the converter.

    The system is first simulated to the operating point. Then, the output admittance
    of the converter is measured at the PCC: the PCC voltage is imposed by a stiff
    voltage source, whose magnitude and frequency equal those of the operating point,
    and small-signal voltage excitations are injected in the d- and q-axes. The grid
    impedance of `mdl` as well as any time variation and negative-sequence component of
    its source only affect the operating point, whose grid frequency is that of the
    source at `t0`. A DC bus of `mdl` is included in the measurement.

    Parameters
    ----------
    mdl : GridConverterSystem
        Continuous-time system model.
    ctrl : GridConverterControlSystem
        Discrete-time control system.
    cfg : MeasurementCfg
        Measurement configuration.

    Returns
    -------
    OutputAdmittance
        Admittance matrix elements and the operating point.

    Notes
    -----
    With carrier-comparison PWM, background switching harmonics can bias the measured
    admittance at the excitation frequency. Results near switching harmonics and their
    sidebands may depend strongly on the excitation amplitude and its phase relative to
    the carrier, even when the numerical solution has converged.

    """
    mdl_inj, ctrl_inj, res, T_s = _operating_point(mdl, ctrl, cfg)
    n_freqs = np.size(cfg.freqs)
    amplitudes = cfg.abs_u_e * np.linspace(1.0, cfg.amplitude_multiplier, n_freqs)
    excitations = list(zip(cfg.freqs, amplitudes, strict=True))
    task = partial(_measure_at_frequency, cfg, mdl_inj, ctrl_inj, T_s)
    Y_c = np.array(run_frequency_sweep(task, excitations, cfg.multiprocess))
    res.f_e = np.array(cfg.freqs, dtype=float)  # A copy, independent of cfg
    res.Y_dd, res.Y_qd = Y_c[:, 0, 0], Y_c[:, 0, 1]
    res.Y_dq, res.Y_qq = Y_c[:, 1, 0], Y_c[:, 1, 1]
    return res


# %%
def plot_output_admittance(
    res: OutputAdmittance,
    form: Literal["polar", "re_im"] = "re_im",
    passivity_index: bool = True,
    latex: bool = False,
) -> None:
    """
    Plot the elements of the output admittance matrix.

    Parameters
    ----------
    res : OutputAdmittance
        Output admittance.
    form : Literal["polar", "re_im"], optional
        Form of the elements, defaults to "re_im". Options are:
        - "polar": magnitude and phase
        - "re_im": real and imaginary parts
    passivity_index : bool, optional
        Plot also the input feedforward passivity index computed from the admittance
        matrix, defaults to True.
    latex : bool, optional
        Use latex for plots, defaults to False.

    """
    set_style(latex)
    _plot_admittance_matrix(res, form)
    if passivity_index:
        _plot_passivity_index(res)


def _plot_admittance_matrix(res: OutputAdmittance, form: str) -> None:
    """Plot the elements, two rows per element, dd and dq left, qd and qq right."""
    names = [["dd", "qd"], ["dq", "qq"]]
    if form == "polar":
        fig, axs = plt.subplots(4, 2, sharey="row")
    else:
        fig, axs = plt.subplots(4, 2, sharex=True, sharey=True)
    for i, pair in enumerate(names):
        for j, name in enumerate(pair):
            Y, (ax_a, ax_b) = getattr(res, f"Y_{name}"), axs[2 * i : 2 * i + 2, j]
            Y_name = r"Y_\mathrm{" + name + "}"
            if form == "polar":
                ax_a.loglog(res.f_e, np.abs(Y))
                ax_b.semilogx(res.f_e, np.unwrap(np.angle(Y, deg=True), period=360))
                ax_a.set_ylabel(r"$|" + Y_name + r"|\ (\mathrm{S})$")
                ax_b.set_ylabel(r"$\angle " + Y_name + r"\ (\mathrm{deg})$")
            else:
                ax_a.semilogx(res.f_e, np.real(Y))
                ax_b.semilogx(res.f_e, np.imag(Y))
                ax_a.set_ylabel(r"$\mathrm{Re}\{" + Y_name + r"\}\ (\mathrm{S})$")
                ax_b.set_ylabel(r"$\mathrm{Im}\{" + Y_name + r"\}\ (\mathrm{S})$")
    if form == "polar":
        # The same limits for all the magnitudes and for all the phases
        for k in (0, 1):
            limits = [axs[row, 0].get_ylim() for row in (k, k + 2)]
            y_lim = (min(lim[0] for lim in limits), max(lim[1] for lim in limits))
            for row in (k, k + 2):
                axs[row, 0].set_ylim(y_lim)
    for ax in axs[:, 1]:
        ax.tick_params(axis="y", labelleft=True)
    for ax in axs[-1, :]:
        ax.set_xlabel("Frequency (Hz)")
    for ax in axs.flat:
        ax.margins(x=0)
    fig.align_ylabels()
    plt.show()


def _plot_passivity_index(res: OutputAdmittance) -> None:
    """Plot the input feedforward passivity index of the admittance matrix."""
    _, ax = plt.subplots(1, 1, figsize=(4, 3))
    Y_c = np.array([[res.Y_dd, res.Y_qd], [res.Y_dq, res.Y_qq]])
    Y_c = np.moveaxis(Y_c, -1, 0)
    nu_F = 0.5 * np.min(np.linalg.eigvals(Y_c + np.matrix_transpose(Y_c.conj())), 1)
    ax.axhline(0, linestyle="--", color="k", linewidth="1")
    ax.semilogx(res.f_e, nu_F.real)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Passivity index")
    ax.margins(x=0)
    plt.show()


def plot_operating_point(
    res: OutputAdmittance, base: utils.BaseValues, latex: bool = False
) -> None:
    """
    Plot the converter voltage, PCC voltage, grid voltage, and grid current vectors of
    the operating point.

    Parameters
    ----------
    res : OutputAdmittance
        Output admittance with the operating point.
    base : BaseValues
        Base values for per-unit conversion.
    latex : bool, optional
        Use latex for plots, defaults to False.

    """
    set_style(latex)
    _, ax = plt.subplots()
    ax.grid(True, zorder=0)
    ax.add_patch(Circle((0, 0), 1, fill=False, edgecolor="gray", zorder=1))
    vectors = [
        (res.e_g0 / base.u, "blue", r"$\mathbf{e}_\mathrm{g0}$"),
        (res.u_g0 / base.u, "red", r"$\mathbf{u}_\mathrm{g0}$"),
        (res.u_c0 / base.u, "black", r"$\mathbf{u}_\mathrm{c0}$"),
        (res.i_g0 / base.i, "green", r"$\mathbf{i}_\mathrm{g0}$"),
    ]
    for x, color, label in vectors:
        ax.quiver(
            0,
            0,
            x.real,
            x.imag,
            angles="xy",
            scale_units="xy",
            scale=1,
            color=color,
            label=label,
            zorder=2,
        )
    ticks = [-1, -0.5, 0, 0.5, 1]
    ax.set_xlabel("d (p.u.)")
    ax.set_ylabel("q (p.u.)")
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.legend(loc="upper left")
    ax.set_aspect("equal")
    plt.show()
