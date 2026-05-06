from pypalace import Config, Simulation,Tools
from pypalace.builder import Model, Domains, Boundaries, Solver

''' paths '''
path_to_palace = "/Users/firasabouzahr/Desktop/AWSPalace/install/bin/palace-arm64.bin"
mesh_dir = "mesh/"
config_dir = "config/"

''' build Palace config file '''
meshfile = mesh_dir + "qubit_resonator_mesh.bdf"
my_config = Config(config_dir + "example01.json")
 
# define config["Problem"]
my_config.add_Problem("Eigenmode",Output="example01_output") # config["Problem"]

# define adaptive mesh refinement, the qubit is coarsely meshed to save on file size so we use AMR to boost simulation accuracy
my_refinement = Model.Refinement(Tol = 1e-6,MaxIts = 3)

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
                                    N = 3,
                                    Save = 3)
## linear solver parameters
Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-8,
                              MaxIts = 50)

## add them to config["Solver"] and solver["Linear"]
my_config.add_Solver(Simulation=eigenmode_params,Order = 2,Linear=Linear_params)

# save it
my_config.save_config(check_validity=True) # checks validity of file and raises error if something is missing

''' simulate on an HPC '''
cavity_qubit_sim = Simulation(my_config,path_to_palace) # define simulation object

n = 32 # MPI processses
slurm_directives = Simulation.HPC_options(
                                    partition="short", # #SBATCH --partition=short
                                    time="00:30:00", # #SBATCH --time=00:30:00
                                    nodes=1, # #SBATCH --nodes=1
                                    ntasks_per_node=n, # #SBATCH --ntasks-per-node=30
                                    mem=75, # #SBATCH --mem=75G
                                    job_name="test-job", # #SBATCH --job-name=test-job
                                    custom=["account=p#####"] # custom directives you want to add to the job script like account for example.
                                    )


cavity_qubit_sim.run(n=n,HPC_options=slurm_directives) # 32 mpi processses
