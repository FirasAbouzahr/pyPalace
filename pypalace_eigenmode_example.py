from pypalace import Simulation, Domains, Boundaries, Solver

my_sim = Simulation("Eigenmode",Output="eigenmode_output")

my_sim.add_Model("test.msh",
                 Tol = 1.0e-2,
                 MaxIts = 3,
                 SaveAdaptIterations = True,
                 SaveAdaptMesh = True,
                 Nonconformal = False)

# define materials
silicon = Domains.Material([8],1.0,11.5,0.0)
air = Domains.Material([6,7],1.0,1.0,0.0)
my_materials = [silicon,air]

# define boundary conditions
PECs = Boundaries.PEC([1,2,3])
LP1 = Boundaries.LumpedPort(1,[9],"+X",50.0,0.0,0.0)
LP2 = Boundaries.LumpedPort(2,[10],"-X",50.0,0.0,0.0)
LP3 = Boundaries.LumpedPort(3,[11],"-Y",50.0,0.0,0.0)
LP4 = Boundaries.LumpedPort(4,[12],"+Y",50.0,0.0,0.0)
Impedance1 = Boundaries.Impedance([5],Rs = 4.5440e+10)
my_BCs = [PECs,LP1,LP2,LP3,LP4,Impedance1]

# define postprocessing
Energy1 = Domains.Postprocessing_Energy(1,[8])
Domain_postprocessing = [Energy1]

# define Eigenmode and Linear parameters
eigenmode_params = Solver.Eigenmode(Target = 2.0,
                                    Tol = 1.0e-8,
                                    N = 10,
                                    Save = 10)

Linear_params = Solver.Linear(KSPType = "GMRES",
                              Tol = 1e-08,
                              MaxIts = 500)

my_sim.add_Domains(my_materials,Domain_postprocessing)
my_sim.add_Boundaries(my_BCs)
my_sim.add_Solver(Simulation=eigenmode_params,Order = 2,Linear=Linear_params)

my_sim.print_config()
my_sim.save_config("eigenmode_example.json")
