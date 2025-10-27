import pandas as pd

class Simulation:
    
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

