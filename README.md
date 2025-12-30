# pyPalace 

pyPalace is a python code suite used to streamline [AWS Palace](https://awslabs.github.io/palace/stable/) electromagnetic simulations for the design and modeling of circuit QED/superconducting quantum devices. The main functionality of pyPalace is to generate Palace config files using python. pyPalace is also a general purpose superconducting circuit design tool that provides functionality to extract Hamiltonian/device parameters from Palace simulation results, conduct iterative design studies, and interface with HPCs. 

For comments, questions, or collaboration please feel free to contact me at [firasabouzahr2030@u.northwestern.edu](mailto:firasabouzahr2030@u.northwestern.edu).

## Table of Contents
- [Installation](#installation)
- [Examples and Resources ](#examples-and-resources)
- [Function definitions](#function-definitions)

# Installation

Currently the only option is to install from source.

Open a terminal and navigate to the directory where you want the project:

```
cd <your_directory>
git clone https://github.com/FirasAbouzahr/pyPalace.git
cd pyPalace
```

Install the package locally using pip:

```
pip install -e .
```

# Examples and Resources 

Examples of how to use pyPalace can be found [here](Examples).

Aspects of pyPalace that are still being developed:
- Documentation and examples for driven, transient, electrostatic, and magnetostatic.
- Postprocessing in examples.
- Expand capabilities of certain features.
- Transient simulations.

# Function definitions

pyPalace function definitions and relevant links to corresponding AWS Palace documentation can be found in [pypalace](pypalace). 
