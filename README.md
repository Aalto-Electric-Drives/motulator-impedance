# motulator-impedance

**Mechanical impedance of machine drives and output admittance of grid converters for [motulator](https://github.com/Aalto-Electric-Drives/motulator)**

[![PyPI version](https://img.shields.io/pypi/v/motulator-impedance.svg)](https://pypi.org/project/motulator-impedance/)

Documentation: https://aalto-electric-drives.github.io/motulator-impedance/

This package measures small-signal frequency responses of systems built in *motulator* by frequency sweeps: the system is simulated to its operating point, a small-signal excitation is injected one frequency at a time, and the response is computed with the discrete Fourier transform. The frequencies are simulated in parallel. Two responses are provided:

- **Mechanical impedance** <i>Z</i><sub>M</sub>(<i>s</i>) = −Δ<i>τ</i><sub>M</sub>(<i>s</i>)/Δ<i>ω</i><sub>M</sub>(<i>s</i>) of a machine drive, which describes the dynamics of the machine and its control system as seen from the shaft [[1]](#references). The rotor speed is imposed, and speed excitations are superimposed on it. A drive whose mechanical impedance is passive (its phase within ±90°) is stable with any passive mechanical system.
- **Output admittance** of a grid converter at the point of common coupling [[2]](#references), as a 2×2 matrix in synchronous coordinates. The PCC voltage is imposed by a stiff source, and voltage excitations are injected in the d- and q-axes. The admittance is the basis of impedance-based stability analysis, e.g., through its passivity index.

## Installation

Install the package from PyPI in a [virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/) (*motulator* is installed as a dependency). On Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install motulator-impedance
```

On Windows, the environment is created and activated with `py -m venv .venv` and `.venv\Scripts\activate`.

For development, clone the repository and install the package with `pip install -e ".[dev]"`.

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

if __name__ == "__main__":  # Needed for the parallel processes, see Scope
    Z_M = drive.measure_mechanical_impedance(mdl, ctrl, meas_cfg)
    drive.plot_mechanical_impedance(Z_M)
```

The output admittance of a grid converter:

```python
import numpy as np
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

if __name__ == "__main__":
    Y = grid.measure_output_admittance(mdl, ctrl, meas_cfg)
    grid.plot_output_admittance(Y, form="re_im")
```

The results are dataclasses, which can be saved, e.g., by `scipy.io.savemat(path, dataclasses.asdict(Y))`. Complete examples are in the [example gallery](https://aalto-electric-drives.github.io/motulator-impedance/examples/index.html).

## Scope

- The frequencies are simulated in parallel processes by default (`multiprocess=True`), so the model and the control system must be picklable: use module-level functions or callable objects as references, not lambda functions. In a script, call the measurement under `if __name__ == "__main__":`, since the processes import the script again on Windows and macOS, as well as on Linux from Python 3.14 onward. In the interactive interpreter, use `multiprocess=False`.
- With carrier-comparison PWM, background switching harmonics can bias the measured admittance near the switching harmonics and their sidebands.
- The grid impedance and the DC bus of the system model are included in the operating point; the admittance is measured with the PCC voltage imposed.

## References

1. Hartikainen, Tiitinen, Laine, Hinkkanen, "Identification of mechanical impedance of an electric machine drive for drivetrain design," Proc. IEEE IEMDC, 2023, https://doi.org/10.1109/IEMDC55163.2023.10238992
1. Määttä, Kukkola, Seppänen, Hinkkanen, "Open-source Python tool for grid converter output admittance identification," 2026, https://arxiv.org/abs/2607.10653

## Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->

<!-- prettier-ignore-start -->

<!-- markdownlint-disable -->

<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/maattaj11"><img src="https://avatars.githubusercontent.com/u/165767331?v=4?s=50" width="50px;" alt="Juho Määttä"/><br /><sub><b>Juho Määttä</b></sub></a><br /><a href="https://github.com/Aalto-Electric-Drives/motulator-impedance/commits?author=maattaj11" title="Code">💻</a> <a href="#example-maattaj11" title="Examples">💡</a> <a href="#ideas-maattaj11" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/HannuHar"><img src="https://avatars.githubusercontent.com/u/96597650?v=4?s=50" width="50px;" alt="Hannu Hartikainen"/><br /><sub><b>Hannu Hartikainen</b></sub></a><br /><a href="https://github.com/Aalto-Electric-Drives/motulator-impedance/commits?author=HannuHar" title="Code">💻</a> <a href="#ideas-HannuHar" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/lauritapio"><img src="https://avatars.githubusercontent.com/u/85596019?v=4?s=50" width="50px;" alt="Lauri Tiitinen"/><br /><sub><b>Lauri Tiitinen</b></sub></a><br /><a href="https://github.com/Aalto-Electric-Drives/motulator-impedance/commits?author=lauritapio" title="Code">💻</a> <a href="#ideas-lauritapio" title="Ideas, Planning, & Feedback">🤔</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://research.aalto.fi/en/persons/marko-hinkkanen"><img src="https://avatars.githubusercontent.com/u/76600872?v=4?s=50" width="50px;" alt="Marko Hinkkanen"/><br /><sub><b>Marko Hinkkanen</b></sub></a><br /><a href="https://github.com/Aalto-Electric-Drives/motulator-impedance/commits?author=mhinkkan" title="Code">💻</a> <a href="#ideas-mhinkkan" title="Ideas, Planning, & Feedback">🤔</a> <a href="#example-mhinkkan" title="Examples">💡</a> <a href="#mentoring-mhinkkan" title="Mentoring">🧑‍🏫</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->

<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->
