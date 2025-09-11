from pypalace.simulation import eigenmode
from pypalace.builder import *

# initialize eigenmode simulation
my_eigen_sim = eigenmode("test_script.json","outputfiles")

# define model parameters and optionally add Refinement
my_eigen_sim.add_model(Mesh = "test.msh",
                       L0 = 0.001,
                       Tol = 1.0e-2,
                       MaxIts = 3,
                       SaveAdaptIterations = True,
                       SaveAdaptMesh = True,
                       Nonconformal = False)

# define materials
silicon = Material([8],1.0,11.5,0.0)
air = Material([6,7],1.0,1.0,0.0)
my_materials = [silicon,air]

# define boundary conditions
PECs = BoundaryCondition_PEC([1,2,3])
LP1 = BoundaryCondition_LumpedPort(1,[9],"+X",50.0,0.0,0.0)
LP2 = BoundaryCondition_LumpedPort(2,[10],"-X",50.0,0.0,0.0)
LP3 = BoundaryCondition_LumpedPort(3,[11],"-Y",50.0,0.0,0.0)
LP4 = BoundaryCondition_LumpedPort(4,[12],"+Y",50.0,0.0,0.0)
Impedance1 = BoundaryCondition_Impedance([5],Rs = 4.5440e+10)
my_BCs = [PECs,LP1,LP2,LP3,LP4,Impedance1]

# define postprocessing
Energy1 = PostProcessing_Domain_Energy(1,[8])
my_postprocessing = [Energy1]

# add materials, boundary conditions, postprocessing
my_eigen_sim.add_Domains(my_materials)
my_eigen_sim.add_Boundaries(my_BCs)
my_eigen_sim.add_Postprocessing(my_postprocessing)

# add simulation hyperparameters
my_eigen_sim.add_Solver(N = 10, # number of eigenmodes to solve
                        Eigenmode_tol = 1.0e-8, # error tolerance
                        Target = 2.0, # target frequency
                        Save = 10, # eigenmodes to save
                        Type = "Default", # solver type
                        KSPType = "GMRES", # krylov method type
                        Tol = 1.0e-8, # solver tolerance
                        Order = 2, # solver order
                       )

my_eigen_sim.publish_script()
my_eigen_sim.print_script()
