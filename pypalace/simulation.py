import pandas as pd
import subprocess

class Simulation:

    def __init__(self,path_to_palace):
        self.path_to_palace = path_to_palace
        
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

    def run_palace(self,n,path_to_json):
        command = subprocess.run(["mpirun", "-n",str(n),self.path_to_palace,path_to_json],capture_output=True,text=True)
        print(command.stdout.strip())
        print(command.stderr.strip())

    def run_palace_HPC(self,n,path_to_json,HPC_options,custom_script_name = None):
        
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
            file.write('export MY_SIM="{}"\n'.format(path_to_json))
            file.write('export MPI_PROCESSES={}\n'.format(n))
            file.write("\n")
            file.write("mpirun -n $MPI_PROCESSES $PALACE $MY_SIM")


        command = subprocess.run(['sbatch', custom_script_name],capture_output=True,text=True)
        print(command.stdout.strip())
        print(command.stderr.strip())
            
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
