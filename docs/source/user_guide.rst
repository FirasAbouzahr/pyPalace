.. _userguide:

User guide
==========

This page outlines a typical pyPalace workflow. Step-by-step notebooks and scripts live under
:ref:`jupyter-examples`.

If you are not modeling qubits, the configure → simulate steps below are still the main path;
qubit-oriented meshing and analysis steps are optional (see **Beyond qubit applications** on the
home page).


Workflow at a glance
--------------------

#. **Design & mesh** — Lay out the device (for example in Qiskit Metal) and produce a Palace-ready mesh (``.msh`` or ``.bdf``). Example 00 uses :meth:`~pypalace.Mesh.mesh_Quantum_Metal_design`; other tutorials ship pre-built meshes.
#. **Configure** — Build ``config["Problem"]``, ``Model``, ``Domains``, ``Boundaries``, and ``Solver`` with :mod:`pypalace.builder`, assemble them in a :class:`~pypalace.config.Config`, and save JSON.
#. **Simulate** — Point :class:`~pypalace.simulation.Simulation` at your Palace binary and call :meth:`~pypalace.simulation.Simulation.run` (local MPI or Slurm).
#. **Analyze** — Read CSV / field outputs; apply LOM, EPR, or custom postprocessing (see the example notebooks).


Building a Palace configuration
---------------------------------

Import the builder namespaces and create a config object:

.. code-block:: python

   from pypalace.builder import Model, Domains, Boundaries, Solver
   from pypalace.config import Config

   cfg = Config("my_simulation.json")
   cfg.add_Problem(Type="Eigenmode", Output="./output")
   cfg.add_Model(Mesh="device.msh", L0=1.0e-6)
   # ... add_Domains, add_Boundaries, add_Solver ...
   cfg.save_config()

Use :meth:`~pypalace.Mesh.get_mesh_attributes` to map mesh physical groups to materials and boundary conditions.

Palace field semantics are documented in the
`stable Palace configuration reference <https://awslabs.github.io/palace/stable/config/config/>`_.


Running Palace
--------------

.. code-block:: python

   from pypalace.simulation import Simulation

   palace = "/path/to/palace-x86_64.bin"
   sim = Simulation(cfg, palace)
   sim.run(n=8)  # local MPI ranks

For clusters, pass ``HPC_options`` from :meth:`~pypalace.simulation.Simulation.HPC_options` (partition, time limit, tasks per node, etc.). See the
`Examples README <https://github.com/FirasAbouzahr/pyPalace/blob/main/Examples/README.md>`_ for a Slurm template.


Mesh generation (Quantum Metal)
-------------------------------

For coplanar designs in Qiskit Metal, :meth:`~pypalace.Mesh.mesh_Quantum_Metal_design` writes a tagged Gmsh mesh and returns attribute metadata. Extra packages are required — see :ref:`install`.


Analysis workflows (qubit-focused examples)
-------------------------------------------

These tutorials are superconducting-qubit oriented; the Palace problem types are general:

* Capacitance + LOM — :ref:`ex02` (``Electrostatic``)
* Eigenmodes + EPR — :ref:`ex01` (``Eigenmode``)
* Driven :math:`S_{21}` — :ref:`ex03` (``Driven``)
* Quantum Metal mesh → sim — :ref:`ex00` (``Eigenmode``)

API details for config, simulation, and mesh modules are in :doc:`modules`.
