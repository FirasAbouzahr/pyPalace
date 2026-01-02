# pyPalace 

pyPalace is a python code suite used to streamline [AWS Palace](https://awslabs.github.io/palace/stable/) electromagnetic simulations for the design and modeling of circuit QED/superconducting quantum devices. The main functionality of pyPalace is to generate Palace config files using python. pyPalace is also a general purpose superconducting circuit design tool that provides functionality for quantum analysis of Palace results, conduct iterative design studies, and interface with HPCs. 

For comments, questions, or collaboration feel free to contact me at [firasabouzahr2030@u.northwestern.edu](mailto:firasabouzahr2030@u.northwestern.edu).

## Table of Contents
- [Installation](#installation)
- [Examples and Resources](#examples-and-resources)
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

All pyPalace Examples can be found [here](Examples). The current examples available are:

* [qubit-resonator eigenmode](Examples/qubit-resonator%20eigenmode/)
  - Config generation for eigenmode simulations of a resonator-qubit device.
  - EPR analysis with pyPalace.

* [resonator eigenmode](Examples/resonator%20eigenmode/)
  - Config generation for eigenmode simulations of a single resonator device.
 
* [iterative studies with pyPalace](Examples/iterative%20studies%20with%20pyPalace/)
  - How to use pyPalace for iterative qubit design studies.
  - HPC interfacing with pyPalace.
 
* [Flux through a SQUID loop (Magnetostatics)](Examples/Flux%20through%20a%20SQUID%20loop%20%28Magnetostatics%29/)
  - Config generation for magnetostatic simulation of a tunable transmon with a coupled flux bias line with pyPalace.
  - Quantum analysis with scQubits to extract frequency tunability from Palace results.
  
 * [Qubit Hamiltonian from Capacitance Matrix (Electrostatics)](Examples/Qubit%20Hamiltonian%20from%20Capacitance%20Matrix%20%28Electrostatics%29/)
  - Generate and execute electrostatic simulations of a pocket transmon and a xmon qubit with pyPalace.
  - Quantum analysis with scQubits to extract qubit Hamiltonian parameters from Palace results.
 
# Function definitions

pyPalace function definitions and relevant links to corresponding AWS Palace documentation can be found in [pypalace](pypalace). 
