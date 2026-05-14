"""
Configuration interface for generating AWS Palace configuration files.

This module provides the :class:`Config` class for building, validating,
and saving Palace JSON configuration files.
"""

import json
import numpy as np

class Config:

    """
    Object used to generate AWS Palace configuration files.

    This class constructs and manages the JSON configuration structure
    used for Palace simulations.

    Parameters
    ----------
    config_name : str
        Name of the configuration and path where the JSON file will be saved.
    """
    
    
    def __init__(self,config_name:str):
    
        self.config_name = config_name
        self.tracker = []
        self.config = {}
        self.saved = False
        
    @classmethod
    def load_config(cls, config_name):
    
        """
        Creates a new config object from a pre-existing Palace configuration file.

        Parameters
        ----------
        config_name : str
            Path to pre-existing configuration file
        """
        
        with open(config_name, "r") as f:
            existing_config = json.load(f)

        this_config = cls(config_name)  # create instance

        this_config.tracker = ["Problem","Solver","Model","Domains","Boundaries"]
        this_config.config = existing_config

        return this_config
        
    def add_Problem(self, Type: str, Output: str, Verbose=2):
        """
        Add ``Problem`` block to the Palace configuration.
        
        This corresponds to the ``config["Problem"]`` section in the AWS Palace configuration file.

        Parameters
        ----------
        Type : str
            Problem type. Must be one of:
            "Electrostatic", "Magnetostatic", "Eigenmode",
            "Driven", "Transient", or "BoundaryMode".
        Output : str
            Directory path where simulation results will be saved.
        Verbose : int, optional
            Verbosity level of the Palace log file (default is 2).
        """
    
        self.tracker.append("Problem")

        self.Type = Type.lower().capitalize()
        if self.Type == "Boundarymode":
            self.Type = "BoundaryMode"

        self.config["Problem"] = {"Type":Type,
                               "Verbose":Verbose,
                               "Output":Output}

    def add_Model(self,Mesh:str,L0=1.0e-6,Lc=None,Refinement=None):
        """
        Add ``Model`` block to the Palace configuration.

        This corresponds to the ``config["Model"]`` section in the AWS Palace configuration file.
        
        Parameters
        ----------
        Mesh : str
            Path to mesh file to be simulated.
        L0 : float
            Length scale of mesh units relative to meters (default is 1.0e-6 corresponding to 1 mesh unit = 1 µm)
        Lc : float, optional
            Characteristic length scale used for nondimensionalization.
        Refinement : dict, optional
            Mesh refinement settings. This should be a dictionary generated using :func:`pypalace.builder.Model.Refinement`. 
        """
    
        self.tracker.append("Model")
        
        postprocessing_dict = {}
        model_dict = {"Mesh":Mesh,
                      "L0":L0}
        
        if Lc != None:
            model_dict["Lc"] = Lc
        
        if Refinement != None:
            model_dict["Refinement"] = Refinement

        self.config["Model"] = model_dict

    def add_Domains(self,Materials,Postprocessing = []):
        """
        Add ``Domains`` block to the Palace configuration.

        This corresponds to the ``config["Domains"]`` section in the AWS Palace configuration file.
        
        Parameters
        ----------
        Materials : list
            List of material definitions generated using :func:`pypalace.builder.Domains.Material`.
        Postprocessing : list, optional
            List of Domains postprocessing definitions generated using :mod:`pypalace.builder.Domains` postprocessing functions.
        """
    
        self.tracker.append("Domains")

        domain_dict = {}

        domain_dict["Materials"] = list(Materials)
        
        Postprocessing_labels = ["Energy","Probe"]
        
        if len(Postprocessing) != 0:
            for lab in Postprocessing_labels:

                mask = Postprocessing[:, 1] == lab
                current = Postprocessing[mask][:,0]

                if len(current) != 0:
                    postprocessing_dict[lab] = list(current)

                domain_dict["Postprocessing"] = postprocessing_dict

        self.config["Domains"] = domain_dict
        
    def add_Boundaries(self,BCs,Postprocessing = []):
    
        """
        Add ``Boundaries`` block to the Palace configuration.

        This corresponds to the ``config["Boundaries"]`` section in the AWS Palace configuration file.
        
        Parameters
        ----------
        BCs : list
            List of boundary conditions definitions generated using :mod:`pypalace.builder.Boundaries` boundary condition functions.
        Postprocessing : list, optional
            List of Boundaries postprocessing definitions generated using :mod:`pypalace.builder.Boundaries` postprocessing functions
            (``SurfaceFlux``, ``Dielectric``, ``FarField``, and on recent Palace builds also ``Impedance`` and ``Voltage`` under ``Postprocessing``).
        """
        
        self.tracker.append("Boundaries")
        
        postprocessing_dict = {}
        boundary_dict = {}
        
        BCs = np.array(BCs)
        Postprocessing = np.array(Postprocessing)
        
        BC_labels_scalartype = ["PEC","PMC","Absorbing","WavePortPEC","Ground","ZeroCharge","Periodic"]
        BC_labels_arraytype = ["Impedance","Conductivity","LumpedPort","WavePort","SurfaceCurrent","Terminal"]

        
        for lab in BC_labels_scalartype:
            mask = BCs[:, 1] == lab
            current = BCs[mask][:,0]
            
            if len(current) == 1:
                boundary_dict[lab] = list(current)[0]
        
        for lab in BC_labels_arraytype:
            mask = BCs[:, 1] == lab
            current = BCs[mask][:,0]
            
            if len(current) != 0:
                boundary_dict[lab] = list(current)
        
        Postprocessing_arraytype = ["SurfaceFlux","Dielectric","Impedance","Voltage"]
        Postprocessing_scalartype = ["FarField"]
        
        if len(Postprocessing) != 0:
            
            for lab in Postprocessing_arraytype:
            
                mask = Postprocessing[:, 1] == lab
                current = Postprocessing[mask][:,0]
                
                if len(current) != 0:
                    postprocessing_dict[lab] = list(current)
            
            for lab in Postprocessing_scalartype:
                mask = Postprocessing[:, 1] == lab
                current = Postprocessing[mask][:,0]
                if len(current) > 1:
                    raise ValueError(
                        'Multiple "{}" postprocessing entries are not supported; supply at most one.'.format(lab)
                    )
                if len(current) == 1:
                    postprocessing_dict[lab] = list(current)[0]
            
            boundary_dict["Postprocessing"] = postprocessing_dict
            
        self.config["Boundaries"] = boundary_dict

    def add_Solver(self,Simulation,Order=1,Device="CPU",Linear=None):
    
        """
        Add ``Solver`` block to the Palace configuration.

        This corresponds to the ``config["Solver"]`` section in the AWS Palace configuration file.
        
        Parameters
        ----------
        Simulation : dict
            Dictionary of simulation hyperparameters generated using :mod:`pypalace.builder.Solver` parameter functions.
        Order : int
            Finite element order.
        Device : str
            Runtime device configuration. Must be one of: "CPU", "GPU", "Debug".
        """
    
        self.tracker.append("Solver")

        solver_dict = {"Order":Order,"Device":Device}

        if self.Type != Simulation[1]:
            raise ValueError("Your simulation type is invalid, use the function add_Solver_{} instead.".format(self.Type))

        solver_dict[self.Type] = Simulation[0]

        if Linear == None:
            solver_dict["Linear"] = {"Type":"Default","KSPType": "Default"}
        else:
            solver_dict["Linear"] = Linear

        self.config["Solver"] = solver_dict

    def save_config(self,check_validity = True):
    
        """
        Saves Config object as AWS Palace .JSON configuration file.

        Parameters
        ----------
        check_validity : bool, optional
            If True, check that all required configuration blocks have been defined before saving (default True).
        """
    
        self.saved = True
        
        if check_validity == True:
            validity_counter = []
            validity_list = ["Problem","Solver","Model","Domains"]

            for i in validity_list:
                if i in self.tracker:
                    validity_counter.append(0)
                else:
                    validity_counter.append(i)
                    
            if len(validity_counter) == 4:
                with open(self.config_name, "w") as f:
                    json.dump(self.config, f, indent=2)   # indent=4 makes it pretty-printed
                    
            else:
                raise ValueError("Your AWS Palace configuration file is invalid, please add" + ", ".join(validity_counter) + "block(s)")

        else:
            with open(self.config_name, "w") as f:
                json.dump(self.config, f, indent=2)
        

    def print_config(self):
    
        """
        Print the current configuration as formatted JSON.
        """
        
        print(json.dumps(self.config, indent=2))
        


