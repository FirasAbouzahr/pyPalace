"""
Helper utilities for constructing AWS Palace configuration dictionaries.

This module provides builder-style functions that mirror the structure of the
AWS Palace input file (e.g., Model, Domains, Boundaries, Solver). These
functions return dictionaries formatted for use with
:class:`pypalace.config.Config`.
"""

import numpy as np


class Model:

    """
    Helper functions for generating ``config["Model"]`` arguments
    for use with :meth:`pypalace.config.Config.add_Model`.

    These functions mirror AWS Palace model and mesh-refinement settings
    and return dictionaries formatted for the Palace configuration file.

    See the `AWS Palace Model documentation <https://awslabs.github.io/palace/stable/config/model/>`_
    for full details on model and refinement options.
    """
    
    @staticmethod
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
    
    @staticmethod
    def Refinement_Boxes(Levels,BoundingBoxMin,BoundingBoxMax):
        return {"Levels":Levels,"BoundingBoxMin":BoundingBoxMin,"BoundingBoxMax":BoundingBoxMax}
    
    @staticmethod
    def Refinement_Spheres(Levels,Center,Radius):
        return {"Levels":Levels,"Center":Center,"Radius":Radius}

class Domains:

    """
    Helper functions for generating ``config["Domains"]`` arguments
    for use with :meth:`pypalace.config.Config.add_Domains`.

    These functions mirror AWS Palace domain, material, and domain-level
    postprocessing definitions and return dictionaries formatted for the
    Palace configuration file.

    See the `AWS Palace Domains documentation <https://awslabs.github.io/palace/stable/config/domains/>`_
    for full details on materials and domain postprocessing.
    """
    
    @staticmethod
    def Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None):
        dict = {"Attributes":Attributes,
                "Permeability":Permeability,
                "Permittivity":Permittivity}
                
        material_list = [LossTan,Conductivity,LondonDepth,MaterialAxes]
        material_labels = ["LossTan","Conductivity","LondonDepth","MaterialAxes"]
        new_material_list = []
        new_material_labels = []
        
        for i,j in zip(material_list,material_labels): # silly numpy made me hardcode this
            if i == None:
                pass
            else:
                dict[j] = i

        return dict
        
    @staticmethod
    def Postprocessing_Energy(Index,Attributes):
        dict  = {"Index":Index,
                 "Attributes":Attributes}
        
        return dict,"Energy"
    
    @staticmethod
    def Postprocessing_Probe(Index,Center):
        dict  = {"Index":Index,
                 "Center":Center}
        
        return dict,"Probe"

class Boundaries:

    """
    Helper functions for generating ``config["Boundaries"]`` arguments
    for use with :meth:`pypalace.config.Config.add_Boundaries`.

    These functions mirror AWS Palace boundary-condition and boundary-level
    postprocessing definitions and return dictionaries formatted for the
    Palace configuration file.

    See the `AWS Palace Boundaries documentation <https://awslabs.github.io/palace/stable/config/boundaries/>`_
    for the boundary types and postprocessing options that match the current **stable**
    Palace release. If you build Palace from a newer **development** tree, additional
    ``config["Boundaries"]["Postprocessing"]`` keys may exist there before they appear on
    the stable site; for example ``Impedance`` and ``Voltage`` mode postprocessing are
    described in `Palace main branch boundaries.md <https://github.com/awslabs/palace/blob/main/docs/src/config/boundaries.md>`_.

    Note that ``Boundaries.Impedance`` builds the **surface impedance boundary condition**
    (top-level ``"Impedance"`` array under ``Boundaries``), while
    ``Boundaries.Postprocessing_Impedance`` builds an entry for **postprocessing** mode
    impedance (nested under ``"Postprocessing"``); the JSON key name is the same, but the
    object shape and meaning differ.
    """

    @staticmethod
    def PEC(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"PEC"
        
    @staticmethod
    def PMC(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"PMC"
        
    @staticmethod
    def Absorbing(Attributes,Order):
        dict = {"Attributes":Attributes,
                "Order":Order}
        return dict,"Absorbing"
        
    @staticmethod
    def Conductivity(Attributes,Conductivity,Permeability,Thickness=None):
    
        dict = {"Attributes":Attributes,
                "Conductivity":Conductivity,
                "Permeability":Permeability}
        
        if Thickness != None:
            dict["Thickness"] = Thickness
        
        return dict,"Conductivity"
        
    @staticmethod
    def Ground(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"Ground"

    @staticmethod
    def ZeroCharge(Attributes):
        dict = {"Attributes": Attributes}
        return dict,"ZeroCharge"

    @staticmethod
    def Terminal(Index,Attributes):
        dict = {"Index":Index,"Attributes":Attributes}
        return dict,"Terminal"
        
    @staticmethod
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
    
    @staticmethod
    def Elements(Attributes,Direction,CoordinateSystem):
        return {"Attributes":Attributes,"Direction":Direction,"CoordinateSystem":CoordinateSystem}
    
    @staticmethod
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

    @staticmethod
    def WavePortPEC(Attributes):
        dict = {"Attributes": Attributes}
        return dict,"WavePortPEC"

    @staticmethod
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
    
    ## need to fix syntax to match lumped port ##
    @staticmethod
    def SurfaceCurrent(Index,Attributes,Direction,CoordinateSystem=None,Elements=None):
        dict = {"Index":Index,
                "Attributes":Attributes,
                "Direction":Direction}
                
        if Elements != None:
            dict = {"Index":Index,
            "Attributes":Attributes,
            "Elements":Elements}
            
        if CoordinateSystem != None:
            dict["CoordinateSystem"] = CoordinateSystem
        
        return dict,"SurfaceCurrent"

    @staticmethod
    def Periodic_BoundaryPair(DonorAttributes, ReceiverAttributes, Translation=None, AffineTransformation=None):
        pair_dict = {"DonorAttributes": DonorAttributes, "ReceiverAttributes": ReceiverAttributes}
        if Translation != None:
            pair_dict["Translation"] = Translation
        if AffineTransformation != None:
            pair_dict["AffineTransformation"] = AffineTransformation
        return pair_dict

    @staticmethod
    def Periodic(FloquetWaveVector=None, BoundaryPairs=None):
        periodic_dict = {}
        if FloquetWaveVector != None:
            periodic_dict["FloquetWaveVector"] = FloquetWaveVector
        if BoundaryPairs != None:
            periodic_dict["BoundaryPairs"] = list(BoundaryPairs)
        return periodic_dict, "Periodic"

    @staticmethod
    def Postprocessing_Dielectric(Index,Attributes,Type,Thickness,Permittivity,LossTan):
        dict = {"Index":Index,
                "Attributes":Attributes,
                "Type":Type,
                "Thickness":Thickness,
                "Permittivity":Permittivity,
                "LossTan":LossTan}

        return dict,"Dielectric"
        
    @staticmethod
    def Postprocessing_SurfaceFlux(Index,Attributes,Type,TwoSided=False,Center=None):
        dict = {"Index":Index,
                "Attributes":Attributes,
                "Type":Type}
                
        if TwoSided == True:
            dict["TwoSided"] = str(TwoSided)
        
        elif Center != None:
            dict["TwoSided"] = Center

        return dict,"SurfaceFlux"

    @staticmethod
    def Postprocessing_Impedance(Index,VoltageAttributes=None,CurrentAttributes=None,VoltagePath=None,CurrentPath=None,NSamples=None):
        dict = {"Index":Index}
        if VoltageAttributes != None:
            dict["VoltageAttributes"] = VoltageAttributes
        if CurrentAttributes != None:
            dict["CurrentAttributes"] = CurrentAttributes
        if VoltagePath != None:
            dict["VoltagePath"] = VoltagePath
        if CurrentPath != None:
            dict["CurrentPath"] = CurrentPath
        if NSamples != None:
            dict["NSamples"] = NSamples
        return dict,"Impedance"

    @staticmethod
    def Postprocessing_Voltage(Index,VoltageAttributes=None,VoltagePath=None,NSamples=None):
        dict = {"Index":Index}
        if VoltageAttributes != None:
            dict["VoltageAttributes"] = VoltageAttributes
        if VoltagePath != None:
            dict["VoltagePath"] = VoltagePath
        if NSamples != None:
            dict["NSamples"] = NSamples
        return dict,"Voltage"

    @staticmethod
    def Postprocessing_FarField(Attributes,NSample=None,ThetaPhis=None):
        dict = {"Attributes":Attributes}
        if NSample != None:
            dict["NSample"] = NSample
        if ThetaPhis != None:
            dict["ThetaPhis"] = ThetaPhis
        return dict,"FarField"

class Solver:

    """
    Helper functions for generating ``config["Solver"]`` arguments
    for use with :meth:`pypalace.config.Config.add_Solver`.

    These functions mirror AWS Palace solver configurations for electrostatic,
    magnetostatic, eigenmode, driven, transient, boundary mode, and linear simulations.

    See the `AWS Palace Solver documentation <https://awslabs.github.io/palace/stable/config/solver/>`_
    for full details on solver options.
    """
    
    @staticmethod
    def Electrostatic(Save):
        return {"Save":Save},"Electrostatic"
        
    @staticmethod
    def Magnetostatic(Save):
        return {"Save":Save},"Magnetostatic"
        
    @staticmethod
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

    @staticmethod
    def BoundaryMode(Freq=None,N=1,Save=0,Target=0.0,Tol=None,MaxSize=None,Type="Default",Attributes=None):

        boundarymode_dict = {"N":N,
                              "Save":Save,
                              "Type":Type}

        boundarymode_list = np.array([Freq,Target,Tol,MaxSize])
        boundarymode_labels = np.array(["Freq","Target","Tol","MaxSize"])
        boundarymode_mask = boundarymode_list[:,] == None

        boundarymode_list = boundarymode_list[~boundarymode_mask]
        boundarymode_labels = boundarymode_labels[~boundarymode_mask]

        for i in range(len(boundarymode_list)):
            boundarymode_dict[boundarymode_labels[i]] = boundarymode_list[i]

        if Attributes != None:
            boundarymode_dict["Attributes"] = Attributes

        return boundarymode_dict,"BoundaryMode"
        
    @staticmethod
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
        
    @staticmethod
    def Driven_Samples(Type=None,MinFreq=None,MaxFreq=None,FreqStep=None,NSample=None,Freq=None,SaveStep=None,AddToPROM=None):
        
        samples_dict = {}
        
        samples_list = np.array([Type,MinFreq,MaxFreq,FreqStep,NSample,Freq,SaveStep,AddToPROM])
        samples_labels = np.array(["Type","MinFreq","MaxFreq","FreqStep","NSample","Freq","SaveStep","AddToPROM"])
        samples_mask = samples_list[:,] == None
        
        samples_list = samples_list[~samples_mask]
        samples_labels = samples_labels[~samples_mask]

        for i in range(len(samples_list)):
            samples_dict[samples_labels[i]] = samples_list[i]
        
        return samples_dict
        
    @staticmethod
    def Transient(Type=None,Excitation=None,ExcitationFreq=None,ExcitationWidth=None,MaxTime=None,TimeStep=None,SaveStep=None,Order=None,RelTol=None,AbsTol=None):
        
        TD_dict = {}
        
        TD_list = np.array([Type,Excitation,ExcitationFreq,ExcitationWidth,MaxTime,TimeStep,SaveStep,Order,RelTol,AbsTol])
        TD_labels = np.array(["Type","Excitation","ExcitationFreq","ExcitationWidth","MaxTime","TimeStep","SaveStep","Order","RelTol","AbsTol"])
        TD_mask = TD_list[:,] == None
        
        TD_list = TD_list[~TD_mask]
        TD_labels = TD_labels[~TD_mask]

        for i in range(len(TD_list)):
            TD_dict[TD_labels[i]] = TD_list[i]

        return TD_dict,"Transient"
        
    @staticmethod
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
        
