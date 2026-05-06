from pypalace import Config, Simulation,Tools
from pypalace.builder import Model, Domains, Boundaries, Solver

''' paths '''
path_to_palace = "/projects/p32999/palace/palace_install/bin/palace-x86_64.bin"
mesh_dir = "mesh/"
config_dir = "config/"

''' build Palace config file '''
meshfile = mesh_dir + "driven_resonator.bdf"
my_config = Config(config_dir + "example03.json")
 
# define config["Problem"]
my_config.add_Problem("Driven",Output="example03_output") # config["Problem"]

# define config["Model"] block
my_config.add_Model(meshfile,L0=1e-6)#,Refinement=my_refinement)

# define materials
silicon = Domains.Material(Attributes = [1],Permeability=1.0,Permittivity=11.45,LossTan=1e-07)
air = Domains.Material([2],1.0,1.0,0.0)
my_materials = [silicon,air] # material list for input into add_Domains()

# define boundary conditions
PECs = Boundaries.PEC([3,4,7,8])
Port1 = Boundaries.LumpedPort(Index=1,Attributes=[5],Direction="+Y",Excitation=True,R=50)
Port2 = Boundaries.LumpedPort(Index=2,Attributes=[6],Direction="-Y",R=50)
my_BCs = [PECs,Port1,Port2] # boundary condition list for input into add_Boundaries()

# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_config.add_Domains(my_materials)
my_config.add_Boundaries(my_BCs)

## driven parameters
driven_params = Solver.Driven(MinFreq=7.0740,MaxFreq=7.0760,FreqStep=0.00005,SaveStep=1)
# eigenfrequency should be 7.075 GHz
## linear solver parameters
Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-6,
                              MaxIts = 50)

## add them to config["Solver"] and solver["Linear"]
my_config.add_Solver(Simulation=driven_params,Order = 2,Linear=Linear_params)

# save it
my_config.save_config(check_validity=True) # checks validity of file and raises error if something is missing

''' simulate on an HPC '''

driven_cavity_sim = Simulation(my_config,path_to_palace) # define simulation object

n = 75 # MPI processses
slurm_directives = Simulation.HPC_options(
                                    partition="short", # #SBATCH --partition=short
                                    time="01:00:00", # #SBATCH --time=00:30:00
                                    nodes=1, # #SBATCH --nodes=1
                                    ntasks_per_node=n, # #SBATCH --ntasks-per-node=30
                                    mem=100, # #SBATCH --mem=75G
                                    job_name="QuSEN-resonator", # #SBATCH --job-name=test-job
                                    custom=["account=p32999"] # custom directives you want to add to the job script like account for example.
                                    )
driven_cavity_sim.run(n=n,HPC_options=slurm_directives)
