# pyPalace 

pyPalace is a code suite used to generate [AWS Palace](https://awslabs.github.io/palace/stable/) (FEM electromagnetic simulations) config files with python. The main goal of this suite is to allow for a more intuitive, automated, and easy-to-use method of writing Palace config files without the need to actually write json files directly. 

AWS Palace please sponsor me (: 

## Table of Contents
- [Eigenmode Example](#eigenmode-example): Example of using pyPalace to generate an AWS Palace config file ready for simulation
- [Function definitions](#function-definitions): Definition of functions and useful links to AWS Palace's github for more context

Aspects of pyPalace that are in progress:
- documentation and exmaples for driven, transient, electrostatic, and magnetostatic.
- postprocessing in examples
- expand capabilities of certain features
- transient simulations

# Eigenmode Example

Here is an example using pyPalace to create an AWS Palace config file for an eigenmode simulation of a superconducting circuit consisting of a single coplanar resonator coupled to a feedline. 

The mesh file for this device has the following domain/block definitions:

| Name          | ID |
| --------------|---|
| substrate     | 1 |
| air           | 2 |
| resonator     | 3 |
| port1         | 4 |
| port2         | 5 |
| fair_field    | 6 |
| feedline      | 7 |
| ground_plane1 | 8 |
| ground_plane2 | 9 |

Now we can use pyPalace to build corresponding AWS Palace config file. The example that is discussed below can be found [here](eigenmode_example.py).

Start by importing the pyPalace functions:
```python
from pypalace import Config, Domains, Boundaries, Solver
```

Now let's create our Config object, which defines config["Problem"], and also create config["Model"]:
```python
my_sim = Config("Eigenmode",Output="eigenmode_output") # creates config["Problem"]
my_sim.add_Model("eigenmode_example.bdf") # creates config["Model"], no adaptive mesh refinement
```

Now we define our materials:
```python
# define materials
silicon = Domains.Material([1],1.0,11.45,0.0) # silicon 
air = Domains.Material([2],1.0,1.0,0.0) # air
my_materials = [silicon,air] # material list for input into add_Domains()
```

and our boundary conditions:
```python
# define boundary conditions
PECs = Boundaries.PEC([3,6,7,8,9]) # resonator, far field, feedline, ground plane(s)
Lumped1 = Boundaries.LumpedPort(Index=1,Attributes=[4],Direction="+X",R=50,L=0,C=0) # not necessary for eigenmode simulation
Lumped2 = Boundaries.LumpedPort(Index=2,Attributes=[5],Direction="-X",R=50,L=0,C=0)
my_BCs = [PECs,Lumped1,Lumped2] # boundary condition list for input into add_Boundaries()
```

now let's add config["Domains"] and config["Boundaries"] using our material and BC lists defined above. I will update this example with some postprocessing soon to help better showcase all aspects of 
```python
# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_sim.add_Domains(my_materials)
my_sim.add_Boundaries(my_BCs)
```

Define our eigenmode and linear algebra hyperparameters:
```python
eigenmode_params = Solver.Eigenmode(Target = 1.0,
                                    Tol = 1.0e-6,
                                    N = 5,
                                    Save = 5)

Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-6,
                              MaxIts = 10)
```

and add these to the config["Solver"] block:
```python
my_sim.add_Solver(Simulation=eigenmode_params,Order = 1,Linear=Linear_params)
```

We have defined everything we need so let's print out the config file to see what it looks like:
```python
my_sim.print_config()
```
```
{
  "Problem": {
    "Type": "Eigenmode",
    "Verbose": 2,
    "Output": "eigenmode_output"
  },
  "Model": {
    "Mesh": "example.bdf",
    "L0": 1e-06,
    "Lc": 0.0
  },
  "Domains": {
    "Materials": [
      {
        "Attributes": [
          1
        ],
        "Permeability": 1.0,
        "Permittivity": 11.45,
        "LossTan": 0.0
      },
      {
        "Attributes": [
          2
        ],
        "Permeability": 1.0,
        "Permittivity": 1.0,
        "LossTan": 0.0
      }
    ]
  },
  "Boundaries": {
    "PEC": {
      "Attributes": [
        3,
        6,
        7,
        8,
        9
      ]
    },
    "LumpedPort": [
      {
        "Index": 1,
        "Attributes": [
          4
        ],
        "Direction": "+X",
        "R": 50,
        "L": 0,
        "C": 0
      },
      {
        "Index": 2,
        "Attributes": [
          5
        ],
        "Direction": "-X",
        "R": 50,
        "L": 0,
        "C": 0
      }
    ]
  },
  "Solver": {
    "Order": 1,
    "Device": "CPU",
    "Eigenmode": {
      "N": 5,
      "Save": 5,
      "Type": "Default",
      "Target": 1.0,
      "Tol": 1e-06
    },
    "Linear": {
      "Type": "Default",
      "KSPType": "Default",
      "Tol": 1e-06,
      "MaxIts": 10
    }
  }
}
```

If it look's good, we are ready to save it! Note ```save_config()``` will also do a validity check and error out if it finds that you did not make a valid config file (e.g., you're missing an important block):
```python
my_sim.save_config("eigenmode_example.json")
```

The config file generated from this can be found [here](eigenmode_example.json).

# Function definitions

## pyPalace.builder

The builder classes (Domains, Boundaries, Solver) are used to define blocks that go into the config["Domains"],config["Boundaries"], and config["Solver"]

Definitions of function parameters come straight from [AWS Palace](https://awslabs.github.io/palace/stable/). So I won't go over specifics of parameters here in too much details. Some functions are still missing and/or incomplete (e.g., Lumped Port does not yet take Rs,Ls,Cs values). This is a work in progress.

Any parameters in the builder functions which have **None** as their default values will not be included in the config file and hence will revert to their default values set by Palace unless specificed expliticly in the function calls. See the example below.

### Domains

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Domains (see below).

```python
Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None) 
```
Defines the material properities to be assigned to volume blocks/domains from your mesh file. See [domains["Materials"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Materials%22])

* **Attributes** (list) - ID(s) of mesh domain(s) 
* **Permeability* (float) - Magnetic permeability
* **Permittivity** (float) - Dielectric permittivity
* **LossTan** (float,optional) - Loss tangent
* **Conductivity** (float,optional) - Electric conductivity
* **LondonDepth** (float,optional) - London penatration depth
* **MaterialAxes** (list,optional) - Axes directions for anisotropic materials

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

* **Index** (list) - Index to identify this domain in postprocessing output files
* **Center** (list) - Coordinates of probe in mesh units

### Boundaries

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Boundaries (see below).

```python
PEC(Attributes)
```
Defines which surface blocks/domains will have a perfect electric conductor boundary condition. See [boundaries["PEC"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22PEC%22])

* **Attributes** (list) - ID(s) of mesh domain(s) 

```python
PMC(Attributes)
```
Defines which surface blocks/domains will have a perfect magnetic conductor boundary condition. See [boundaries["PMC"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22PMC%22])

* **Attributes** (list) - ID(s) of mesh domain(s) 

```python
Absorbing(Attributes,Order):
```
Defines which surface blocks/domains will have an absorbing boundary condition. See [boundaries["Absorbing"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Absorbing%22])

* **Attributes** (list) - ID(s) of mesh domain(s) 
* **Order** (1 or 2) - first or second order approximation of far field absorbing boundary condition
        
```python
Conductivity(Attributes,Conductivity,Permeability,Thickness=None)
```
Defines which surface blocks/domains will have a conducting boundary condition. See [boundaries["Conductivity"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Conductivity%22])

* **Attributes** (list) - ID(s) of mesh domain(s)
* **Conductivity** (float,optional) - Electric conductivity
* **Permeability** (float) - Magnetic permeability
* **Thickness** (float,optional) - Conductor thickness in mesh units
           
```python
Ground(Attributes)
```
Defines which surface blocks/domains will have a grounded boundary condition. See [boundaries["Ground"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Ground%22])

* **Attributes** (list) - ID(s) of mesh domain(s) 

```python
LumpedPort(Index,Attributes,Direction,R,L,C)
```
Defines which surface blocks/domains will have a lumped port boundary condition. See [boundaries["LumpedPort"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22LumpedPort%22])

* **Index** (list) - Index for postprocessing
* **Attributes** (list) - ID(s) of mesh domain(s) 
* **Direction** (string or list) - ID(s) of mesh domain(s) 
* **R** (float) - Circuit resistance
* **L** (float) - Circuit inductance
* **C** (float) - Circuit capactiance

```python
Impedance(Attributes,Rs=None,Ls=None,Cs=None)
```
Defines which surface blocks/domains will have a impedance condition. See [boundaries["Impedance"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Impedance%22])

* **Attributes** (list) - ID(s) of mesh domain(s) 
* **R** (float) - Surface resistance
* **L** (float) - Surface inductance
* **C** (float) - Surface capactiance

```python
Postprocessing_Dielectric(Index,Attributes,Type,Thickness,Permittivity,LossTan):
```
Calculates interface dielectric loss at surfaces. See see [boundaries["Postprocessing"]["Dielectric"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Postprocessing%22][%22Dielectric%22]) 

* **Index** (list) - Index to identify this domain in postprocessing output files
* **Attributes** (list) - ID(s) of mesh domain(s)
* **Type** (string) - Type of dielectric interface for energy participation ratio (EPR) calculations
* **Thickness** (integer) - Thickness of dielectric interface in mesh units
* **Permittivity** (float) - Dielectric permittivity
* **LossTan** (float) - Loss tangent

### Solver

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Solver (see below).
```python
Eigenmode(Target=None,Tol=None,MaxIts=None,MaxSize=None,N=1,Save=1,Type="Default"):
```
Defines eigenmode hyperparameters. See [solver["Eigenmode"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Eigenmode%22])

* **Target** (float) - Frequency target above which to search for eigenmode frequency
* **Tol** (float) - Convergence tolerance for eigenmode solver
* **MaxIts** (integer) - Maximum number of iterations for eigenmode solver
* **MaxSize** (integer) - Maximum subspace size
* **N** (integer) - Number of eigenmodes to compute
* **Save** (integer) - Number of eigenmodes to save
* **Type** (string) - Eigenvalue solver type

```python
Linear(Type="Default",KSPType="Default",Tol=None,MaxIts=None,MaxSize=None):
```
Defines linear algebra hyperparameters. See [solver["Linear"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Linear%22])

* **Type** (string) - Solver type for preconditioning system of equations
* **KSPType** (string) - Krylov subspace solver type
* **Tol** (float) - Residual convergence tolerance
* **MaxIts** (integer) - Maximum number of iterations for linear solver
* **MaxSize** (integer) -  Maximum Krylov space size for the GMRES and FGMRES solvers

## pyPalace.Config

```python
pyPalace.Config(Type,Verbose=2,Output="sim_output")
```
Config obejct starts a new AWS Palace config file and will also specificy the config["Problem"] block in it. See [config["Problem"]](https://awslabs.github.io/palace/stable/config/problem/)

* **Type** (string) - Simulation type
* **Verbose** (integer) - Verbosity of output
* **Output** (string) - Name of out output file to save results to

```python
add_Model(Mesh,L0=1.0e-6,Lc=0.0,Tol=None,MaxIts=None,MaxSize=None,Nonconformal=None,UpdateFraction=None,UniformLevels=None,SaveAdaptMesh=None,SaveAdaptIterations=None)
```
Defines config["Model"]. See [config["Model"]](https://awslabs.github.io/palace/stable/config/model/).

* **Mesh** (string) - Mesh file name
* **L0** (float) - Units of mesh unit relative to 1 meter.
* **Lc** (float) - Characteristic length scale used for nondimensionalization, specified in mesh length units

The below options are for adapative mesh refinement, see [model["Refinement"]](https://awslabs.github.io/palace/stable/config/model/#model[%22Refinement%22]).

* **Tol** (float) - Convergence tolerance for adapative mesh refinement iterations
* **MaxIts** (integer) - Maximum number of adapative mesh refinement iterations
* **MaxSize** (integer) - Maximum degrees of freedom for adapative mesh refinement
* **Nonconformal** (boolean) - Choose if adaptive mesh refinement is nonconformal or not
* **UpdateFraction** (float) - Marking fraction used to choose which elements to refine
* **UniformLevels** (integer) - Levels of uniform parallel mesh refinement
* **SaveAdaptMesh** (boolean) - Choose to save refined mesh
* **SaveAdaptIterations** (boolean) - Choose to save results from each iteration of adapative mesh refinement

```python
add_Domains(Materials,Postprocessing = []):
```
adds domains["Materials"] and domains["Postprocessing"] to the palace config file as defined using pyPalace.builder.Domains.

* **Materials** (list) - List of materials to add to config file
* **Postprocessing** (list) - List of domain postprocessings to add to config file

```python
add_Boundaries(BCs,Postprocessing = []):
```
adds config["Boundaries"] and boundaries["Postprocessing"] to the palace config file as defined using pyPalace.builder.Boundaries.

* **Materials** (list) - List of boundary conditions to add to config file
* **Postprocessing** (list) - List of boundaries postprocessings to add to config file

```python
add_Solver(Simulation,Order=1,Device="CPU",Linear=None)
```
adds config["Solver"], solver["<simulation_type>"], and solver["Solver"]["Linear"]. 

* **Simulation** (ouput from ```pyPalace.builder.Solver.<sim_type>```) - Adds specified simulation hyperparameters
* **Order** (integer) - Order of simulation solver
* **Device** (string) - Device to run simulation on
* **Linear** (ouput from ```pyPalace.builder.Solver.Linear```) - Adds specified linear solver hyperparameters

```python
save_config(config_name,check_validity = True):
```
saves your AWS Palace config file.

* **config_name** (boolena) - Name of config file to save as
* **check_validity** (boolean) - Choose if you want to check your config file is valid

```python
print_config()
```
prints config file as a string so you can view it

