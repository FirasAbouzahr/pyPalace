import pandas as pd
import subprocess
import numpy as np
import json
from .config import Config
from .tools import Tools

class Simulation:

    def __init__(self,config:Config,path_to_palace:str):
        self.path_to_palace = path_to_palace
        self.config = config
        self.path_to_json = self.config.config_name
        
    def HPC_options(partition,time,nodes,ntasks_per_node,mem,job_name,custom = None):
        
        partition = "partition={}".format(partition)
        time = "time={}".format(time)
        nodes = "nodes={}".format(nodes)
        ntasks_per_node = "ntasks-per-node={}".format(ntasks_per_node)
        mem = "mem={}G".format(mem)
        job_name = "job-name={}".format(job_name)
        
        slurm_list = [partition,time,nodes,ntasks_per_node,mem,job_name]
        
        if custom != None:
            for sbatches in custom:
                slurm_list.append(sbatches)
        
        return slurm_list
    
        
    def run(self,n,HPC_options=None,custom_script_name = None):
    
        if self.config.saved == False:
            self.config.save_config()
    
        if HPC_options == None:
            command = subprocess.run(["mpirun", "-n",str(n),self.path_to_palace,self.path_to_json],capture_output=True,text=True)
            print(command.stdout.strip())
            print(command.stderr.strip())

        else:
                if custom_script_name == None:
                    custom_script_name = "palace_jobscript.sh"
                
                with open(custom_script_name, "w") as file:
                
                    file.write("#!/bin/bash\n")
                    file.write("\n")
                    
                    for sbatches in HPC_options:
                        file.write("#SBATCH --{}\n".format(sbatches))
                
                    file.write("\n")
                    
                    file.write('export PALACE="{}"\n'.format(self.path_to_palace))
                    file.write('export MY_SIM="{}"\n'.format(self.path_to_json))
                    file.write('export MPI_PROCESSES={}\n'.format(n))
                    file.write("\n")
                    file.write("mpirun -n $MPI_PROCESSES $PALACE $MY_SIM")
                    

                command = subprocess.run(['sbatch', custom_script_name],capture_output=True,text=True)
                print(command.stdout.strip())
                print(command.stderr.strip())
                
        
        if self.config.sim["Problem"]["Type"] == "Electrostatic":
            cap_matrix_results = self.config.sim["Problem"]["Output"]+"/terminal-C.csv"
            cap_matrix = pd.read_csv(cap_matrix_results)
            cap_matrix = cap_matrix.drop(columns=['        i'])
            
            meshfile = self.config.sim["Model"]["Mesh"]
            mesh_attributes = Tools.get_mesh_attributes(meshfile)
            
            setup = self.config.sim["Boundaries"]["Terminal"]
            names = []
            for terminal in setup:
                cap_matrix_index = terminal["Index"]
                ID = terminal["Attributes"][0]
                names.append(mesh_attributes[mesh_attributes.ID==str(ID)].Name.iloc[0])
            
            
            cap_matrix.index = names
            cap_matrix.columns = names
            
            return cap_matrix
                
                
            
            
