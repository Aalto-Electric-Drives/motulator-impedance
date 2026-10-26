# Installation

The package requires Python 3.12 or newer, and it installs *motulator* as its dependency. It supports *motulator* 0.15, 0.16, 0.17, and 0.18, and the support is extended after each new release of *motulator* has been tested.

## Option 1: Use pip

Install the package in a [virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/). On Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install motulator-impedance
```

On Windows:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install motulator-impedance
```

If PowerShell does not allow running the activation script, allow it with `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`.

The plots need a GUI library for *matplotlib*. On some Linux systems, it must be installed separately; see the [installation of *motulator*](https://aalto-electric-drives.github.io/motulator/installation.html).

## Option 2: Clone the Repository

Clone the repository to run the examples or to develop the package. On Linux and macOS:

```bash
git clone https://github.com/Aalto-Electric-Drives/motulator-impedance
cd motulator-impedance
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,doc]"
```

On Windows, create and activate the virtual environment as in Option 1. The `dev` dependencies are needed for the tests and the code checks, and the `doc` dependencies for building this documentation. In [VS Code](https://code.visualstudio.com/docs/python/environments), the virtual environment can also be created with the Python extension.

Then run an example, e.g.:

```bash
python examples/drive/plot_45kw_im_vhz_mechanical_impedance.py
```

The tests are run with `pytest`, and the documentation is built with the command:

```bash
sphinx-build -b html docs/source docs/build/html
```
