from pypalace import Config, Simulation
from pypalace.builder import Model, Domains, Boundaries, Solver
from pypalace.analysis import LOM

''' path to Palace executable '''
path_to_palace = "/Users/firasabouzahr/Desktop/AWSPalace/install/bin/palace-arm64.bin" # change to your path
 
''' path to mesh files / where we will save generated config files '''
mesh_dir = "mesh/"
config_dir = "config/"

''' path to mesh file + name of config file we will generate in pyPalace'''
xmon_meshfile = mesh_dir + "xmon.bdf"
xmon_path_to_json = config_dir + "xmon-electrostatic_sim.json"

''' Define config object '''
xmon_config = Config(xmon_path_to_json)

''' Problem and Model '''
xmon_config.add_Problem(Type="Electrostatic",Output="xmon_electro_output")
xmon_config.add_Model(xmon_meshfile) # no AMR, meshed finely already

''' Materials '''
silicon = Domains.Material([1],1.0,11.45,0.0) # silicon
air = Domains.Material([2],1.0,1.0,0.0) # air
xmon_config.add_Domains(Materials=[silicon,air]) # add the materials

''' Boundary Conditions '''
## terminals ##
cross_terminal = Boundaries.Terminal(Index=1,Attributes=[3]) # qubit cross
claw_terminal = Boundaries.Terminal(Index=2,Attributes=[4]) # claw

## Ground ##
Grounds = Boundaries.Ground(Attributes=[5,6]) # ground plane, far field

''' Boundary Postprocessing '''
cross_sf = Boundaries.Postprocessing_SurfaceFlux(Index=1,Attributes=[3],Type="Electric")
claw_sf = Boundaries.Postprocessing_SurfaceFlux(Index=2,Attributes=[4],Type="Electric")

my_BCs = [cross_terminal,claw_terminal,Grounds]
my_BC_postprocessing = [cross_sf,claw_sf]

## add boundary conditions and boundary postprocessing
xmon_config.add_Boundaries(BCs=my_BCs,Postprocessing=my_BC_postprocessing)

''' electrostatic simulation and linear solver paramters '''
electro_params = Solver.Electrostatic(Save=3)

Linear_params = Solver.Linear(Type="BoomerAMG",
                              KSPType = "CG",
                              Tol = 1e-6, # make more stringent for better results
                              MaxIts = 25)
                              
xmon_config.add_Solver(Simulation=electro_params,
                       Order= 2, # second order solver
                       Linear=Linear_params)
                       
''' run the simulation & extract capacitance matrix'''
xmon_simulation = Simulation(xmon_config,path_to_palace)
xmon_simulation.run(n=5) # 5 mpi processses

capacitance_matrix = xmon_simulation.get_capacitance_matrix()

''' LOM analysis to extract Hamiltonian parameters '''
C00 = capacitance_matrix.iloc[0,0]
C_Sigma = C00
LJ = 14e-09 # 10 nH

Hamiltonian_params = LOM.get_Hamiltonian_parameters(C_Sigma,LJ)
print(Hamiltonian_params)
