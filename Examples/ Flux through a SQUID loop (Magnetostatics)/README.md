## Magnetic flux through a transmon SQUID loop for frequency tunability studies

Here we demonstrate how to use pyPalace to generate an AWS Palace config file for magnetostatic simulations. Specifically, this is a study of the magnetic flux through tranmon qubit's SQUID loop in order to analyze it frequency tunability. 

The device in question is shown below, generated with [Qiskit Metal](https://qiskit-community.github.io/qiskit-metal/). The corresponding Qiskit Metal code to generate this device can be found [here](). The device consists of an "xmon" style transmon. At the bottom of its cross geoemetry is a 20 x 20 square micron quasi-SQUID loop (no real junctions). The loop is coupled to a flux bias line directly beneath it. 

<p align="center">
  <img src="Figures/qiskit_metal-tunable_xmon-image.png" width="600">
</p>

We use pyPalace to generate a config file for the corresponding meshed geometry of this device. Using Palace's SurfaceFlux postprocessing (config["Boundaries"]["PostProcessing"]["SurfaceFlux"]), the simulation will output information about flux through the SQUID loop. We then use [scQubits]() to further analyze the results and extract the frequency tunability of our qubit as well as its coherence information. 

**Table of Conents:**
* [CCreating a magnetostatic config file with pyPalace](#creating-a-magnetostatic-config-file-for-this-device-with-pyPalace)
* [Quantum Analysis with scQubits](#quantum-analysis-with-scqubits)

## Creating a magnetostatic config file for this device with pyPalace

The example outlined below can be found in [this python script](tunable_xmon_config_generator.py) or this [this notebook](tunable_xmon_config_generator.ipynb).

We start by importing the needed pyPalace libraries:

```python
from pypalace import Config, Model, Domains, Boundaries, Solver, Simulation
```
Before we begin defining our config file, let's take a look the mesh attributes.

```python
meshfile = "tunable_xmon.bdf"
Simulation.get_mesh_attributes(meshfile)
```

```python
my_config = Config("Magnetostatic",Output="magneto_output")
my_config.add_Model(meshfile,L0=1e-6) # no adaptive mesh refinement, already finely meshed 
```

This outputs the following pandas dataframe:

<img src="Figures/attributes_dataframe.png" width="300">

Now we define our materials and boundary conditions and add them to the config["Domains"] and config["Boundaries"] blocks. We add a surface current BC at the flux line port, this generates the magnetic flux through our SQUID loop.

```python
# define materials
silicon = Domains.Material([1],1.0,11.45,0.0) # silicon 
air = Domains.Material([2],1.0,1.0,0.0) # air
my_materials = [silicon,air] # material list for input into add_Domains()

# define boundary conditions
PECs = Boundaries.PEC([3,5,7,8]) # xmon cross, flux bias line, ground_plane, far_field
flux_port = Boundaries.SurfaceCurrent(Index=1,Attributes=[6],Direction="+X") # add surface current to the flux port to give flux line current 
my_BCs = [PECs,flux_port] # boundary condition list for input into add_Boundaries()
my_config.add_Boundaries(my_BCs)
```

We add SurfaceFlux postprocessing so that Palace returns the flux through the designated atrribute(s), in this case we are only interested in the SQUID loop, mesh attribute 4.

```python
# define materials
# add our "dummy" SQUID loop to SurfaceFlux postprocesssing so we can get magnetic flux through it
surfaceFlux_pp = Boundaries.Postprocessing_SurfaceFlux(Index=2,Attributes=[4],Type="Magnetic")
my_Boundaries_pp = [surfaceFlux_pp]
```

Adding Domains (materials) and Boundaries (BC and BC postprocessing) to config["Domains"] and config["Boundaries"], respectively:

```python
# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_config.add_Domains(my_materials)
my_config.add_Boundaries(my_BCs,Postprocessing=my_Boundaries_pp)
```
Finally, we define magnetostatic and linear solver parameters
```python
magneto_params = Solver.Magnetostatic(Save=5)

Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-6,
                              MaxIts = 100)
                              
my_config.add_Solver(Simulation=magneto_params,Order= 2,Linear=Linear_params)
```

Let's take a look at the config file:
```python
my_config.print_config()
```
```
{
  "Problem": {
    "Type": "Magnetostatic",
    "Verbose": 2,
    "Output": "magneto_output"
  },
  "Model": {
    "Mesh": "tunable_xmon.bdf",
    "L0": 1e-06
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
        5,
        7,
        8
      ]
    },
    "SurfaceCurrent": [
      {
        "Index": 1,
        "Attributes": [
          6
        ],
        "Direction": "+X"
      }
    ],
    "Postprocessing": {
      "SurfaceFlux": [
        {
          "Index": 2,
          "Attributes": [
            4
          ],
          "Type": "Magnetic"
        }
      ]
    }
  },
  "Solver": {
    "Order": 2,
    "Device": "CPU",
    "Magnetostatic": {
      "Save": 5
    },
    "Linear": {
      "Type": "Default",
      "KSPType": "Default",
      "Tol": 1e-06,
      "MaxIts": 100
    }
  }
}
```

Everything looks good, so we can save the config file:

Save the config file
```python
my_config.save_config("tunable_xmon.json")
```

## Quantum Analysis with scQubits

Once we run the simulation (took about 50 seconds to run with 50 MPI processes on an HPC) using the config file we generated above, we can analyze Palace's results using scQubits. Relevant to this analysis, we need the files ```surface-F.csv``` and ```terminal-I.csv``` from the Palace output. The code below can be found [here](scqubits_analysis.ipynb).

```python
import scqubits as scq
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
```

We read in the relevant Palace output files:

```python
## read in the flux data ##
phi_df = pd.read_csv("magneto_output/surface-F.csv",usecols = [1])
phi_df.columns = ["flux"]

## read in the current data ##
current_df = pd.read_csv("magneto_output/terminal-I.csv",usecols = [1])
current_df.columns = ["current"] 
```

Calculate flux per unit current in units of flux quantum and choose our qubit parameters:

```python
# divide the flux through our SQUID loop by the terminal current to get flux per unit current [weber / ampere]
dphi_dI = phi_df.flux.to_numpy() / current_df.current.to_numpy() 

## convert to units of flux quantum ## 
phi0 = 2.0678338484619295e-15 
norm_dphi_dI = abs(dphi_dI/phi0) # normalize

## current through flux line ###
current = np.linspace(0,20*10**(-3),25)

## SQUID loop parameters for scqubits ##
junction_asymmetry = .01
EJmax = 50
EC=.5
```

Finally, let's find the tunability of our qubit's frequency as a function of the flux bias line's input current:

```python
frequencies = []
for I in current:
    flux = I * norm_dphi_dI
    qubit = scq.TunableTransmon(EJmax=EJmax,
                                         EC=EC,
                                         d=junction_asymmetry,
                                         flux=flux,
                                         ng=0.0,
                                         ncut=30
                                        )
    frequencies.append(qubit.E01())
    
frequencies = np.array(frequencies)
deltaf = frequencies - frequencies.max()

fig,ax = plt.subplots()
plt.plot(current*1000,deltaf*10**3)

plt.xlabel("Flux Bias Line Current [mA]",fontsize = 14)
plt.ylabel(r"$\Delta f_q$ [MHz]",fontsize = 14)
plt.xticks(fontsize = 12)
plt.yticks(fontsize = 12)

plt.title("Change in Qubit Frequency vs Flux Bias Line Current")
plt.savefig("Figures/deltaf_vs_current.png")
```
This yields the following plot:

<p align="center">
  <img src="Figures/deltaf_vs_current.png" width="600">
</p>

With the given SQUID parameters, we get a frequency tunability range of about 6 MHz - not great but this could be optimized with a better design of the fluxline and fluxline-qubit coupling. 
