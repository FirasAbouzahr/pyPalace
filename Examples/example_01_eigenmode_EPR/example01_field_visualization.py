from pypalace import Config,Simulation,Tools
import numpy as np
from pypalace.analysis import EPR

''' paths '''
mesh_dir = "mesh/"
config_dir = "config/"

''' load previously made config file '''
meshfile = mesh_dir + "qubit_resonator_mesh.bdf"
my_config = Config.load_config(config_dir + "example01.json")
 
''' create simulation object to extract results from completeted simulation '''
cavity_qubit_sim = Simulation(my_config,None) # define simulation object, don't need to specify path for analysis only

''' Visualize the electric field magnitude to figure out the qubit & resonator modes '''

# qubit
cavity_qubit_sim.plot_field(field="E",index=1,save="Figures/qubit_mode.png") # plots magnitude of electric field

# resonator
cavity_qubit_sim.plot_field(field="E",index=2,save="Figures/resonator_mode.png") # plots magnitude of electric field
