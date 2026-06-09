.. _jupyter-examples:

Jupyter examples
==================

Worked tutorials are in the pyPalace repository:

`Examples/ on GitHub <https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples>`_

Clone the repo so notebook paths to ``mesh/``, ``config/``, and ``*_output/`` resolve:

.. code-block:: bash

   git clone https://github.com/FirasAbouzahr/pyPalace.git
   cd pyPalace

Each folder has a README with figures and run notes. Before simulating, set ``path_to_palace``
to your Palace binary, or use :func:`~pypalace.palace_env.get_palace_executable` when Palace is
on ``PATH`` (see :ref:`install`).

The notebooks are written for superconducting-qubit workflows, but the same pattern—config,
``Simulation.run``, then postprocess Palace output—applies to any Palace problem type you
configure.


Example index
-------------

Example 00 — Quantum Metal → pyPalace
-------------------------------------

.. _ex00:

`example_00_Quantum_Metal_to_pyPalace <https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_00_Quantum_Metal_to_pyPalace>`_

Mesh a coplanar Qiskit Metal design, build a config, run Palace, and analyze results.
Main file: ``example00_notebook.ipynb``. Requires ``qiskit-metal`` in addition to ``pypalace`` (:ref:`install`).


Example 01 — Eigenmode & EPR
----------------------------

.. _ex01:

`example_01_eigenmode_EPR <https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_01_eigenmode_EPR>`_

Cavity–qubit eigenmode simulation and EPR Hamiltonian extraction.
``example01_script.py`` (HPC), ``example01_analysis_notebook.ipynb``, ``example01_field_visualization.py``.
ParaView field dumps are not on GitHub; CSVs are provided for analysis-only runs.


Example 02 — Electrostatics & LOM
---------------------------------

.. _ex02:

`example_02_electrostatics_LOM <https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_02_electrostatics_LOM>`_

Capacitance matrices and LOM for transmon-style qubits.
``example02_notebook_TransmonCross.ipynb`` and ``example02_notebook_pocketTransmon.ipynb`` (plus script versions).


Example 03 — Driven resonator and S21
-------------------------------------

.. _ex03:

`example_03_fdomain_driven_resonator <https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_03_fdomain_driven_resonator>`_

Frequency-domain driven simulation and lineshape fitting.
``example03_script.py`` and ``example03_analysis_notebook.ipynb``; sample output under ``example03_output/``.


Running simulations
-------------------

After a :class:`~pypalace.config.Config` is saved, use :class:`~pypalace.simulation.Simulation`:

.. code-block:: python

   from pypalace.simulation import Simulation

   sim = Simulation(cfg, palace)
   sim.run(n=10)

Slurm options: :meth:`~pypalace.simulation.Simulation.HPC_options` and the
`Examples README <https://github.com/FirasAbouzahr/pyPalace/blob/main/Examples/README.md>`_.


Suggested order
---------------

#. Example 00 — meshing + end-to-end QM workflow
#. Example 02 — electrostatics & LOM (friendly notebooks)
#. Example 01 — eigenmodes & EPR
#. Example 03 — driven ports & :math:`S_{21}`
