import numpy as np

class Domains:
    
    def Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None):
        dict = {"Attributes":Attributes,
                "Permeability":Permeability,
                "Permittivity":Permittivity}
                
        material_list = np.array([LossTan,Conductivity,LondonDepth,MaterialAxes])
        material_labels = np.array(["LossTan","Conductivity","LondonDepth","MaterialAxes"])
        material_mask = material_list[:,] == None
        
        material_list = material_list[~material_mask]
        material_labels = material_labels[~material_mask]
        
        for i in range(len(material_list)):
            dict[material_labels[i]] = material_list[i]

        return dict

    def Postprocessing_Energy(Index,Attributes):
        dict  = {"Index":Index,
                 "Attributes":Attributes}
        
        return dict,"Energy"
        
    def Postprocessing_Probe(Index,Center):
        dict  = {"Index":Index,
                 "Center":Attributes}
        
        return dict,"Probe"

class Boundaries:
    
    def PEC(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"PEC"
    
    def PMC(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"PMC"
        
    def Absorbing(Attributes,Order):
        dict = {"Attributes":Attributes,
                "Order":Order}
        return dict,"Absorbing"
        
    def Conductivity(Attributes,Conductivity,Permeability,Thickness=None):
    
        dict = {"Attributes":Attributes,
                "Conductivity":Conductivity,
                "Permeability":Permeability}
        
        if Thickness != None:
            dict["Thickness"] = Thickness
        
        return dict,"Conductivity"
        
    def Ground(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"Ground"
    

    def LumpedPort(Index,Attributes,Direction,R,L,C):
        dict = {"Index":Index,
                "Attributes":Attributes,
                "Direction":Direction,
                "R":R,
                "L":L,
                "C":C}
        
        return dict,"LumpedPort"

    def Impedance(Attributes,Rs=None,Ls=None,Cs=None):

        dict = {"Attributes":Attributes}

        impedance_list = np.array([Rs,Ls,Cs])
        impedance_labels = np.array(["Rs","Ls","Cs"])
        impedance_mask = impedance_list[:,] == None

        impedance_list = impedance_list[~impedance_mask]
        impedance_labels = impedance_labels[~impedance_mask]

        for i in range(len(impedance_list)):
            dict[impedance_labels[i]] = impedance_list[i]

        return dict,"Impedance"

    def Postprocessing_Dielectric(Index,Attributes,Type,Thickness,Permittivity,LossTan):
        dict = {"Index":Index,
                "Attributes":Attributes,
                "Type":Type,
                "Thickness":Thickness,
                "Permittivity":Permittivity,
                "LossTan":LossTan}

        return dict,"Dielectric"

class Solver:
    def Eigenmode(Target=None,Tol=None,MaxIts=None,MaxSize=None,N=1,Save=1,Type="Default"):

        eigenmode_dict = {"N":N,
                          "Save":Save,
                          "Type":Type}
    
        eigenmode_list = np.array([Target,Tol,MaxIts,MaxSize])
        eigenmode_labels = np.array(["Target","Tol","MaxIts","MaxSize"])
        eigenmode_mask = eigenmode_list[:,] == None

        eigenmode_list = eigenmode_list[~eigenmode_mask]
        eigenmode_labels = eigenmode_labels[~eigenmode_mask]

        for i in range(len(eigenmode_list)):
            eigenmode_dict[eigenmode_labels[i]] = eigenmode_list[i]

        return eigenmode_dict,"Eigenmode"

    def Linear(Type="Default",KSPType="Default",Tol=None,MaxIts=None,MaxSize=None):

        Linear_dict = {"Type":Type,
                       "KSPType": KSPType}

        Linear_list = np.array([Tol,MaxIts,MaxSize])
        Linear_labels = np.array(["Tol","MaxIts","MaxSize"])
        Linear_mask = Linear_list[:,] == None

        Linear_list = Linear_list[~Linear_mask]
        Linear_labels = Linear_labels[~Linear_mask]

        for i in range(len(Linear_list)):
            Linear_dict[Linear_labels[i]] = Linear_list[i]
        
        return Linear_dict
        
