from pypalace import Simulation, Config, Model, Domains, Boundaries, Solver

meshfile = "qubit_resonator_mesh.bdf"
my_config = Config("Eigenmode",Output="eigenmode_output") # config["Problem"]
 
# define adaptive mesh refinement, the qubit is coarsely meshed to save on file size so we use AMR to boost simulation accuracy
my_refinement = Model.Refinement(Tol = 1e-6,MaxIts = 4)

# define config["Model"] block
my_config.add_Model(meshfile,L0=1e-6,Refinement=my_refinement)

# define materials
sapphire = Domains.Material(Attributes = [1],Permeability=1.0,Permittivity=[9.3,9.3,11.4],MaterialAxes=[[1,0,0],[0,1,0],[0,0,1]],LossTan=8.6e-5)
air = Domains.Material([2],1.0,1.0,0.0)
my_materials = [sapphire,air] # material list for input into add_Domains()

# define boundary conditions
PECs = Boundaries.PEC([3,4,5,7,8]) #
JJ = Boundaries.LumpedPort(Index=1,Attributes=[6],Direction="+X",R=0,L=round(10.4*10**(-9),9),C=0)
my_BCs = [PECs,JJ] # boundary condition list for input into add_Boundaries()

# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_config.add_Domains(my_materials)
my_config.add_Boundaries(my_BCs)

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
my_config.add_Solver(Simulation=eigenmode_params,Order = 2,Linear=Linear_params)

# save it
my_config.save_config("qubit_res.json",check_validity=True) # checks validity of file and raises error if something is missing
