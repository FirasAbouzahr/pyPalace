import numpy as np

class eigenmode:
    def __init__(self,filename,Output,Verbose=2):
        self.filename = filename
        self.tracker = []
        with open(self.filename, "w") as file:
            file.write('{ \n "Problem": \n{\n "Type": "Eigenmode", \n "Verbose":' + str(Verbose) + ', \n "Output":' + Output + '\n},\n')

    def add_model(self,Mesh,L0,UniformLevels=None,Tol=None,MaxIts=None,SaveAdaptIterations=None,SaveAdaptMesh=None,Nonconformal=None):
        self.tracker.append("Model")

        refinement_list = np.array([UniformLevels,Tol,MaxIts,SaveAdaptIterations,SaveAdaptMesh,Nonconformal])
        refinement_labels = np.array(["UniformLevels","Tol","MaxIts","SaveAdaptIterations","SaveAdaptMesh","Nonconformal"])
        
        refinement_mask = refinement_list[:] == None
        refinement_list = refinement_list[~refinement_mask]
        refinement_labels = refinement_labels[~refinement_mask]
        
        refinement_string = ''
        
        for i in range(len(refinement_list)):

            opts = refinement_list[i]
            
            if refinement_labels[i] == "SaveAdaptIterations" or refinement_labels[i] == "SaveAdaptMesh" or refinement_labels[i] == "Nonconformal":
                opts = str(opts).lower()

            if i == 0:
                current_string = '"' + refinement_labels[i] + '":' + str(opts) + ','
                
            elif i == len(refinement_list) - 1:
                current_string = '\n"' + refinement_labels[i] + '":' + str(opts)
                
            else:
                current_string = '\n"' + refinement_labels[i] + '":' + str(opts) + ','

            refinement_string = refinement_string + current_string

        if refinement_string == '':
            with open(self.filename, "a") as file:
                file.write('\n"Model": \n{\n "Mesh": ' + Mesh + ', \n "L0": ' + str(L0) + '\n},\n')
        else:
            with open(self.filename, "a") as file:
                file.write('\n"Model": \n{\n "Mesh": ' + Mesh + ', \n "L0": ' + str(L0) + ', \n "Refinement": \n{\n' + refinement_string + '\n}\n},\n')

    def add_Domains(self,Materials):
        total_Materials = ''
        for i in range(len(Materials)):
            if i == len(Materials) - 1:
                total_Materials = total_Materials + Materials[i] + "\n"
            else:
                total_Materials = total_Materials + Materials[i] + ",\n\n"

        full_Domain = '\n "Domains": {\n "Materials": [\n' + total_Materials + ']\n },'

        with open(self.filename, "a") as file:
            file.write(full_Domain)
    
    def add_Boundaries(self,BCs):

        BCs = np.array(BCs)
        
        total_BCs = '\nBoundaries:\n{'
        total_LumpedPort = '\nLumpedPort:\n[\n'
        total_PEC = '\nPEC:'
        total_Impedance = '\nImpedance:[\n'

        PEC_mask = BCs[:, 1] == 'PEC'
        LumpedPort_mask = BCs[:, 1] == 'LumpedPort'
        Impedance_mask = BCs[:, 1] == 'Impedance'

        PECs = BCs[PEC_mask]
        LumpedPorts = BCs[LumpedPort_mask]
        Impedances = BCs[Impedance_mask]

        if len(PECs) > 1:
            raise ValueError("Too many PEC boundary Conditions - Please aggregate your PECs into one condition")
        elif len(PECs) == 1:
            total_PEC = total_PEC + PECs[0][0] + '\n,'
        else:
            total_PEC = ''

        ## needs to be changed - should be defined similar to LumpedPort not like PEC ##
        if len(Impedances) > 1:
            raise ValueError("Too many Impedance boundary Conditions - Please aggregate your Impedances into one condition")
        elif len(Impedances) == 1:
            total_Impedance = total_Impedance + Impedances[0][0] + '\n],'
        else:
            total_Impedance = ''

        if len(LumpedPorts) != 0:
        
            for i in range(len(LumpedPorts)):
                if i == len(LumpedPorts) - 1:
                    total_LumpedPort = total_LumpedPort + LumpedPorts[i][0] + "\n]"
                else:
                    total_LumpedPort = total_LumpedPort + LumpedPorts[i][0] + ",\n\n"
        else:
            total_LumpedPort = ''

        total_BCs = total_BCs + total_PEC + total_Impedance + total_LumpedPort + '},'

        with open(self.filename, "a") as file:
            file.write(total_BCs)

    def add_Postprocessing(self,Postprocessing):
        
        Postprocessing = np.array(Postprocessing)

        total_Postprocessing = '\nPostprocessing:\n{'
        total_Dielectric = '\nDielectric:\n[\n'
        total_Energy = '\nEnergy:\n[\n'
        
        Dielectric_mask = Postprocessing[:, 1] == 'Dielectric'
        Energy_mask = Postprocessing[:, 1] == 'Energy'

        Dielectrics = Postprocessing[Dielectric_mask]
        Energys = Postprocessing[Energy_mask]

        ## compiling boundary dielectric postprocessing ###
        if len(Dielectrics) == 0:
            total_Dielectric = ''
        else:
            for i in range(len(Dielectrics)):
                if i == len(Dielectrics) - 1:
                    total_Dielectric = total_Dielectric + Dielectrics[i][0] + "\n]"
                else:
                    total_Dielectric = total_Dielectric + Dielectrics[i][0] + ",\n\n"
        
        ## compiling domain energy postprocessing ###
        if len(Energys) == 0:
            total_Energy = ''
        else:
            for i in range(len(Energys)):
                if i == len(Energys) - 1:
                    total_Energy = total_Energy + Energys[i][0] + "\n]"
                else:
                    total_Energy = total_Energy + Energys[i][0] + ",\n"

        total_Postprocessing = total_Postprocessing + total_Energy + total_Dielectric + '\n}'
        
        with open(self.filename, "a") as file:
            file.write(total_Postprocessing)

    def add_Solver(self,N,Eigenmode_tol,Target,Save,Type,Tol,KSPType,Order=1,Device='CPU',MaxIts=500):
        with open(self.filename, "a") as file:
            file.write(',\n{ \n "Solver": \n{\n "Order":' + str(Order) + ',\n"Device" :' + Device + ', \n"Eigenmode": {\n "N":' + str(N)
                       + ',\n"Tol": ' + str(Eigenmode_tol) + ',\n"Target": ' + str(Target) + ',\n"Save": ' + str(Save) + '\n}' + ', \n"Linear": {\n "Type":' + Type
                       + ',\n"KSPType": ' + KSPType + ',\n:Tol": ' + str(Tol) + ',\n"MaxIts": ' + str(MaxIts) +'\n}\n}\n')

    def publish_script(self):
        with open(self.filename, "a") as file:
            file.write('\n}')
    
    def print_script(self):
        with open(self.filename, 'r') as f:
            content = f.read()
            print(content)

    def valid_script(self):
        pass
