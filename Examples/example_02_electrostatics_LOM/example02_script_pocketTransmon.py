from pypalace import Config, Simulation
from pypalace.builder import Model, Domains, Boundaries, Solver
from pypalace.analysis import LOM

''' path to Palace executable '''
path_to_palace = "/Users/firasabouzahr/Desktop/AWSPalace/install/bin/palace-arm64.bin" # change to your path

''' path to mesh files / where we will save generated config files '''
mesh_dir = "mesh/"
config_dir = "config/"

''' path to mesh file + name of config file we will generate in pyPalace'''
pocket_meshfile = mesh_dir + "pocket_transmon.bdf"
pocket_path_to_json = config_dir + "pocket_transmon-electrostatic_sim.json"

''' Define config object '''
pocket_config = Config(pocket_path_to_json)

''' Problem and Model '''
pocket_config.add_Problem(Type="Electrostatic",Output="pocket_electro_output")
pocket_config.add_Model(pocket_meshfile) # no AMR, meshed finely already

''' Materials '''
silicon = Domains.Material([1],1.0,11.45,0.0) # silicon
air = Domains.Material([2],1.0,1.0,0.0) # air
pocket_config.add_Domains(Materials=[silicon,air]) # add the materials

''' Boundary Conditions '''
## terminals ##
top_pad_terminal = Boundaries.Terminal(Index=1,Attributes=[3]) # top capacitor pad
bottom_pad_terminal = Boundaries.Terminal(Index=2,Attributes=[4]) # bottom capacitor pad
coupler_terminal = Boundaries.Terminal(Index=3,Attributes=[5]) # qubit-res coupler
resonator_terminal = Boundaries.Terminal(Index=4,Attributes=[6]) # truncated resonator - we won't use this but must assign it something

## Ground ##
Grounds = Boundaries.Ground(Attributes=[7,8]) ## ground plane, far field

''' Boundary Postprocessing '''
top_pad_sf = Boundaries.Postprocessing_SurfaceFlux(Index=1,Attributes=[3],Type="Electric")
bottom_pad_sf = Boundaries.Postprocessing_SurfaceFlux(Index=2,Attributes=[4],Type="Electric")
coupler_pad_sf = Boundaries.Postprocessing_SurfaceFlux(Index=3,Attributes=[5],Type="Electric")
resonator_sf = Boundaries.Postprocessing_SurfaceFlux(Index=4,Attributes=[6],Type="Electric")

my_BCs = [top_pad_terminal,bottom_pad_terminal,coupler_terminal,Grounds]
my_BC_postprocessing = [top_pad_sf,bottom_pad_sf,coupler_pad_sf,resonator_sf]

## add boundary conditions and boundary postprocessing
pocket_config.add_Boundaries(BCs=my_BCs,Postprocessing=my_BC_postprocessing)

''' electrostatic simulation and linear solver paramters '''
electro_params = Solver.Electrostatic(Save=3)

Linear_params = Solver.Linear(Type="BoomerAMG",
                              KSPType = "CG",
                              Tol = 1e-6, # make more stringent for better results
                              MaxIts = 25)
                              
pocket_config.add_Solver(Simulation=electro_params,
                     Order= 2, # second order solver
                     Linear=Linear_params)
                       
''' run the simulation '''
pocket_simulation = Simulation(pocket_config,path_to_palace)
pocket_simulation.run(n=5) # 5 mpi processses

capacitance_matrix = pocket_simulation.get_capacitance_matrix()

''' LOM analysis to extract Hamiltonian parameters '''
C00 = capacitance_matrix.iloc[0,0]
C11 = capacitance_matrix.iloc[1,1]
C01 = capacitance_matrix.iloc[0,1]
C02 = capacitance_matrix.iloc[0,2]

C_Sigma = abs(C01) + ((C00 + C01)*(C11+C01))/(C00 + C11 + 2*C01) + abs(C02)
LJ = 14e-09

Hamiltonian_params = LOM.get_Hamiltonian_parameters(C_Sigma,LJ)
print(Hamiltonian_params)
