from pypalace import Config, Model, Domains, Boundaries, Solver, Simulation

meshfile = "single_resonator_mesh.bdf"

'''Now let's create our Config object, which defines config["Problem"], and let's also create config["Model"]:'''
my_sim = Config("Eigenmode",Output="resonator_eigenmode_output") # creates config["Problem"]
my_sim.add_Model(meshfile) # creates config["Model"], no AMR because the circuit element is already meshed finely

'''Now we define our materials:'''
# define materials
silicon = Domains.Material([1],1.0,11.45,0.0) # silicon
air = Domains.Material([2],1.0,1.0,0.0) # air
my_materials = [silicon,air] # material list for input into add_Domains()

'''and our boundary conditions:'''
# define boundary conditions
PECs = Boundaries.PEC([3,6,7,8,9]) # resonator, far field, feedline, ground plane(s)
Lumped1 = Boundaries.LumpedPort(Index=1,Attributes=[4],Direction="+X",R=50,L=0,C=0) # for Q_c calculations or to drive later
Lumped2 = Boundaries.LumpedPort(Index=2,Attributes=[5],Direction="-X",R=50,L=0,C=0)
my_BCs = [PECs,Lumped1,Lumped2] # boundary condition list for input into add_Boundaries()

'''Now let's add config["Domains"] and config["Boundaries"] using our material and BC lists defined above.'''
my_sim.add_Domains(my_materials)
my_sim.add_Boundaries(my_BCs)

'''Define our eigenmode and linear solver parameters and add them to the config["Solver"] block'''
eigenmode_params = Solver.Eigenmode(Target = 1.0,
                                    Tol = 1.0e-6,
                                    N = 5,
                                    Save = 5)

Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-6,
                              MaxIts = 10)

my_sim.add_Solver(Simulation=eigenmode_params,Order = 1,Linear=Linear_params)

'''we are ready to save the config file and start simulating (:'''
'''Note save_config() will also do a validity check and error out if it finds that you did not make a valid config file (e.g., you're missing a required block):'''
my_sim.save_config("single_resonator.json")
