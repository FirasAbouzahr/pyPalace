from pypalace import Config,Simulation,Tools
import numpy as np
from pypalace.analysis import EPR

# check modes using Paraview
qubit_mode = 1
resonator_mode = 2
JJ_port_index = 1 # taken from config file generated in example01_script.py

''' paths '''
path_to_palace = "/Users/firasabouzahr/Desktop/AWSPalace/install/bin/palace-arm64.bin"
mesh_dir = "mesh/"
config_dir = "config/"

''' load previously made config file '''
meshfile = mesh_dir + "qubit_resonator_mesh.bdf"
my_config = Config.load_config(config_dir + "example01.json")
 
''' create simulation object to extract results from completeted simulation '''
cavity_qubit_sim = Simulation(my_config,path_to_palace) # define simulation object

''' EPR analysis '''
LJ = Tools.get_LJ_from_config(my_config,JJ_port_index) # need it for EPR

# qubit parameters
f_q = cavity_qubit_sim.get_frequency_eigenmode(qubit_mode) # qubit frequency
p_q = cavity_qubit_sim.get_portEPR(JJ_port_index,qubit_mode) # qubit EPR to JJ

# resonator parameters
f_r = cavity_qubit_sim.get_frequency_eigenmode(resonator_mode) # resonator frequency
p_r = cavity_qubit_sim.get_portEPR(JJ_port_index,resonator_mode) # resonator EPR to JJ
kappa_int = cavity_qubit_sim.get_kappa_eigenmode(resonator_mode)

# calculate H params
alpha = EPR.calculate_anharmonicity(p_q,f_q,LJ) # unitless, GHz, Henries, returns in Hz
chi = EPR.calculate_dispersive_shift(p_q,p_r,f_q,f_r,LJ) # unitless, unitless, GHz, GHz, Henries, returns in Hz
g = EPR.calculate_coupling_strength(f_q,f_r,alpha,chi) # Hz

# scale to commonly used units
alpha = alpha / 1e6 # MHz
chi = chi / 1e3 # kHz
g = g / 1e6 # MHz

print("----------------------------")
print("Qubit Hamiltonian parameters")
print("----------------------------")
print(f"Frequency [GHz] = {f_q:.2f}")
print(f"Anharmonicity (⍺) [MHz] = {alpha:.2f} \n")
print("----------------------------")
print("Cavity Hamiltonian parameters")
print("----------------------------")
print(f"Frequency [GHz] = {f_q:.2f}")
print(f"kappa_internal (κ) [kHz] = {kappa_int:.2f} \n") # for kappa_loaded, we need feedline ports defined or driven simulations
print("----------------------------")
print("Cavity-Qubit Hamiltonian parameters")
print("----------------------------")
print(f"Chi Shift [kHz] = {chi:.2f}")
print(f"Coupling strength (g) [MHz] = {g:.2f}\n")
