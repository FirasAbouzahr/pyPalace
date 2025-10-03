from pypalace import Config, Domains, Boundaries, Solver

my_sim = Config("Eigenmode",Output="eigenmode_output")
my_sim.add_Model("eigenmode_example.bdf")

# define materials
silicon = Domains.Material([1],1.0,11.45,0.0)
air = Domains.Material([2],1.0,1.0,0.0)
my_materials = [silicon,air] # material list for input into add_Domains()


PECs = Boundaries.PEC([3,6,7,8,9]) # resonator, far field, feedline, ground plane(s)
Lumped1 = Boundaries.LumpedPort(Index=1,Attributes=[4],Direction="+X",R=50,L=0,C=0) # not necessary for eigenmode simulation
Lumped2 = Boundaries.LumpedPort(Index=2,Attributes=[5],Direction="-X",R=50,L=0,C=0)
my_BCs = [PECs,Lumped1,Lumped2] # boundary condition list for input into add_Boundaries()

# add config["Domains"] and config["Boundaries"] using our material and BC lists above
my_sim.add_Domains(my_materials)
my_sim.add_Boundaries(my_BCs)

eigenmode_params = Solver.Eigenmode(Target = 1.0,
                                    Tol = 1.0e-10,
                                    N = 5,
                                    Save = 5)

Linear_params = Solver.Linear(Type="Default",
                              KSPType = "Default",
                              Tol = 1e-10,
                              MaxIts = 10)

my_sim.add_Solver(Simulation=eigenmode_params,Order = 1,Linear=Linear_params)

my_sim.print_config()
my_sim.save_config("eigenmode_example.json")
