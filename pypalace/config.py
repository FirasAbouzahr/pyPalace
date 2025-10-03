import json
import numpy as np

class Config:
    def __init__(self,Type,Verbose=2,Output="sim_output"):
        
        self.tracker = ["Problem"]

        self.Type = Type.lower().capitalize()
        
        self.sim = {"Problem":
                     {"Type":Type,
                      "Verbose":Verbose,
                      "Output":Output
                     }
                    }
    def add_Model(self,Mesh,L0=1.0e-6,Lc=0.0,Tol=None,MaxIts=None,MaxSize=None,Nonconformal=None,UpdateFraction=None,UniformLevels=None,SaveAdaptMesh=None,SaveAdaptIterations=None):

        self.tracker.append("Model")
        
        model_dict = {"Mesh":Mesh,
                      "L0":L0,
                      "Lc":Lc}

        refinement_list = np.array([Tol,MaxIts,MaxSize,Nonconformal,UpdateFraction,UniformLevels,SaveAdaptMesh,SaveAdaptIterations])
        refinement_labels = np.array(["Tol","MaxIts","MaxSize","Nonconformal","UpdateFraction","UniformLevels","SaveAdaptMesh","SaveAdaptIterations"])
        refinement_mask = refinement_list[:,] == None

        refinement_list = refinement_list[~refinement_mask]
        refinement_labels = refinement_labels[~refinement_mask]

        refinement_dict = {}
        
        for i in range(len(refinement_list)):
            refinement_dict[refinement_labels[i]] = refinement_list[i]

        if len(refinement_dict) != 0:
            model_dict["Refinement"] = refinement_dict

        self.sim["Model"] = model_dict

    def add_Domains(self,Materials,Postprocessing = []):
        self.tracker.append("Domains")

        domain_dict = {}

        domain_dict["Materials"] = list(Materials)

        if len(Postprocessing) != 0:

            postprocessing_dict = {}
            
            Postprocessing = np.array(Postprocessing)

            Energy_mask = Postprocessing[:, 1] == 'Energy'
            Probe_mask = Postprocessing[:, 1] == 'Probe'

            Energeies = Postprocessing[Energy_mask][:,0]
            Probes = Postprocessing[Probe_mask][:,0]

            if len(Energeies) != 0:
                postprocessing_dict["Energy"] = list(Energeies)
                
            if len(Probes) != 0:
                postprocessing_dict["Probe"] = list(Probes)

            domain_dict["Postprocessing"] = postprocessing_dict

        self.sim["Domains"] = domain_dict
        
    def add_Boundaries(self,BCs,Postprocessing = []):
        self.tracker.append("Boundaries")
        
        boundary_dict = {}
        
        BCs = np.array(BCs)
        Postprocessing = np.array(Postprocessing)
        
        BC_labels = ["PEC","PMC","LumpedPort","Impedance","Absorbing","Ground"]
        
        for lab in BC_labels:
            mask = BCs[:, 1] == lab
            current = BCs[mask][:,0]
            
            if len(current) == 1:
                boundary_dict[lab] = list(current)[0]
            elif len(current) >= 1:
                boundary_dict[lab] = list(current)
            else:
                pass

        if len(Postprocessing) != 0:

            postprocessing_dict = {}
            
            Postprocessing = np.array(Postprocessing)

            SurfaceFlux_mask = Postprocessing[:, 1] == 'SurfaceFlux'
            Dielectric_mask = Postprocessing[:, 1] == 'Dielectric'

            SurfaceFluxes = Postprocessing[SurfaceFlux_mask][:,0]
            Dielectrics = Postprocessing[Dielectric_mask][:,0]

            if len(SurfaceFluxes) != 0:
                postprocessing_dict["SurfaceFlux"] = list(SurfaceFluxes)
                
            if len(Dielectrics) != 0:
                postprocessing_dict["Dielectric"] = list(Dielectrics)

            boundary_dict["Postprocessing"] = postprocessing_dict

        self.sim["Boundaries"] = boundary_dict

    def add_Solver(self,Simulation,Order=1,Device="CPU",Linear=None):
        self.tracker.append("Solver")

        solver_dict = {"Order":Order,"Device":Device}

        if self.Type != Simulation[1]:
            raise ValueError("Your simulation type is invalid, use the function add_Solver_{} instead.".format(self.Type))

        solver_dict[self.Type] = Simulation[0]

        if Linear == None:
            solver_dict["Linear"] = {"Type":"Default","KSPType": "Default"}
        else:
            solver_dict["Linear"] = Linear

        self.sim["Solver"] = solver_dict

    def save_config(self,config_name,check_validity = True):
        
        if check_validity == True:
            validity_counter = []
            validity_list = ["Problem","Solver","Model","Domains"]

            for i in validity_list:
                if i in self.tracker:
                    validity_counter.append(0)
                else:
                    validity_counter.append(i)
                    
            if len(validity_counter) == 4:
                with open(config_name, "w") as f:
                    json.dump(self.sim, f, indent=2)   # indent=4 makes it pretty-printed
                    
            else:
                raise ValueError("Your AWS Palace configuration file is invalid, please add" + ", ".join(validity_counter) + "block(s)")

        else:
            with open(config_name, "w") as f:
                json.dump(self.sim, f, indent=2)
        

    def print_config(self):
        print(json.dumps(self.sim, indent=2))
