"""
10-kVA, GFL, output admittance
==============================

This example measures the output admittance of a 10-kVA grid-following (GFL)
converter. The converter and grid models are the same as in the example
`10-kVA GFL converter
<https://aalto-electric-drives.github.io/motulator/grid_examples/grid_following/plot_10kva_gfl.html>`_
of motulator.

"""

# %%
import numpy as np
from motulator.grid import control, model, utils

from motulator_impedance import grid

# %%
# Compute base values based on the nominal values.

nom = utils.NominalValues(U=400, I=14.5, f=50, P=10e3)
base = utils.BaseValues.from_nominal(nom)

# %%
# Configure the measurement.

meas_cfg = grid.MeasurementCfg(abs_u_e=0.01 * base.u, freqs=np.geomspace(1, 10e3, 100))

# %%
# Configure the system model.

ac_filter = model.LFilter(L_f=0.2 * base.L)
ac_source = model.ThreePhaseSource(w_g=base.w, e_g=base.u)
converter = model.VoltageSourceConverter(u_dc=650)
mdl = model.GridConverterSystem(converter, ac_filter, ac_source)

# %%
# Configure the control system.

cfg = control.CurrentVectorControllerCfg(
    i_max=1.5 * base.i, L=0.2 * base.L, T_s=1 / 10e3
)
inner_ctrl = control.CurrentVectorController(cfg)
ctrl = control.GridConverterControlSystem(inner_ctrl)

# Set the references
ctrl.set_power_ref(0.5 * base.p)
ctrl.set_reactive_power_ref(0.5 * base.p)

# %%
# Measure the output admittance and plot the results.

if __name__ == "__main__":
    res = grid.measure_output_admittance(mdl, ctrl, meas_cfg)
    # To save the results, e.g., in MATLAB format:
    # from dataclasses import asdict
    # from scipy.io import savemat
    # savemat("gfl_admittance.mat", asdict(res))
    grid.plot_output_admittance(res, form="re_im")
    grid.plot_operating_point(res, base)
