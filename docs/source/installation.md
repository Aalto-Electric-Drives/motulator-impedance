# Installation

The package requires Python 3.12 or newer. The installation of *motulator* and its dependencies is described in the [documentation of *motulator*](https://aalto-electric-drives.github.io/motulator/installation.html); *motulator* is installed automatically as a dependency of this package. The package supports *motulator* 0.15 and 0.16, and the support is extended after each new release of *motulator* has been tested.

## Option 1: Use pip

Install the package with `pip` in a [virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/), which keeps the package and its dependencies separate from other Python projects. Some Linux distributions, such as Debian, do not allow installing packages into the system Python with `pip` at all. Create and activate the environment in your project folder. On Linux and macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bat
py -m venv .venv
.venv\Scripts\activate
```

Then, install the package:

```bash
pip install motulator-impedance
```

The environment must be activated again in each new terminal.

## Option 2: Clone the Repository

For developers and advanced users, cloning the repository is recommended. The following instructions are for [VS Code](https://code.visualstudio.com):

1. Install VS Code, Python, and `git` on your computer. Install also the recommended extensions in VS Code.

1. Clone the project using the command:

   ```bash
   git clone https://github.com/Aalto-Electric-Drives/motulator-impedance
   ```

1. Launch VS Code from the cloned project's root directory.

1. [Create a virtual environment](https://code.visualstudio.com/docs/python/environments) in the workspace.

1. Install the package with its optional dependencies in the VS Code terminal, after the virtual environment is created and activated:

   ```bash
   pip install -e .[dev,doc]
   ```

   The `dev` dependencies are needed for the tests and the code checks and the `doc` dependencies for building this documentation.

1. Now you can run the example scripts in the `examples/` folder.

The tests are run with `pytest` and the documentation is built with the command:

```bash
sphinx-build -b html docs/source docs/build/html
```
