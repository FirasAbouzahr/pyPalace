import numpy as np


class Model:

    def Refinement(Tol=None,MaxIts=None,MaxSize=None,Nonconformal=None,UpdateFraction=None,UniformLevels=None,Boxes=None,Spheres=None,SaveAdaptMesh=None,SaveAdaptIterations=None):
        
        refinement_list = np.array([Tol,MaxIts,MaxSize,Nonconformal,UpdateFraction,UniformLevels,Boxes,Spheres,SaveAdaptMesh,SaveAdaptIterations])
        refinement_labels = np.array(["Tol","MaxIts","MaxSize","Nonconformal","UpdateFraction","UniformLevels","Boxes","Spheres","SaveAdaptMesh","SaveAdaptIterations"])
        refinement_mask = refinement_list[:,] == None

        refinement_list = refinement_list[~refinement_mask]
        refinement_labels = refinement_labels[~refinement_mask]

        refinement_dict = {}
        
        for i in range(len(refinement_list)):
            refinement_dict[refinement_labels[i]] = refinement_list[i]
        
        return refinement_dict
    
    def Refinement_Boxes(Levels,BoundingBoxMin,BoundingBoxMax):
        return {"Levels":Levels,"BoundingBoxMin":BoundingBoxMin,"BoundingBoxMax":BoundingBoxMax}
    
    def Refinement_Spheres(Levels,Center,Radius):
        return {"Levels":Levels,"Center":Center,"Radius":Radius}

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
    

    def LumpedPort(Index,Attributes,Direction=None,CoordinateSystem=None,Excitation=None,Active=None,R=None,L=None,C=None,Rs=None,Ls=None,Cs=None,Elements=None):
    
        dict = {"Index":Index,
                "Attributes":Attributes}
                
        if (R != None or L != None or C != None) and (Rs != None or Ls != None or Cs != None):
            raise ValueError("Cannot combine both circuit (R,L,C) and surface (Rs,Ls,Cs) parameters")
            
        if Direction != None and Elements != None:
            raise ValueError("Cannot use both Direction and Elements")

        LP_list = np.array([Direction,CoordinateSystem,Excitation,Active,R,L,C,Rs,Ls,Cs,Elements])
        LP_labels = np.array(["Direction","CoordinateSystem","Excitation","Active","R","L","C","Rs","Ls","Cs","Elements"])
        LP_mask = LP_list[:,] == None

        LP_list = LP_list[~LP_mask]
        LP_labels = LP_labels[~LP_mask]

        for i in range(len(LP_list)):
            dict[LP_labels[i]] = LP_list[i]

        return dict,"LumpedPort"
        
    def LumpedPort_Elements(Attributes,Direction,CoordinateSystem):
        return {"Attributes":Attributes,"Direction":Direction,"CoordinateSystem":CoordinateSystem}
        
    def WavePort(Index,Attributes,Excitation=None,Active=None,Mode=None,Offset=None,SolverType=None,MaxIts=None,KSPTol=None,EigenTol=None,Verbose=None):
        dict = {"Index":Index,
                "Attributes":Attributes}

        WP_list = np.array([Excitation,Active,Mode,Offset,SolverType,MaxIts,KSPTol,EigenTol,Verbose])
        WP_labels = np.array(["Excitation","Active","Mode","Offset","SolverType","MaxIts","KSPTol","EigenTol","Verbose"])
        WP_mask = WP_list[:,] == None

        WP_list = WP_list[~WP_mask]
        WP_labels = WP_labels[~WP_mask]

        for i in range(len(WP_list)):
            dict[WP_labels[i]] = WP_list[i]

        return dict,"WavePort"
    
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
    
    def Electrostatic(N):
        return {"N":N}
    
    def Magnetostatic(N):
        return {"N":N}

    def Eigenmode(Target,Tol=None,MaxIts=None,MaxSize=None,N=1,Save=1,Type="Default"):

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
        
    
    def Driven(MinFreq=None,MaxFreq=None,FreqStep=None,SaveStep=None,Samples=None,Save=None,Restart=None,AdaptiveTol=None,AdaptiveMaxSamples=None,AdaptiveConvergenceMemory=None):
        
        driven_dict = {}
        
        if AdaptiveTol == None and (Restart != None or AdaptiveMaxSamples != None or AdaptiveConvergenceMemory != None):
            print("AdaptiveTol not set, ignoring adaptive frequency sweep")
            AdaptiveTol,Restart,AdaptiveMaxSamples,AdaptiveConvergenceMemory = None,None,None,None
        
    
        driven_list = np.array([MinFreq,MaxFreq,FreqStep,SaveStep,Samples,Save,Restart,AdaptiveTol,AdaptiveMaxSamples,AdaptiveConvergenceMemory])
        driven_labels = np.array(["MinFreq","MaxFreq","FreqStep","SaveStep","Samples","Save","Restart","AdaptiveTol","AdaptiveMaxSamples","AdaptiveConvergenceMemory"])
        driven_mask = driven_list[:,] == None
        
        driven_list = driven_list[~driven_mask]
        driven_labels = driven_labels[~driven_mask]

        for i in range(len(driven_list)):
            driven_dict[driven_labels[i]] = driven_list[i]

        return driven_dict,"Driven"
    
    def Driven_Samples(Type=None,MinFreq=None,MaxFreq=None,FreqStep=None,NSample=None,Freq=None,SaveStep=None,AddtoPROM=None):
        
        samples_dict = {}
        
        samples_list = np.array([Type,MinFreq,MaxFreq,FreqStep,NSample,Freq,SaveStep,AddtoPROM])
        samples_labels = np.array(["Type","MinFreq","MaxFreq","FreqStep","NSample","Freq","SaveStep","AddtoPROM"])
        samples_mask = samples_list[:,] == None
        
        samples_list = samples_list[~samples_mask]
        samples_labels = samples_labels[~samples_mask]

        for i in range(len(samples_list)):
            samples_dict[samples_labels[i]] = samples_list[i]
        
        return samples_dict
        

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
        
