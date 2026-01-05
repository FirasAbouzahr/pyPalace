from pypalace import Config, Model, Domains, Boundaries, Solver, Simulation

'''create config object'''
my_config = Config("tunable_xmon.json")

'''add Problem and Model blocks to config'''
my_config.add_Problem("Magnetostatic",Output="magneto_output")
my_config.add_Model(meshfile,L0=1e-6) # no adaptive mesh refinement, already finely meshed 

'''define materials and boundary conditions'''
# define materials
silicon = Domains.Material([1],1.0,11.45,0.0) # silicon
air = Domains.Material([2],1.0,1.0,0.0) # air
my_materials = [silicon,air] # material list for input into add_Domains()

# define boundary conditions
PECs = Boundaries.PEC([3,5,7,8]) # xmon cross, flux bias line, ground_plane, far_field
flux_port = Boundaries.SurfaceCurrent(Index=1,Attributes=[6],Direction="+X") # add surface current to the flux port to give flux line current
my_BCs = [PECs,flux_port] # boundary condition list for input into add_Boundaries()

'''add surface flux postprocessing'''
# add our "dummy" SQUID loop to SurfaceFlux postprocesssing so we can get magnetic flux through it
surfaceFlux_pp = Boundaries.Postprocessing_SurfaceFlux(Index=2,Attributes=[4],Type="Magnetic")
my_Boundaries_pp = [surfaceFlux_pp]

'''add Domains (materials) and Boundaries (BC and BC postprocessing) to config["Domains"] and config["Boundaries"], respectively:'''
# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_config.add_Domains(my_materials)
my_config.add_Boundaries(my_BCs,Postprocessing=my_Boundaries_pp)

'''add magnetostatic and linear solver parameters'''
magneto_params = Solver.Magnetostatic(Save=5)

Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-6,
                              MaxIts = 100)
                              
my_config.add_Solver(Simulation=magneto_params,Order= 2,Linear=Linear_params)

'''save config file'''
my_config.save_config()

