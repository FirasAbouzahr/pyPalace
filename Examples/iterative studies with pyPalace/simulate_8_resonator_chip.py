from pypalace import Config, Model, Domains, Boundaries, Solver, Simulation

for i in range(8):
    current_mesh = "res{}.bdf".format(i)
    my_config = Config("Eigenmode",Output="res{}_output".format(i)) # config["Problem"]

    # define config["Model"] block
    my_config.add_Model(current_mesh,L0=1e-6)#,Refinement=my_refinement)

    # define materials
    sapphire = Domains.Material(Attributes = [1],
                                Permeability=[1.0,1.0,1.0],
                                Permittivity=[9.3,9.3,11.4], # anisotropic
                                LossTan=[15*10**(-4)]*3, # EFG sapphire loss tangent from https://arxiv.org/pdf/2206.14334
                                MaterialAxes=[[1,0,0],[0,1,0],[0,0,1]])
    air = Domains.Material([2],1.0,1.0,0.0)
    my_materials = [sapphire,air] # material list for input into add_Domains()
    
    # define boundary conditions
    PECs = Boundaries.PEC([3,4,7,8]) # resonator, feedline, ground_plane, far_field
    left_LP = Boundaries.LumpedPort(Index=1,Attributes=[5],Direction="+X",R=50,L=0,C=0)
    right_LP = Boundaries.LumpedPort(Index=2,Attributes=[6],Direction="-X",R=50,L=0,C=0)
    my_BCs = [PECs,left_LP,right_LP] # boundary condition list for input into add_Boundaries()
    
    # add config["Domains"] and config["Boundaries"] using our material and BC lists above
    my_config.add_Domains(my_materials)
    my_config.add_Boundaries(my_BCs)

    ## eigenmode parameters
    eigenmode_params = Solver.Eigenmode(Target = 3.0,
                                        Tol = 1.0e-8,
                                        N = 4,
                                        Save = 4)
    ## linear solver parameters
    Linear_params = Solver.Linear(Type="Default",
                                  KSPType = "Default",
                                  Tol = 1e-8,
                                  MaxIts = 50)
    
    ## add them to config["Solver"] and solver["Linear"]
    my_config.add_Solver(Simulation=eigenmode_params,Order = 2,Linear=Linear_params)
    
    ## save this config
    current_config = "res{}_config.json".format(i)
    my_config.save_config(current_config) # checks validity of file and raises error if something is missing
    
    
    ##################################################
    ##################################################
    #### create slurm scripts and submit HPC jobs ####
    ##################################################
    ##################################################
    
    palace = "/projects/p32999/palace/palace_install/bin/palace-x86_64.bin"
    config = "/projects/p32999/pyPalace/{}".format(current_config)
    my_sim = Simulation(palace,config)
    
    HPC_options = Simulation.HPC_options(
                                    partition="short", # #SBATCH --partition=short
                                    time="00:30:00", # #SBATCH --time=00:30:00
                                    nodes=1, # #SBATCH --nodes=1
                                    ntasks_per_node=100, # #SBATCH --ntasks-per-node=30
                                    mem=100, # #SBATCH --mem=64G
                                    job_name="res{}".format(i), # #SBATCH --job-name=test-job
                                    custom=["account=p32999"]) # custom directives you want to add to the job script, for example at my university we need to add account
                                    
                                    
    my_sim.run_palace_HPC(n=100, # number of MPI processes
                          HPC_options=HPC_options, # Slurm directives (e.g, request HPC resources)
                          custom_script_name="jobscript_res{}".format(i)) 
