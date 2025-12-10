This example creates an AWS Palace config file for an eigenmode simulation of a superconducting circuit consisting of a single qubit-resonator subsystem (with a truncated feedline). 

Below are images of the device, its corresponding mesh, and the qubit mode from the eigenmode simulation visualized in ParaView.

<img src="Figures/qubit_res.png" width="900">

## Creating an eigenmode config file for this device with pyPalace

The example outlined below can be found in [this python script](resonator_eigenmode_example.py) or this [this notebook](resonator_eigenmode_example.ipynb).

We start by importing the needed pyPalace libraries:

```python
from pypalace import Simulation, Config, Model, Domains, Boundaries, Solver
```

First let's create the config object (automatically creates config["Problem"] and also define config["Model"].

```python
meshfile = "qubit_resonator_mesh.bdf"
my_sim = Config("Eigenmode",Output="eigenmode_output") # config["Problem"]
 
# define adaptive mesh refinement, the qubit is coarsely meshed to save on file size so we use AMR to boost simulation accuracy
my_refinement = Model.Refinement(Tol = 1e-6,MaxIts = 4)

# define config["Model"] block
my_sim.add_Model(meshfile,L0=1e-6,Refinement=my_refinement)
```

Before we start assigning material properties and boundary conditions, let's take look at the attributes in the mesh file: 

```python
my_attributes = Simulation.get_mesh_attributes(meshfile)
my_attributes
```

This outputs the following pandas dataframe:

<img src="Figures/attributes_dataframe.png" width="300">

So we have the following attributes:
**Volumes**
* we'll define substrate (1) as sapphire
* and we'll define air as a vacuum

**Surfaces**
* feedline (3), resonator (4), and qubit (5), and ground plane are the superconducting components which we will define as PEC
* JJ is the Josephson junction, we will define this as a lumped port with inductance $L_J$ = 10.4 nH
* far field is the geometry closing boundary, we also define this as PEC, some folk define it as an absorbing boundary condition instead.


Now we define our materials and boundary conditions and add them to the config["Domains"] and config["Boundaries"] blocks.
```python
# define materials
sapphire = Domains.Material(Attributes = [1],Permeability=1.0,Permittivity=[9.3,9.3,11.4],MaterialAxes=[[1,0,0],[0,1,0],[0,0,1]],LossTan=8.6e-5)
air = Domains.Material([2],1.0,1.0,0.0)
my_materials = [sapphire,air] # material list for input into add_Domains()

# define boundary conditions
PECs = Boundaries.PEC([3,4,5,7,8]) # 
JJ = Boundaries.LumpedPort(Index=1,Attributes=[6],Direction="+X",R=0,L=round(10.4*10**(-9),9),C=0) 
my_BCs = [PECs,JJ] # boundary condition list for input into add_Boundaries()

# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_sim.add_Domains(my_materials)
my_sim.add_Boundaries(my_BCs)
```

Define eigenmode and linear solver parameters
```python
## eigenmode parameters
eigenmode_params = Solver.Eigenmode(Target = 3.0,
                                    Tol = 1.0e-8,
                                    N = 6,
                                    Save = 6)
## linear solver parameters
Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-8,
                              MaxIts = 50)

## add them to config["Solver"] and solver["Linear"]
my_sim.add_Solver(Simulation=eigenmode_params,Order = 2,Linear=Linear_params)
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
    "Mesh": "qubit_resonator_mesh.bdf",
    "L0": 1e-06,
    "Refinement": {
      "Tol": 1e-06,
      "MaxIts": 4
    }
  },
  "Domains": {
    "Materials": [
      {
        "Attributes": [
          1
        ],
        "Permeability": 1.0,
        "Permittivity": [
          9.3,
          9.3,
          11.4
        ],
        "LossTan": 8.6e-05,
        "MaterialAxes": [
          [
            1,
            0,
            0
          ],
          [
            0,
            1,
            0
          ],
          [
            0,
            0,
            1
          ]
        ]
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
        4,
        5,
        7,
        8
      ]
    },
    "LumpedPort": [
      {
        "Index": 1,
        "Attributes": [
          6
        ],
        "Direction": "+X",
        "R": 0,
        "L": 1e-08,
        "C": 0
      }
    ]
  },
  "Solver": {
    "Order": 2,
    "Device": "CPU",
    "Eigenmode": {
      "N": 6,
      "Save": 6,
      "Type": "Default",
      "Target": 3.0,
      "Tol": 1e-08
    },
    "Linear": {
      "Type": "Default",
      "KSPType": "Default",
      "Tol": 1e-08,
      "MaxIts": 50
    }
  }
}
```
The MaterialAxes definition for sapphire gets a bit ugly in the config file... working to beautify it (:

Save the config file
```python
my_sim.save_config("qubit_res.json",check_validity=True) # checks validity of file and raises error if something is missing
```

## EPR analysis

coming soon! we are adding new functions to pyPalace to calculate Hamiltonian parameters with EPR analysis.
