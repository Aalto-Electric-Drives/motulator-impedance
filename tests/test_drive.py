"""Tests of the mechanical impedance measurement."""

from math import pi

import motulator.drive.control.im as im_control
import numpy as np
import pytest
from motulator.drive import model

from motulator_impedance import drive

PAR = im_control.InductionMachineInvGammaPars(
    n_p=2, R_s=3.7, R_R=2.1, L_sgm=0.021, L_M=0.224
)


def test_mechanical_impedance_of_open_loop_vhz() -> None:
    """The measured mechanical impedance equals that of the linearized machine."""
    # Under open-loop V/Hz control, the stator voltage is constant in coordinates
    # rotating at w_s, so the mechanical impedance is that of the machine alone
    R_s, R_R, L_sgm, L_M, n_p = PAR.R_s, PAR.R_R, PAR.L_sgm, PAR.L_M, PAR.n_p
    w_s, psi_s, w_M0 = 2 * pi * 25, 1.04, 70.0  # Slip 2*pi*25 - 2*70 = 17 rad/s
    mdl = model.Drive(
        model.InductionMachine(PAR),
        model.ExternalRotorSpeed(),
        model.VoltageSourceConverter(u_dc=540),
    )
    mdl.mechanics.set_external_rotor_speed(w_M0)
    est_par = im_control.InductionMachineInvGammaPars(
        n_p=n_p, R_s=0, R_R=0, L_sgm=0, L_M=np.inf
    )
    cfg = im_control.ObserverBasedVHzControllerCfg(
        psi_s_nom=psi_s, i_s_max=np.inf, alpha_f=0, alpha_tau=0, alpha_psi=0
    )
    ctrl = im_control.VHzControlSystem(
        im_control.ObserverBasedVHzController(est_par, cfg)
    )
    ctrl.set_speed_ref(w_s / n_p)
    freqs = np.array([10.0, 100.0])
    meas_cfg = drive.MeasurementCfg(
        abs_w_e=0.5, freqs=freqs, t0=0.5, t1=0.2, multiprocess=False
    )
    res = drive.measure_mechanical_impedance(mdl, ctrl, meas_cfg)

    # Linearized model in coordinates rotating at w_s, the real state vector being
    # [Re{psi_s}, Re{psi_R}, Im{psi_s}, Im{psi_R}]
    A_c = np.array(
        [
            [-R_s / L_sgm - 1j * w_s, R_s / L_sgm],
            [R_R / L_sgm, -R_R / L_sgm - R_R / L_M - 1j * (w_s - n_p * w_M0)],
        ]
    )
    psi_s0, psi_R0 = np.linalg.solve(A_c, [-1j * w_s * psi_s, 0])
    i_s0 = (psi_s0 - psi_R0) / L_sgm
    A = np.block([[np.real(A_c), -np.imag(A_c)], [np.imag(A_c), np.real(A_c)]])
    b_c = np.array([0, 1j * n_p * psi_R0])  # Input vector of the rotor speed
    B = np.concatenate((np.real(b_c), np.imag(b_c)))

    def im_row(r: np.ndarray) -> np.ndarray:
        """Row vector of the real state vector giving Im{r @ [psi_s, psi_R]}."""
        return np.concatenate((np.imag(r), np.real(r)))

    # Torque 1.5*n_p*Im{i_s*conj(psi_R)}, linearized
    C = im_row(np.conj(psi_R0) * np.array([1, -1]) / L_sgm)
    C -= im_row(np.conj(i_s0) * np.array([0, 1]))
    C *= 1.5 * n_p
    tau_M0 = 1.5 * n_p * np.imag(i_s0 * np.conj(psi_R0))
    Z_M = [-C @ np.linalg.solve(2j * pi * f * np.eye(4) - A, B) for f in freqs]

    assert res.w_M0 == pytest.approx(w_M0)
    assert res.tau_M0 == pytest.approx(tau_M0, rel=0.01)
    assert res.Z_M == pytest.approx(Z_M, rel=0.01)


class _FailingControlSystem(im_control.VHzControlSystem):
    """Control system raising a numerical failure after the time `t_fail`."""

    t_fail = 0.0

    def compute_output(self, fbk):
        if self.t > self.t_fail:
            raise FloatingPointError("test")
        return super().compute_output(fbk)


@pytest.mark.filterwarnings("ignore:Simulation stopped:RuntimeWarning")
def test_failed_simulation_raises() -> None:
    """A simulation failing during the excitation stops the measurement."""
    mdl = model.Drive(
        model.InductionMachine(PAR),
        model.ExternalRotorSpeed(),
        model.VoltageSourceConverter(u_dc=540),
    )
    mdl.mechanics.set_external_rotor_speed(70.0)
    cfg = im_control.ObserverBasedVHzControllerCfg(psi_s_nom=1.04, i_s_max=10.6)
    ctrl = _FailingControlSystem(im_control.ObserverBasedVHzController(PAR, cfg))
    ctrl.set_speed_ref(70.0)
    ctrl.t_fail = 0.15  # After the operating point
    meas_cfg = drive.MeasurementCfg(
        abs_w_e=0.5, freqs=np.array([10.0]), t0=0.1, t1=0.1, multiprocess=False
    )
    with pytest.raises(RuntimeError, match="simulation failed"):
        drive.measure_mechanical_impedance(mdl, ctrl, meas_cfg)


def test_mechanics_must_be_external_rotor_speed() -> None:
    """The rotor speed must be imposed by ExternalRotorSpeed."""
    mdl = model.Drive(
        model.InductionMachine(PAR),
        model.MechanicalSystem(J=0.015),
        model.VoltageSourceConverter(u_dc=540),
    )
    cfg = im_control.ObserverBasedVHzControllerCfg(psi_s_nom=1.04, i_s_max=10.6)
    ctrl = im_control.VHzControlSystem(im_control.ObserverBasedVHzController(PAR, cfg))
    ctrl.set_speed_ref(50.0)
    with pytest.raises(TypeError, match="ExternalRotorSpeed"):
        drive.measure_mechanical_impedance(mdl, ctrl, drive.MeasurementCfg(abs_w_e=1))
