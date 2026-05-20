pyPalace documentation
======================

pyPalace is an open-source Python toolkit for simulating and analyzing superconducting
quantum devices with `AWS Palace <https://awslabs.github.io/palace/stable/>`_.

It helps you build Palace JSON configurations, generate meshes (including from Qiskit Metal
designs), run simulations locally or on HPC, visualize fields, and apply analysis workflows
such as Lumped Oscillator Modeling (LOM) and Energy Participation Ratio (EPR).

The core library is not limited to qubits; see **Beyond qubit applications** below.


Getting started
***************

After :ref:`install` of pyPalace, read the :ref:`userguide` for the usual workflow, then
work through the :ref:`jupyter-examples` in the GitHub repository (notebooks and scripts under
``Examples/``).

Palace itself must be installed separately; see the
`Palace installation guide <https://awslabs.github.io/palace/stable/install/install/>`_.


Overview
********

pyPalace wraps common Palace setup tasks in Python:

* **Configuration** — :mod:`pypalace.builder` helpers and :class:`~pypalace.config.Config` to assemble and save JSON input files.
* **Meshing** — :class:`~pypalace.Mesh` (or ``from pypalace import mesh``) for Gmsh export from coplanar Qiskit Metal layouts and for reading mesh attribute tables.
* **Simulation** — :class:`~pypalace.simulation.Simulation` to launch Palace locally or via Slurm.
* **Analysis** — utilities in the examples and :mod:`pypalace.analysis` for extracting Hamiltonian parameters from EM results.

Numerics rely on NumPy, SciPy, and Pandas; plotting uses Matplotlib and PyVista where examples need it.


Beyond qubit applications
~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

   **Not working on qubits?** The Palace-facing parts of pyPalace—:mod:`pypalace.builder`,
   :class:`~pypalace.config.Config`, and :class:`~pypalace.simulation.Simulation`—are a
   direct, problem-agnostic wrapper around AWS Palace. You can use them for any
   electromagnetic setup Palace supports (resonators, filters, packaging, antennas, etc.).

   Much of the documentation and the ``Examples/`` notebooks highlight superconducting qubits
   (LOM, EPR, Qiskit Metal meshing). Treat those as optional: use the config and simulation
   workflow you need, and ignore the qubit-specific analysis unless it applies to your project.


Contact
*******

Questions or collaboration: `firasabouzahr2030@u.northwestern.edu <mailto:firasabouzahr2030@u.northwestern.edu>`_.

Source and issues: `GitHub <https://github.com/FirasAbouzahr/pyPalace>`_.


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: GETTING STARTED

   installation
   user_guide


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: EXAMPLES

   examples


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: API REFERENCE

   modules
