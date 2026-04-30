import pandas as pd
import subprocess
import numpy as np
import json
from .config import Config
from .tools import Tools

class Simulation:



    def __init__(self,config:Config,path_to_palace:str):
    
        ''' 
        
        create Simulation object:
        
        config: pyPalace Config object
        path_to_palace: path/to/your/palace/install
    
        '''
    
        self.path_to_palace = path_to_palace
        self.config = config
        self.path_to_json = self.config.config_name
        
    def HPC_options(partition,time,nodes,ntasks_per_node,mem,job_name,custom = None):
    
    
        ''' 
        
        define slurm directives for running pyPalace simulations on HPC, input parameter into Simulation.run() 
    
        '''
        
        
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
    
        
    def run(self,n,HPC_options=None,custom_script_name=None):
    
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
                
                
    def get_capacitance_matrix(self):
        
        if self.config.config["Problem"]["Type"] != "Electrostatic":
            raise ValueError("Simulation type is not electrostatic, no capacitance matrix to extract")
        else:
            cap_matrix_results = self.config.config["Problem"]["Output"]+"/terminal-C.csv"
            cap_matrix = pd.read_csv(cap_matrix_results)
            cap_matrix = cap_matrix.drop(columns=['        i'])
            
            meshfile = self.config.config["Model"]["Mesh"]
            mesh_attributes = Tools.get_mesh_attributes(meshfile)
            
            setup = self.config.config["Boundaries"]["Terminal"]
            names = []
            for terminal in setup:
                cap_matrix_index = terminal["Index"]
                ID = terminal["Attributes"][0]
                names.append(mesh_attributes[mesh_attributes.ID==str(ID)].Name.iloc[0])
            
            cap_matrix.index = names
            cap_matrix.columns = names
            
            return cap_matrix
    
    def get_eigenFrequencies(self):
    
        if self.config.config["Problem"]["Type"] != "Eigenmode":
            raise ValueError("Simulation type is not eigenmode, no eigenfrequencies to extract")
            
        else:
        
            freq_results = self.config.config["Problem"]["Output"]+"/eig.csv"
            freqs = pd.read_csv(freq_results,usecols = [0,1,2,3])
            freqs.columns = ["mode","frequency_GHz","frequency_Im","Q"]
            
            return freqs
                
    def get_portEPR(self,port_index:int):
    
        if self.config.config["Problem"]["Type"] != "Eigenmode":
            raise ValueError("Simulation type is not eigenmode, no port EPR to extract")
            
        try:
            EPR_results = self.config.config["Problem"]["Output"]+"/port-EPR.csv"
            EPR = pd.read_csv(EPR_results,usecols=[0,port_index + 1])
            EPR.columns = ["mode","EPR"]
            return
            
        except:
            raise ValueError("Are you sure you defined a port?")

    def get_Sij(self,index1:int,index2:int):
    
        if self.config.config["Problem"]["Type"] != "Driven":
            raise ValueError("Simulation type is not Driven, no port S-parameters to extract")
            
        else:
        
            Smatrix_results = self.config.config["Problem"]["Output"]+"/port-S.csv"
            Smatrix = pd.read_csv(Smatrix_results)
            
            ReSij =  '             |S[{}][{}]| (dB)'.format(index1,index2)
            ImSij =  '        arg(S[{}][{}]) (deg.)'.format(index1,index2)
            
            try:
                f_GHz = Smatrix['        f (GHz)'].to_numpy()
                ReSij_column = Smatrix[ReSij].to_numpy()
                ImSij_column = Smatrix[ImSij].to_numpy()
                columns = ["frequency_GHz","|S[{}][{}]| (dB)".format(index1,index2),"arg(S[{}][{}]) (deg)".format(index1,index2)]
                Scustom = pd.Dataframe({columns[0]:f_GHz,columns[1]:ReSij_column,columns[2]:ImSij_column})
                return Scustom
                
            except:
                raise ValueError("Selected S_ij matrix elements do not exist, please check specified indices")

        
