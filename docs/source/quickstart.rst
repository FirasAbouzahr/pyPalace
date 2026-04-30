Quickstart
==========

pyPalace workflows are script- or notebook-based. A typical workflow consists of:

1. Building a Palace configuration using pyPalace objects
2. Running the simulation locally, or on an HPC.
3. Extracting results and performing quantum analysis (e.g., LOM, EPR)

Minimal Electrostatic + LOM Workflow
-----------------------------------

A complete working example is provided here:

``Examples/example_02_electrostatics_LOM/example02_notebook_TransmonCross.ipynb``

This example demonstrates:

- building an electrostatic Palace configuration
- running a simulation locally
- extracting the capacitance matrix
- performing Lumped Oscillator Modeling (LOM) analysis

This workflow produces a capacitance matrix and corresponding LOM-derived qubit Hamiltonian parameters.

The required mesh file is included in the repository.

Before running the example, update:

- ``path_to_palace`` to your local Palace executable

To run the notebook:

.. code-block:: bash

    cd Examples/example_02_electrostatics_LOM
    jupyter notebook

Alternatively, run the script version:

.. code-block:: bash

    cd Examples/example_02_electrostatics_LOM
    python example_02_TransmonCross.py
