# motulator-impedance

**Mechanical impedance of machine drives and output admittance of grid converters for [motulator](https://github.com/Aalto-Electric-Drives/motulator)**

Documentation: https://aalto-electric-drives.github.io/motulator-impedance/

This package measures small-signal frequency responses of systems built in *motulator* by frequency sweeps: the system is simulated to its operating point, a small-signal excitation is injected one frequency at a time, and the response is computed with the discrete Fourier transform. The frequencies are simulated in parallel. Two responses are provided:

- **Mechanical impedance** $Z_\mathrm{M}(s) = -\Delta\tau_\mathrm{M}(s)/\Delta\omega_\mathrm{M}(s)$ of a machine drive, which describes the dynamics of the machine and its control system as seen from the shaft [1]. The rotor speed is imposed, and speed excitations are superimposed on it. A drive whose mechanical impedance is passive (its phase within ±90°) is stable with any passive mechanical system.
- **Output admittance** of a grid converter at the point of common coupling [2], as a 2×2 matrix in synchronous coordinates. The PCC voltage is imposed by a stiff source, and voltage excitations are injected in the d- and q-axes. The admittance is the basis of impedance-based stability analysis, e.g., through its passivity index.

**Status:** The package is in early development, and its interfaces may change before version 1.0. It currently supports *motulator* 0.15, and the support is extended after each new release of *motulator* has been tested.

## Installation

The package is not yet on PyPI. Install it from a clone (*motulator* is installed as a dependency):

```bash
pip install -e .
```

## Usage

The system model and the control system are built in *motulator* as usual. The mechanical impedance of a drive, whose rotor speed is imposed by `ExternalRotorSpeed`:

```python
import motulator.drive.control.im as control
import numpy as np
from motulator.drive import model

from motulator_impedance import drive

par = model.InductionMachineInvGammaPars(
    n_p=2, R_s=60e-3, R_R=30e-3, L_sgm=2.2e-3, L_M=24.5e-3
)
mechanics = model.ExternalRotorSpeed()
mechanics.set_external_rotor_speed(40.0)  # Operating-point speed (rad/s)
mdl = model.Drive(
    model.InductionMachine(par), mechanics, model.VoltageSourceConverter(u_dc=540)
)
cfg = control.ObserverBasedVHzControllerCfg(psi_s_nom=1.04, i_s_max=170.0)
ctrl = control.VHzControlSystem(control.ObserverBasedVHzController(par, cfg))
ctrl.set_speed_ref(40.0)

meas_cfg = drive.MeasurementCfg(abs_w_e=0.3, freqs=np.geomspace(1, 500, 50))
Z_M = drive.measure_mechanical_impedance(mdl, ctrl, meas_cfg)
drive.plot_mechanical_impedance(Z_M)
```

The output admittance of a grid converter:

```python
from motulator.grid import control, model

from motulator_impedance import grid

mdl = model.GridConverterSystem(
    model.VoltageSourceConverter(u_dc=650),
    model.LFilter(L_f=5e-3),
    model.ThreePhaseSource(w_g=2 * np.pi * 50, e_g=326.6),
)
cfg = control.CurrentVectorControllerCfg(i_max=30.0, L=5e-3, T_s=1 / 10e3)
ctrl = control.GridConverterControlSystem(control.CurrentVectorController(cfg))
ctrl.set_power_ref(5e3)
ctrl.set_reactive_power_ref(0.0)

meas_cfg = grid.MeasurementCfg(abs_u_e=3.0, freqs=np.geomspace(1, 10e3, 100))
Y = grid.measure_output_admittance(mdl, ctrl, meas_cfg)
grid.plot_output_admittance(Y, form="re_im")
```

The results are dataclasses, which can be saved, e.g., by `scipy.io.savemat(path, dataclasses.asdict(Y))`. Complete examples are in the [example gallery](https://aalto-electric-drives.github.io/motulator-impedance/examples/index.html).

## Scope

- The frequencies are simulated in parallel processes by default (`multiprocess=True`), so the model and the control system must be picklable: use module-level functions or callable objects as references, not lambda functions.
- With carrier-comparison PWM, background switching harmonics can bias the measured admittance near the switching harmonics and their sidebands.
- The grid impedance and the DC bus of the system model are included in the operating point; the admittance is measured with the PCC voltage imposed.

## References

1. Hartikainen, Tiitinen, Laine, Hinkkanen, "Identification of mechanical impedance of an electric machine drive for drivetrain design," Proc. IEEE IEMDC, 2023, https://doi.org/10.1109/IEMDC55163.2023.10238992
1. Määttä, Kukkola, Seppänen, Hinkkanen, "Open-source Python tool for grid converter output admittance identification," 2026, https://arxiv.org/abs/2607.10653

## License

MIT
