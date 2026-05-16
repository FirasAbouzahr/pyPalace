# pyPalace 

[![Docs](https://img.shields.io/badge/docs-live-blue)](https://firasabouzahr.github.io/pyPalace/)
[![PyPI version](https://img.shields.io/pypi/v/pypalace.svg)](https://pypi.org/project/pypalace/)

pyPalace is an open-source Python toolkit built around [AWS Palace](https://awslabs.github.io/palace/stable/) for the simulation and analysis of superconducting quantum devices. It enables users to build Palace configuration files, run simulations locally or on HPC systems, visualize computed electromagnetic fields, and extract simulation results through streamlined Python workflows.

For superconducting devices, pyPalace includes quantum analysis tools based on methods such as Lumped Oscillator Modeling (LOM) and Energy Participation Ratio (EPR), along with related techniques for extracting important physical parameters of superconducting circuits and qubits.

For questions, comments, or collaboration, contact:  
[firasabouzahr2030@u.northwestern.edu](mailto:firasabouzahr2030@u.northwestern.edu)

---
## Installation

> **Note:** pyPalace requires AWS Palace to be installed separately.

### For users

```bash
pip install pypalace
```

### For developers

Clone the repository:

```bash
git clone https://github.com/FirasAbouzahr/pyPalace.git
cd pyPalace
pip install -e .
```

---

## Examples

Examples can be found in the
[Examples directory](https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples).

* Example 00 (Introduction to pyPalace - **coming soon**)
* [Example 01](https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_01_eigenmode_EPR)
(eigenmode simulations & EPR analysis of a qubit-cavity system)
* [Example 02](https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_02_electrostatics_LOM)
(electrostatic simulations & LOM analysis of Transmon qubits)
* [Example 03](https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_03_fdomain_driven_resonator)
(driven simulation of a resonator & DCM fitting to S21)

---

## Developer Notes

Development wishlist: 
* Add built-in meshing capability to pyPalace (e.g., with Gmsh or other open-source mesh generation tools).
* Expanded testing and validation of less commonly used Palace features and boundary conditions.
* Expanded quantum analysis utilities.
* Additional advanced simulation and workflow examples for more complex device geometries and solver configurations.
* Improvements to usability, documentation clarity, workflow accessibility, and overall user experience.

---

## License
This project is licensed under the MIT License – see the [LICENSE](https://github.com/FirasAbouzahr/pyPalace/blob/main/LICENSE) file for details.
