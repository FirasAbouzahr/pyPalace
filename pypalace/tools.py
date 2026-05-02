"""
Utility functions for working with pyPalace inputs and outputs.

This module provides helper functions for extracting mesh metadata and
simulation parameters from Palace mesh and configuration files.
"""

import pandas as pd
import subprocess
import numpy as np
import json
from .config import Config

class Tools:

    """
    General utility functions used by pyPalace workflows.

    These functions support mesh attribute extraction and retrieval of
    simulation parameters from :class:`pypalace.config.Config` objects.
    """
    
    @staticmethod
    def get_mesh_attributes(filename):
        """
        Extract physical attribute names, IDs, and entity types from a mesh file.

        Supported mesh formats include ``.bdf`` and ``.msh`` files.

        Parameters
        ----------
        filename : str
            Path to the mesh file.

        Returns
        -------
        pandas.DataFrame
            DataFrame with columns ``Name``, ``ID``, and ``Type``.
        """

        attributes_list = []
        attributes_dict = {"Name":[],"ID":[],"Type":[]}
        
        filetype = filename[-4:]
        
        if filetype == '.bdf':
        
            attributes_start = "$ Property cards"
            attributes_end = "$ Material cards"
            on_off_switch = 0
            
            with open(filename, 'r') as f:
                for line in f:
                    if attributes_start in line:
                        on_off_switch = 1

                    if on_off_switch == 1:
                        attributes_list.append(line)

                    if attributes_end in line:
                        break
                        
                    else:
                        pass
                
                if len(attributes_list) != 0:
                    for atts in attributes_list:
                        if "$ Name:" in atts:
                            attributes_dict["Name"] += [atts[8:][:-1]]
                        elif "PSOLID" in atts:
                            attributes_dict["ID"] += [atts.split()[1]]
                            attributes_dict["Type"] += ["Volume"]
                        elif "PSHELL" in atts:
                            attributes_dict["ID"] += [atts.split()[1]]
                            attributes_dict["Type"] += ["Surface"]
                            
            # Cubit seems to create phantom (not present in the actual geometry) domains, we ignore them
            if len(attributes_dict["Name"]) != len(attributes_dict["ID"]):
                attributes_dict["ID"] = attributes_dict["ID"][:len(attributes_dict["Name"])]
                attributes_dict["Type"] = attributes_dict["Type"][:len(attributes_dict["Name"])]

        elif filetype == '.msh':
            
            attributes_start = "$PhysicalNames"
            attributes_end = "$EndPhysicalNames"
            on_off_switch = 0
            
            with open(filename, 'r') as f:
                for line in f:
                    if on_off_switch == 1:
                        attributes_list.append(line)
                    
                    if attributes_start in line:
                        on_off_switch = 1

                    if attributes_end in line:
                        break
                        
                    else:
                        pass
                
                if len(attributes_list) != 0:
                    for atts in attributes_list:
                        atts = atts.split()

                        if len(atts) == 3:
                            attributes_dict["Name"] += [atts[2].strip('"')]
                            attributes_dict["ID"] += [atts[1]]

                            if atts[0] == "2":
                                attributes_dict["Type"] += ["Surface"]
                            elif atts[0] == "3":
                                attributes_dict["Type"] += ["Volume"]
            
        return pd.DataFrame(attributes_dict,index = None)

    @staticmethod
    def get_LJ_from_config(config:Config,JJ_index:int):
    
        """
        Extract the Josephson inductance from a Palace configuration.

        This searches the ``config["Boundaries"]["LumpedPort"]`` section for a
        lumped port with the specified index and returns its inductance value.

        Parameters
        ----------
        config : pypalace.config.Config
            Config object containing the Palace simulation setup.
        JJ_index : int
            Index of the lumped port representing the Josephson junction.

        Returns
        -------
        float
            Josephson inductance.
        """
        
        LumpedPorts = config.config["Boundaries"]["LumpedPort"]
        
        for port in LumpedPorts:
        
            if port["Index"] == JJ_index:
                LJ = port["L"]
                break
        
        return LJ
        
