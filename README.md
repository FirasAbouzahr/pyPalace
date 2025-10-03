# pyPalace 

AWS Palace please sponsor me (: 

## Table of Contents
- [Eigenmode Example](#eigenmode-example): Example of using pyPalace to generate an AWS Palace config file ready for simulation
- [Function definitions](#function-definitions): Definition of functions and useful links to AWS Palace's github for more context

# Eigenmod Example

Here is an example using pyPalace to create an AWS Palace config file for an eigenmode simulation of a superconducting circuit consisting of a single coplanar resonator coupled to a feedline. 

The end of the mesh file (.bdf) has the following block/domain definitions:

```
$ Name: substrate
$
PSOLID  1       100     0       
$
$ Name: air
$
PSOLID  2       100     0       
$
$ Name: resonator
$
PSHELL  3       100     1       
$
$ Name: port1
$
PSHELL  4       100     1       
$
$ Name: port2
$
PSHELL  5       100     1       
$
$ Name: far_field
$
PSHELL  6       100     1       
$
$ Name: feedline
$
PSHELL  7       100     1       
$
$ Name: ground_plane1
$
PSHELL  8       100     1       
$
$ Name: ground_plane2
$
PSHELL  9       100     1     
```

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

builder functions are used to define blocks that go into the 5 main components of a Palace configuration file: config["Problem"],config["Model"],config["Domains"],config["Boundaries"],config["Solver"]

Definitions of function parameters come straight from [AWS Palace](https://awslabs.github.io/palace/stable/). So I won't go over specifics of parameters here in too much details. Some functions are still missing and/or incomplete (e.g., Lumped Port does not yet take Rs,Ls,Cs values). This is a work in progress.

Any parameters in the builder functions which have **None** as their default values will not be included in the config file and hence will revert to their default values set by Palace unless specificed expliticly in the function calls. See the example below.

### pyPalace.builder.Domains

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Domains (see below).

#### Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None) 

Defines the material properities to be assigned to volume blocks/domains from your mesh file. See [domains["Materials"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Materials%22])

* *Attributes*: Array/list 
* *Permeability*: float 
* *Permittivity*: float 
* *LossTan*: float 
* *Conductivity*: float 
* *LondonDepth*: float 
* *MaterialAxes*: array/list 

#### Postprocessing_Energy(Index,Attributes):

Computes the electric and magnetic field energies in the specific domain attributes. See [domains["Postprocessing"]["Energy"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Postprocessing%22][%22Energy%22])

* *Index*: integer
* *Attributes*: Array/list 

#### Postprocessing_Probe(Index,Center):
Computes the electric and magnetic flux density. See [domains["Postprocessing"]["Probe"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Postprocessing%22][%22Probe%22])

* *Index*: integer
* *Center*: array/list

### pyPalace.builder.Boundaries

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Boundaries (see below).

#### PEC(Attributes)
Defines which surface blocks/domains will have a perfect electric conductor boundary condition. See [boundaries["PEC"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22PEC%22])

* *Attributes*: Array/list 

#### PMC(Attributes)
Defines which surface blocks/domains will have a perfect magnetic conductor boundary condition. See [boundaries["PMC"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22PMC%22])

* *Attributes*: Array/list

#### Absorbing(Attributes,Order):
Defines which surface blocks/domains will have an absorbing boundary condition. See [boundaries["Absorbing"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Absorbing%22])

* *Attributes*: Array/list
* *Order*: integer
        
#### Conductivity(Attributes,Conductivity,Permeability,Thickness=None)
Defines which surface blocks/domains will have a conducting boundary condition. See [boundaries["Conductivity"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Conductivity%22])

* *Attributes*: Array/list
* *Conductivity*: float
* *Permeability*: float
* *Thickness*: float
           
#### Ground(Attributes)
Defines which surface blocks/domains will have a grounded boundary condition. See [boundaries["Ground"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Ground%22])

* *Attributes*: Array/list

#### LumpedPort(Index,Attributes,Direction,R,L,C) 
Defines which surface blocks/domains will have a lumped port boundary condition. See [boundaries["LumpedPort"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22LumpedPort%22])

* *Index*: integer
* *Attributes*: Array/list
* *Direction*: string or array/list
* *R*: float
* *L*: float
* *C*: float

#### Impedance(Attributes,Rs=None,Ls=None,Cs=None):

Defines which surface blocks/domains will have a impedance condition. See [boundaries["Impedance"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Impedance%22])

* *Attributes*: Array/list
* *Rs*: float
* *Ls*: float
* *Cs*: float

#### Postprocessing_Dielectric(Index,Attributes,Type,Thickness,Permittivity,LossTan):

Calculates interface dielectric loss at surfaces. See see [boundaries["Postprocessing"]["Dielectric"]](https://awslabs.github.io/palace/stable/config/boundaries/#boundaries[%22Postprocessing%22][%22Dielectric%22]) 

* *Index*: integer
* *Attributes*: Array/list
* *Type*: string
* *Thickness*: float
* *Permittivity*: float
* *LossTan*: float

### pyPalace.builder.Solver

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Solver (see below).

#### Eigenmode(Target=None,Tol=None,MaxIts=None,MaxSize=None,N=1,Save=1,Type="Default"):

Defines eigenmode hyperparameters. See [solver["Eigenmode"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Eigenmode%22])

* *Target*: float
* *Tol*: float
* *MaxIts* integer
* *MaxSize* integer
* *N*: integer
* *Save* integer
* *Type*: string


#### Linear(Type="Default",KSPType="Default",Tol=None,MaxIts=None,MaxSize=None):

Defines linear algebra hyperparameters. See [solver["Linear"]](https://awslabs.github.io/palace/stable/config/solver/#solver[%22Linear%22])

* *Type*: string
* *KSPType*: string
* *Tol*: float
* *MaxIts*: integer
* *MaxSize*: integer

## pyPalace.Config(Type,Verbose=2,Output="sim_output")

Config obejct starts a new AWS Palace config file and will also specificy the config["Problem"] block in it. See [config["Problem"]](https://awslabs.github.io/palace/stable/config/problem/)

* *Type*: string
* *Verbose*: integer
* *Output*: string

#### add_Model(Mesh,L0=1.0e-6,Lc=0.0,Tol=None,MaxIts=None,MaxSize=None,Nonconformal=None,UpdateFraction=None,UniformLevels=None,SaveAdaptMesh=None,SaveAdaptIterations=None)

Defines config["Model"]. See [config["Model"]](https://awslabs.github.io/palace/stable/config/model/)

* *Mesh*: string
* *L0*: float
* *Lc*: float
* *Tol*: float
* *MaxIts*: integer
* *MaxSize* integer
* *Nonconformal*: boolean
* *UpdateFraction*: boolean
* *UniformLevels*: integer
* *SaveAdaptMesh*: boolean
* *SaveAdaptIterations*: boolean

#### add_Domains(Materials,Postprocessing = []):

adds domains["Materials"] and domains["Postprocessing"] to the palace config file as defined using pyPalace.builder.Domains.

* *Materials*: array/list
  - list of your materials definitions
* *Postprocessing*: array/list
  - list of your Domains postprocessing definitions

#### add_Boundaries(BCs,Postprocessing = []):

adds config["Boundaries"] and boundaries["Postprocessing"] to the palace config file as defined using pyPalace.builder.Boundaries.

* *BCs*: array/list 
  - list of your boundary condition definitions
* *Postprocessing*: array/list
  - list of your Boundaries postprocessing definitions

#### add_Solver(Simulation,Order=1,Device="CPU",Linear=None)

adds config["Solver"], solver["<simulation_type>"], and solver["Solver"]["Linear"]. 

* *Simulation*: ouput from pyPalace.builder.Solver.<sim_type>
* *Order*: integer
* *Device*: string
* *Linear*: ouput from pyPalace.builder.Solver.Linear

#### save_config(config_name,check_validity = True):

saves your AWS Palace config file.
* *Simulation*: string
  - name you want your config file to have
* *check_validity*: boolean
  - if True, checks to see if the config object and hence the file your are trying to save is valid.

#### print_config()

prints config file as a string so you can view it

