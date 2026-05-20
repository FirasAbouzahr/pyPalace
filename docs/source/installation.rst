.. _install:

Install
=======

Prerequisites
-------------

pyPalace is a Python layer on top of `AWS Palace <https://awslabs.github.io/palace/stable/>`_.
You need a working Palace installation (and typically MPI) before you can run simulations.
See the `Palace installation guide <https://awslabs.github.io/palace/stable/install/install/>`_
for building or obtaining ``palace``.

For simulation physics, solvers, boundaries, and mesh requirements, use the
`Palace documentation <https://awslabs.github.io/palace/stable/>`_ as the reference.
pyPalace's :mod:`pypalace.builder` helpers and :class:`~pypalace.config.Config` are intended to
mirror Palace's JSON structure one-to-one: the Python API assembles the same ``Problem``,
``Model``, ``Domains``, ``Boundaries``, and ``Solver`` blocks documented under
`config["..."] <https://awslabs.github.io/palace/stable/config/config/>`_.

Python **3.9+** is required.


Installing via pip
------------------

.. code-block:: bash

   pip install pypalace

To upgrade:

.. code-block:: bash

   pip install pypalace -U


Installing from source
----------------------

.. code-block:: bash

   git clone https://github.com/FirasAbouzahr/pyPalace.git
   cd pyPalace
   pip install -e .


Optional packages for examples
------------------------------

Notebooks and plotting use dependencies already required by ``pypalace``. Install Jupyter to run tutorials:

.. code-block:: bash

   pip install jupyter


Point pyPalace at Palace
------------------------

When you run a simulation, pass the path to your Palace binary:

.. code-block:: python

   palace = "/path/to/palace_install/bin/palace-x86_64.bin"
   my_sim = Simulation(config_object, palace)


Meshes and design workflows
---------------------------

Palace (and therefore pyPalace) accepts a wide range of
`mesh file formats <https://awslabs.github.io/palace/stable/guide/model/#Supported-mesh-formats>`_
for structured and unstructured grids. You can use any design and meshing toolchain that
produces a Palace-compatible file—Cubit, Gmsh, COMSOL export, and others—then point
``config["Model"]["Mesh"]`` at that path via :meth:`~pypalace.config.Config.add_Model`.

pyPalace does not require a single mesh source. Example 00 shows one optional path:
meshing a coplanar layout from `Quantum Metal <https://qiskit-community.github.io/qiskit-metal/>`_
(formerly Qiskit Metal) with :meth:`~pypalace.mesh.mesh.mesh_Quantum_Metal_design`. That path
needs extra packages:

.. code-block:: bash

   pip install gmsh shapely qiskit-metal

Other tutorials ship pre-built ``.bdf`` or ``.msh`` meshes. To list physical groups when
writing configs, use :meth:`~pypalace.mesh.mesh.get_mesh_attributes`.


High-performance computing
--------------------------

Several examples use Slurm via :meth:`~pypalace.simulation.Simulation.run` and ``HPC_options``.
Adjust partition, account, and resource directives for your site — see :ref:`jupyter-examples`.
