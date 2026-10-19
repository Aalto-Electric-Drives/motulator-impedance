"""Tests of the output admittance measurement."""

from collections.abc import Callable

import numpy as np
import pytest
from motulator.grid import control, model

from motulator_impedance import grid
from motulator_impedance._sweep import dft

U_NOM = np.sqrt(2 / 3) * 400  # Peak phase voltage
W_NOM = 2 * np.pi * 50
Z_BASE = U_NOM / (np.sqrt(2) * 10)
L_BASE = Z_BASE / W_NOM


def grid_frequency(t: float) -> float:
    """Grid angular frequency (rad/s) stepping from 50 Hz to 60 Hz at 50 ms."""
    return 1.2 * W_NOM if t > 0.05 else W_NOM


def system(
    u_dc: float | None = 650,
    w_g: float | Callable[[float], float] = W_NOM,
    pwm: bool = False,
    single_update: bool = False,
) -> model.GridConverterSystem:
    """Grid converter system, fed by a DC bus if `u_dc` is None."""
    converter = model.VoltageSourceConverter(u_dc=u_dc)
    dc_bus = None if u_dc else model.DCBus(C_dc=1e-3, u_dc=650, converters=[converter])
    return model.GridConverterSystem(
        converter,
        model.LFilter(L_f=0.2 * L_BASE),
        model.ThreePhaseSource(w_g=w_g, e_g=U_NOM),
        dc_bus=dc_bus,
        pwm=pwm,
        single_update=single_update,
    )


def test_dft_of_unevenly_sampled_signal() -> None:
    """The DFT finds a sinusoid sampled at uneven instants."""
    t = np.sort(np.random.default_rng(0).uniform(0, 0.1, 4000))
    u = 2.0 * np.cos(2 * np.pi * 50 * t + 0.3)
    for window in (False, True):
        y = dft(t, u, 50.0, 0.06, window)
        assert y == pytest.approx(2.0 * np.exp(0.3j), rel=1e-3)
    with pytest.raises(ValueError, match="three periods"):
        dft(t, u, 50.0, 0.04, window=True)  # Two periods: the DC would leak


@pytest.mark.parametrize("dc_bus", [False, True])
def test_admittance_at_sampling_frequency(dc_bus: bool) -> None:
    """
    The measured GFL admittance at the sampling frequency and at its multiple is that
    of the filter.
    """
    # At the sampling frequency and its multiples, the excitation aliases to zero
    # frequency in the sampled control system, so the converter voltage does not
    # respond to it. The results at the multiple need more evaluation points than the
    # default per sampling period.
    T_s, L_f = 1e-4, 0.2 * L_BASE
    cfg = control.CurrentVectorControllerCfg(i_max=30, L=L_f, T_s=T_s)
    if dc_bus:
        mdl = system(u_dc=None)
        assert mdl.dc_bus is not None
        mdl.dc_bus.set_external_dc_current(10.0)
        dc_bus_ctrl = control.DCBusVoltageController(
            C_dc=1e-3, alpha_dc=2 * np.pi * 30, p_max=10e3
        )
        ctrl = control.GridConverterControlSystem(
            control.CurrentVectorController(cfg), dc_bus_ctrl
        )
        ctrl.set_dc_bus_voltage_ref(650.0)
    else:
        mdl = system()
        ctrl = control.GridConverterControlSystem(control.CurrentVectorController(cfg))
        ctrl.set_power_ref(5e3)
    ctrl.set_reactive_power_ref(0.0)
    freqs = np.array([1 / T_s, 5 / T_s])
    meas_cfg = grid.MeasurementCfg(
        abs_u_e=0.05 * U_NOM, freqs=freqs, t0=0.1, t1=0.02, multiprocess=False
    )
    res = grid.measure_output_admittance(mdl, ctrl, meas_cfg)

    Y_L = 1 / (2j * np.pi * freqs * L_f)
    assert res.Y_dd == pytest.approx(Y_L, rel=0.05)
    freqs *= 2  # The results do not share the frequency array with the configuration
    assert res.f_e[0] == pytest.approx(1 / T_s)


def test_operating_point_at_changed_grid_frequency() -> None:
    """The operating point is computed at the grid frequency reached at `t0`."""
    T_s, L_f = 1e-4, 0.2 * L_BASE
    mdl = system(w_g=grid_frequency)
    cfg = control.CurrentVectorControllerCfg(i_max=30, L=L_f, T_s=T_s)
    ctrl = control.GridConverterControlSystem(control.CurrentVectorController(cfg))
    ctrl.set_power_ref(5e3)
    ctrl.set_reactive_power_ref(0.0)
    meas_cfg = grid.MeasurementCfg(
        abs_u_e=0.05 * U_NOM, freqs=np.array([1 / T_s]), t0=0.2, multiprocess=False
    )
    res = grid.measure_output_admittance(mdl, ctrl, meas_cfg)
    assert abs(res.u_g0) == pytest.approx(U_NOM, rel=0.01)
    assert res.Y_dd[0] == pytest.approx(1 / (2j * np.pi * res.f_e[0] * L_f), rel=0.05)


def test_measurement_model_keeps_pwm_settings() -> None:
    """The model of the measurement has the PWM settings of the system model."""
    mdl = system(pwm=True, single_update=True)
    cfg = control.CurrentVectorControllerCfg(i_max=30, L=0.2 * L_BASE, T_s=1e-4)
    ctrl = control.GridConverterControlSystem(control.CurrentVectorController(cfg))
    ctrl.set_power_ref(5e3)
    ctrl.set_reactive_power_ref(0.0)
    meas_cfg = grid.MeasurementCfg(abs_u_e=0.05 * U_NOM, t0=0.02)
    mdl_inj, *_ = grid._operating_point(mdl, ctrl, meas_cfg)
    assert mdl_inj.single_update
    assert type(mdl_inj.pwm) is type(mdl.pwm)


def test_parallel_sweep_equals_serial() -> None:
    """The frequencies simulated in parallel processes give the serial results."""
    mdl = system()
    cfg = control.CurrentVectorControllerCfg(i_max=30, L=0.2 * L_BASE, T_s=1e-4)
    ctrl = control.GridConverterControlSystem(control.CurrentVectorController(cfg))
    ctrl.set_power_ref(5e3)
    ctrl.set_reactive_power_ref(0.0)
    serial, parallel = (
        grid.measure_output_admittance(
            mdl,
            ctrl,
            grid.MeasurementCfg(
                abs_u_e=0.05 * U_NOM,
                freqs=np.array([500.0, 2e3]),
                t0=0.1,
                t1=0.02,
                multiprocess=multiprocess,
            ),
        )
        for multiprocess in (False, True)
    )
    for Y in ("Y_dd", "Y_qd", "Y_dq", "Y_qq"):
        np.testing.assert_allclose(getattr(parallel, Y), getattr(serial, Y), rtol=1e-9)
