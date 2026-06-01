### Example 02 (Electrostatic simulations & LOM analysis of pocket- & Xmon-style Transmon qubits)

Example 02 is split into three python notebooks.
* [build_and_mesh_transmons.ipynb](build_and_mesh_transmons.ipynb) builds the transmon qubit layouts with Quantum Metal and meshes the geometries with pyPalace (Gmsh backend). For a more thorough look at meshing with pyPalace, see [Example 00](https://github.com/FirasAbouzahr/pyPalace/tree/main/Examples/example_00_Quantum_Metal_to_pyPalace).
* [example02_notebook_pocketTransmon.ipynb](example02_notebook_pocketTransmon.ipynb) & [example02_notebook_TransmonCross.ipynb](example02_notebook_TransmonCross.ipynb) are step-by-step walkthroughs to:
    - Generate config object/file for electrostatic simulations to extract Maxwell capacitance matrices.
    - Run the corresponding simulations
    - Perform LOM analysis to extract the qubit Hamiltonian parameters + resonator-qubit system Hamiltonian parameters.
