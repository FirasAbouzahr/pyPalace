import pandas as pd
import subprocess
import numpy as np
import json

## defining constants ##
hbar = 1.0545718176461565e-34
h = 6.62607015e-34
pi = np.pi
phi0 = 2.0678338484619295e-15

class Simulation:

    def __init__(self,path_to_palace,path_to_json):
        self.path_to_palace = path_to_palace
        self.path_to_json = path_to_json
        
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

    def run_palace(self,n):
        
        command = subprocess.run(["mpirun", "-n",str(n),self.path_to_palace,self.path_to_json],capture_output=True,text=True)
        print(command.stdout.strip())
        print(command.stderr.strip())

    def run_palace_HPC(self,n,HPC_options,custom_script_name = None):
        
        if n != int(HPC_options[3][-2:]):
            print("Best practice is to match number of mpi process to number of corses per node. Overwriting to n = ntasks-per-node")
            n = int(HPC_options[3][-2:])
            
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
        
    # f_q in GHz (default of Palace), Ej in Joules, Lj in Henries
    def calculate_anharmonicity(p_q,f_q,Ej = None,Lj = None):

        if Ej == None and Lj == None:
            raise ValueError("Please enter a value for either Ej or Lj")
        elif Ej != None and Lj != None:
            print("Both Ej and Lj defined, defaulting to calculation using Ej")
        elif Ej == None and Lj != None:
            Ej = phi0**2/((2*pi)**2*Lj)

        w_q = 2 * np.pi * f_q * 10**9
        alpha_q = p_q**2 * (hbar * w_q**2)/(8 * Ej) # calculate alpha
        alpha_q = (alpha_q / (2*pi)) * 10**-6 # convert to MHz
        
        return -alpha_q

    def calculate_dispersive_shift(p_q,p_r,f_q,f_r,Ej = None,Lj = None):
        
        if Ej == None and Lj == None:
            raise ValueError("Please enter a value for either Ej or Lj")
        elif Ej != None and Lj != None:
            print("Both Ej and Lj defined, defaulting to calculation using Ej")
        elif Ej == None and Lj != None:
            Ej = phi0**2/((2*pi)**2*Lj)

        w_q = 2 * pi * f_q * 10**9
        w_r = 2 * pi * f_r * 10**9

        chi = p_q * p_r * (hbar * w_q * w_r) / (4 * Ej) # calculate chi
        chi = (chi / (2*pi)) * 10**-6 # convert to MHz
 
        return -chi

    def calculate_lamb_shift(alpha_q,chi):
        return alpha_q - chi/2
        
    def calculate_coupling_strength(f_q,f_r,alpha_q,chi):
        delta = (f_r - f_q)*1000
        sigma = (f_q + f_r)*1000
        denom = alpha_q/(delta *(delta - alpha_q)) + alpha_q/(sigma*(sigma + alpha_q))
        g = np.sqrt(chi/denom/2)
        return g

    def calculate_lamb_shift(alpha_q,chi):
        return alpha_q - chi/2

    def get_anharmonicity(self,qubit_mode,JJ_LumpedPort_index):
        
        with open(self.path_to_json, "r") as f:
            this_config = json.load(f)
        
        output_folder = this_config["Problem"]["Output"]

        # extract the JJ's indunctance (Lj) from config file based on LumpedPort index given
        for lp in this_config["Boundaries"]["LumpedPort"]:
            if lp["Index"] == JJ_LumpedPort_index:
                Lj = lp["L"]

        # convert to Ej
        Ej = phi0**2/((2*np.pi)**2*Lj)

        eigenvals = pd.read_csv(output_folder + "/eig.csv",usecols = [0,1])
        eigenvals.columns = ["m","f"]
        EPR = pd.read_csv(output_folder + "/port-EPR.csv")
        EPR.columns = ["m","p"]

        f_q = eigenvals[eigenvals.m == qubit_mode].f.iloc[0]
        p_q = EPR[EPR.m == qubit_mode].p.iloc[0]

        alpha_q = Simulation.calculate_anharmonicity(p_q,f_q,Ej)

        return alpha_q

    def get_dispersive_shift(self,qubit_mode,resonator_mode,JJ_LumpedPort_index):
        
        with open(self.path_to_json, "r") as f:
            this_config = json.load(f)
        
        output_folder = this_config["Problem"]["Output"]

        # extract the JJ's indunctance (Lj) from config file based on LumpedPort index given
        for lp in this_config["Boundaries"]["LumpedPort"]:
            if lp["Index"] == JJ_LumpedPort_index:
                Lj = lp["L"]

        # convert to Ej
        Ej = phi0**2/((2*np.pi)**2*Lj)

        eigenvals = pd.read_csv(output_folder + "/eig.csv",usecols = [0,1])
        eigenvals.columns = ["m","f"]
        EPR = pd.read_csv(output_folder + "/port-EPR.csv")
        EPR.columns = ["m","p"]

        f_q = eigenvals[eigenvals.m == qubit_mode].f.iloc[0]
        f_r = eigenvals[eigenvals.m == resonator_mode].f.iloc[0]
        p_q = EPR[EPR.m == qubit_mode].p.iloc[0]
        p_r = EPR[EPR.m == resonator_mode].p.iloc[0]

        chi = Simulation.calculate_dispersive_shift(p_q,p_r,f_q,f_r,Ej)

        return chi

    def get_lamb_shift(self,alpha_q,chi):
        return Simulation.calculate_lamb_shift(alpha_q,chi)

    def get_coupling_strength(self,qubit_mode,resonator_mode,JJ_LumpedPort_index):
        
        with open(self.path_to_json, "r") as f:
            this_config = json.load(f)
        
        output_folder = this_config["Problem"]["Output"]

        # extract the JJ's indunctance (Lj) from config file based on LumpedPort index given
        for lp in this_config["Boundaries"]["LumpedPort"]:
            if lp["Index"] == JJ_LumpedPort_index:
                Lj = lp["L"]

        # convert to Ej
        Ej = phi0**2/((2*np.pi)**2*Lj)

        eigenvals = pd.read_csv(output_folder + "/eig.csv",usecols = [0,1])
        eigenvals.columns = ["m","f"]
        EPR = pd.read_csv(output_folder + "/port-EPR.csv")
        EPR.columns = ["m","p"]

        f_q = eigenvals[eigenvals.m == qubit_mode].f.iloc[0]
        f_r = eigenvals[eigenvals.m == resonator_mode].f.iloc[0]
        p_q = EPR[EPR.m == qubit_mode].p.iloc[0]
        p_r = EPR[EPR.m == resonator_mode].p.iloc[0]

        alpha_q = Simulation.calculate_anharmonicity(p_q,f_q,Ej)
        chi = Simulation.calculate_dispersive_shift(p_q,p_r,f_q,f_r,Ej)
        g = Simulation.calculate_coupling_strength(f_q,f_r,alpha_q,chi)
        return g
        
    def get_mesh_attributes(filename):

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
