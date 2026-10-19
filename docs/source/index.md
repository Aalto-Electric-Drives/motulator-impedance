# *motulator-impedance:* Mechanical Impedance and Output Admittance for *motulator*

This package measures small-signal frequency responses of systems built in [*motulator*](https://aalto-electric-drives.github.io/motulator/) by frequency sweeps: the system is simulated to its operating point, a small-signal excitation is injected one frequency at a time, and the response is computed with the discrete Fourier transform. Two responses are provided:

- The **mechanical impedance** $Z_\mathrm{M}(s) = -\Delta\tau_\mathrm{M}(s)/\Delta\omega_\mathrm{M}(s)$ of a machine drive describes the dynamics of the machine and its control system as seen from the shaft {cite}`Har2023`. The rotor speed is imposed, and speed excitations are superimposed on it. A drive whose mechanical impedance is passive, i.e., its phase is within ±90°, is stable with any passive mechanical system.
- The **output admittance** of a grid converter at the point of common coupling {cite}`Maa2026` is a 2×2 matrix in synchronous coordinates. The PCC voltage is imposed by a stiff source, and voltage excitations are injected in the d- and q-axes. The admittance is the basis of impedance-based stability analysis, e.g., through its passivity index.

This documentation covers only the measurements. The system models and control methods are described in the [documentation of *motulator*](https://aalto-electric-drives.github.io/motulator/).

```{toctree}
---
titlesonly:
caption: Getting Started
name: getting_started
maxdepth: 1
---
installation
usage
```

```{toctree}
---
titlesonly:
caption: Examples
name: examples
maxdepth: 1
---
examples/index
```

```{toctree}
---
titlesonly:
caption: Reference
name: reference
maxdepth: 1
---
API <autoapi/motulator_impedance/index>
bibliography
motulator <https://aalto-electric-drives.github.io/motulator/>
```
