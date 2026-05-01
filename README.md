# pyPalace 

[![Docs](https://img.shields.io/badge/docs-live-blue)](https://firasabouzahr.github.io/pyPalace/)

pyPalace is a Python toolkit for streamlining [AWS Palace](https://awslabs.github.io/palace/stable/) electromagnetic simulations for the design and modeling of superconducting quantum devices.

At the top-level, pyPalace is a wrapper around AWS Palace. It enables users to:
- build Palace configuration files,
- run simulations (locally or on HPC systems),
- and extract results cleanly using Python.

For superconducting devices, pyPalace includes quantum analysis tools such as Lumped Oscillator Modeling (LOM), Energy Participation Ratio (EPR) methods, and other techniques to extract important design parameters.

For questions, comments, or collaboration, contact:  
[firasabouzahr2030@u.northwestern.edu](mailto:firasabouzahr2030@u.northwestern.edu)

---

## Installation

> **Note:** pyPalace requires AWS Palace to be installed separately.

Clone the repository:

    cd <your_directory>
    git clone https://github.com/FirasAbouzahr/pyPalace.git
    cd pyPalace

Install locally:

    pip install -e .

---

## Examples 

Examples can be found in the [examples](Examples) directory. More detailed documentation coming soon.

---

## License
This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
