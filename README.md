# pyPalace 

pyPalace is a code suite used to generate [AWS Palace](https://awslabs.github.io/palace/stable/) (FEM electromagnetic simulations) config files with python. The main goal of this suite is to allow for a more intuitive, automated, and easy-to-use method of writing Palace config files for superconducting quantum circuit simulations (or other devices!).

AWS Palace please sponsor me (: 

## Table of Contents
- [Installation](#installation)
- [Examples and Resources ](#examples-and-resources ): Example of using pyPalace to generate an AWS Palace config file ready for simulation
- [Function definitions](#function-definitions): Definition of functions and useful links to AWS Palace's github for more context

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

All that's left to do now is have fun (:

# Examples and Resources 

Examples of how to use pyPalace to generate AWS Palace config files can be found [here](Examples). 

Aspects of pyPalace that are still being developed:
- Documentation and examples for driven, transient, electrostatic, and magnetostatic.
- Postprocessing in examples.
- Expand capabilities of certain features.
- Transient simulations.

We also hope to expand the scope of pyPalace to be a general purpose superconducting qubit design tool in the future:
- Automated simulating on HPCs using Slurm. 
- Materials library with data from simulations and experiments.
- Benchmakring library to help inform your own simulations' compute requirements.
- circuit QED calculations (e.g., Hamiltonian parameters) from simulation results.

And more!

# Function definitions

Definitions of function parameters come straight from [AWS Palace](https://awslabs.github.io/palace/stable/). So I won't go over specifics of parameters here in too much details. Some functions are still missing and/or incomplete (e.g., Lumped Port does not yet take Rs,Ls,Cs values). This is a work in progress.

Any parameters in the following function definitions which have **None** as their default values will not be included in the config file and hence will revert to their default values set by Palace unless specificed expliticly in the function calls.

## pyPalace.Model
All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Model or in other functions within pyPalace.Model.

```python
Refinement(Tol=None,MaxIts=None,MaxSize=None,Nonconformal=None,UpdateFraction=None,UniformLevels=None,Boxes=None,Spheres=None,SaveAdaptMesh=None,SaveAdaptIterations=None)
```

Used to define adapative mesh refinement. See [model["Refinement"]](https://awslabs.github.io/palace/stable/config/model/#model[%22Refinement%22]).

* **Tol** (float) - Convergence tolerance for adapative mesh refinement iterations.
* **MaxIts** (integer) - Maximum number of adapative mesh refinement iterations.
* **MaxSize** (integer) - Maximum degrees of freedom for adapative mesh refinement.
* **Nonconformal** (boolean) - Choose if adaptive mesh refinement is nonconformal or not.
* **UpdateFraction** (float) - Marking fraction used to choose which elements to refine.
* **UniformLevels** (integer) - Levels of uniform parallel mesh refinement.
* **Boxes** (ouput from ```pyPalace.Model.Refinement_Boxes```) - Box region for mesh refinement.
* **Spheres** (ouput from ```pyPalace.Model.Refinement_Spheres```) - Sphere region for mesh refinement.
* **SaveAdaptMesh** (boolean) - Choose to save refined mesh.
* **SaveAdaptIterations** (boolean) - Choose to save results from each iteration of adapative mesh refinement.

```python
Refinement_Boxes(Levels,BoundingBoxMin,BoundingBoxMax)
```
Defines box region for focused adapative mesh refinement. Used as an input for pyPalace.Model.Refinement(...,Boxes,...)

* **Levels** (integer) - Level of parallel mesh refinement inside box region.
* **BoundingBoxMin** (list) - Minimum coordinates of refinement box region, specificed in mesh units.
* **BoundingBoxMax** (list) - Maximum coordinates of refinement box region, specificed in mesh units.

```python
Refinement_Spheres(Levels,Center,Radius)
```
Defines sphere region for focused adapative mesh refinement. Used as an input for pyPalace.Model.Refinement(...,Spheres,...)

* **Levels** (integer) - Level of parallel mesh refinement inside box region.
* **Center** (float) - Center of refinement sphere region, specificed in mesh units.
* **Radius** (float) - Radius of refinement sphere region, specificed in mesh units.

## pyPalace.Domains

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Domains.

```python
Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None) 
```
Defines the material properities to be assigned to volume blocks/domains from your mesh file. See [domains["Materials"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Materials%22])

* **Attributes** (list) - ID(s) of mesh domain(s).
* **Permeability** (float) - Magnetic permeability.
* **Permittivity** (float) - Dielectric permittivity.
* **LossTan** (float,optional) - Loss tangent.
* **Conductivity** (float,optional) - Electric conductivity.
* **LondonDepth** (float,optional) - London penatration depth.
* **MaterialAxes** (list,optional) - Axes directions for anisotropic materials.

```python
Postprocessing_Energy(Index,Attributes):
```
Computes the electric and magnetic field energies in the specific domain attributes. See [domains["Postprocessing"]["Energy"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Postprocessing%22][%22Energy%22])

* **Index** (list) - Index to identify this domain in postprocessing output files
* **Attributes** (list) - ID(s) of mesh domain(s) 

```python
Postprocessing_Probe(Index,Center):
```
Computes the electric and magnetic flux density. See [domains["Postprocessing"]["Probe"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Postprocessing%22][%22Probe%22])

* **Index** (list) - Index to identify this domain in postprocessing output files.
* **Center** (list) - Coordinates of probe in mesh units.

## pyPalace.Boundaries

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Boundaries (see below).

```python
PEC(Attributes)
```
Defines which surface blocks/domains will have a perfect electric conductor boundary condition. See [boundaries["PEC"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22PEC%22])

* **Attributes** (list) - ID(s) of mesh domain(s).

```python
PMC(Attributes)
```
Defines which surface blocks/domains will have a perfect magnetic conductor boundary condition. See [boundaries["PMC"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22PMC%22])

* **Attributes** (list) - ID(s) of mesh domain(s).

```python
Absorbing(Attributes,Order):
```
Defines which surface blocks/domains will have an absorbing boundary condition. See [boundaries["Absorbing"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Absorbing%22])

* **Attributes** (list) - ID(s) of mesh domain(s).
* **Order** (1 or 2) - first or second order approximation of far field absorbing boundary condition.
        
```python
Conductivity(Attributes,Conductivity,Permeability,Thickness=None)
```
Defines which surface blocks/domains will have a conducting boundary condition. See [boundaries["Conductivity"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Conductivity%22])

* **Attributes** (list) - ID(s) of mesh domain(s).
* **Conductivity** (float,optional) - Electric conductivity.
* **Permeability** (float) - Magnetic permeability.
* **Thickness** (float,optional) - Conductor thickness in mesh units.
           
```python
Ground(Attributes)
```
Defines which surface blocks/domains will have a grounded boundary condition. See [boundaries["Ground"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Ground%22])

* **Attributes** (list) - ID(s) of mesh domain(s). 

```python
LumpedPort(Index,Attributes,Direction=None,CoordinateSystem=None,Excitation=None,Active=None,R=None,L=None,C=None,Rs=None,Ls=None,Cs=None,Elements=None)
```
Defines which surface blocks/domains will have a lumped port boundary condition. See [boundaries["LumpedPort"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22LumpedPort%22])

* **Index** (list) - Index for postprocessing.
* **Attributes** (list) - ID(s) of mesh domain(s).
* **Direction** (string or list) - ID(s) of mesh domain(s).
* **CoordinateSystem** (string) - Coordinate system used to define direction.
* **Excitation** (boolean) - Turns on or off port excitation. 
* **Active** (boolean) - Turns on or off damping boundary condition.
* **R** (float) - Circuit resistance.
* **L** (float) - Circuit inductance.
* **C** (float) - Circuit capactiance.
* **Rs** (float) - Surface resistance.
* **Ls** (float) - Surface inductance.
* **Cs** (float) - Surface capactiance.
* **Elements** (output from pyPalace.Boundaries.LumpedPort_Elements --- yet to be defined, don't try for now) - Used to define multielement lumped ports.

```python
Impedance(Attributes,Rs=None,Ls=None,Cs=None)
```
Defines which surface blocks/domains will have a impedance condition. See [boundaries["Impedance"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Impedance%22])

* **Attributes** (list) - ID(s) of mesh domain(s).
* **R** (float) - Surface resistance.
* **L** (float) - Surface inductance.
* **C** (float) - Surface capactiance.

```python
Postprocessing_Dielectric(Index,Attributes,Type,Thickness,Permittivity,LossTan):
```
Calculates interface dielectric loss at surfaces. See see [boundaries["Postprocessing"]["Dielectric"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Postprocessing%22][%22Dielectric%22]) 

* **Index** (list) - Index to identify this domain in postprocessing output files.
* **Attributes** (list) - ID(s) of mesh domain(s).
* **Type** (string) - Type of dielectric interface for energy participation ratio (EPR) calculations.
* **Thickness** (integer) - Thickness of dielectric interface in mesh units.
* **Permittivity** (float) - Dielectric permittivity.
* **LossTan** (float) - Loss tangent.

## pyPalace.Solver

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Solver (see below).

```python
Electrostatic(N):
```
Defines electrostatic simulation options. See [solver["Electrostatic"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Electrostatic%22])

* **N** (integer) - Number of computed electric field solutions to save for visualization.

```python
Magnetostatic(N):
```
Defines magnetostatic simulation options. See [solver["Magnetostatic"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Magnetostatic%22])

* **N** (integer) - Number of computed magnetic field solutions to save for visualization.

```python
Eigenmode(Target,Tol=None,MaxIts=None,MaxSize=None,N=1,Save=1,Type="Default"):
```
Defines eigenmode simulation options. See [solver["Eigenmode"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Eigenmode%22])

* **Target** (float) - Frequency target above which to search for eigenmode frequency.
* **Tol** (float) - Convergence tolerance for eigenmode solver.
* **MaxIts** (integer) - Maximum number of iterations for eigenmode solver.
* **MaxSize** (integer) - Maximum subspace size.
* **N** (integer) - Number of eigenmodes to compute.
* **Save** (integer) - Number of eigenmodes to save.
* **Type** (string) - Eigenvalue solver type.

```python
Driven(MinFreq=None,MaxFreq=None,FreqStep=None,SaveStep=None,Samples=None,Save=None,Restart=None,AdaptiveTol=None,AdaptiveMaxSamples=None,AdaptiveConvergenceMemory=None)
```
Defines Driven simulation options. See [solver["Driven"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Driven%22])

* **MinFreq** (float) - Lower bound of frequency sweep.
* **MaxFreq** (float) - Upper bound of frequency sweep.
* **FreqStep** (float) - Step size of frequency sweep.
* **SaveStep** (integer) - Sets how often to save the computed fields for visualization, specified in number of frequency steps.
* **Samples** (output from pyPalace.Solver.Driven_Samples --- not yet defined, don't try for now') - Specifies additional frequency sweep options.
* **Save** (list) - Sets which frequencies from sweep to save the computed fields for visualization.
* **Restart** (integer) - Iteration from which to restart for partial frequency sweep.
* **AdaptiveTol** (float) - Error tolerance for adaptive frequency sweep.
* **AdaptiveMaxSamples** (integer) - Maximum number of frequency samples used in adaptive frequency sweep.
* **AdaptiveConvergenceMemory** (integer) - Memory used for assessing convergence of the adaptive frequency sweep.


```python
Linear(Type="Default",KSPType="Default",Tol=None,MaxIts=None,MaxSize=None):
```
Defines linear algebra hyperparameters. See [solver["Linear"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Linear%22])

* **Type** (string) - Solver type for preconditioning system of equations.
* **KSPType** (string) - Krylov subspace solver type.
* **Tol** (float) - Residual convergence tolerance.
* **MaxIts** (integer) - Maximum number of iterations for linear solver.
* **MaxSize** (integer) -  Maximum Krylov space size for the GMRES and FGMRES solvers.

## pyPalace.Config

```python
pyPalace.Config(Type,Verbose=2,Output="sim_output")
```
Config obejct starts a new AWS Palace config file and will also specificy the config["Problem"] block in it. See [config["Problem"]](https://awslabs.github.io/palace/stable/config/problem/)

* **Type** (string) - Simulation type.
* **Verbose** (integer) - Verbosity of output.
* **Output** (string) - Name of out output file to save results to.

```python
add_Model(Mesh,L0=1.0e-6,Lc=None,Refinement=None)
```
Defines config["Model"]. See [config["Model"]](https://awslabs.github.io/palace/stable/config/model/).

* **Mesh** (string) - Mesh file name.
* **L0** (float) - Units of mesh unit relative to 1 meter.
* **Lc** (float) - Characteristic length scale used for nondimensionalization, specified in mesh length units.
* **Refinement** (output from pyPalace.Model.Refinement) - Used to define adaptive mesh refinement.

```python
add_Domains(Materials,Postprocessing = []):
```
adds domains["Materials"] and domains["Postprocessing"] to the palace config file as defined using pyPalace.Domains.

* **Materials** (list) - List of materials to add to config file.
* **Postprocessing** (list) - List of domain postprocessings to add to config file.

```python
add_Boundaries(BCs,Postprocessing = []):
```
adds config["Boundaries"] and boundaries["Postprocessing"] to the palace config file as defined using pyPalace.Boundaries.

* **Materials** (list) - List of boundary conditions to add to config file.
* **Postprocessing** (list) - List of boundaries postprocessings to add to config file.

```python
add_Solver(Simulation,Order=1,Device="CPU",Linear=None)
```
adds config["Solver"], solver["<simulation_type>"], and solver["Solver"]["Linear"]. 

* **Simulation** (ouput from ```pyPalace.Solver.<sim_type>```) - Adds specified simulation hyperparameters.
* **Order** (integer) - Order of simulation solver.
* **Device** (string) - Device to run simulation on.
* **Linear** (ouput from ```pyPalace.Solver.Linear```) - Adds specified linear solver hyperparameters.

```python
save_config(config_name,check_validity = True):
```
saves your AWS Palace config file.

* **config_name** (boolena) - Name of config file to save as.
* **check_validity** (boolean) - Choose if you want to check your config file is valid.

```python
print_config()
```
prints config file as a string so you can view it.

