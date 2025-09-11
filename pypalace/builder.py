def Material(Attributes,Permeability,Permittivity,LossTan):
    current_material_def = '{"Attributes": [' + ",".join(str(atts) for atts in Attributes) + '],\n"Permeability":' + str(Permeability) + ',\n"Permittivity":' + str(Permittivity) + ',\n"LossTan":' + str(LossTan) + '}'
    return current_material_def

def BoundaryCondition_PEC(Attributes):
    current_PEC_def = '{"Attributes": [' + ",".join(str(atts) for atts in Attributes) + ']}'
    return current_PEC_def,"PEC"

def BoundaryCondition_LumpedPort(Index,Attributes,Direction,R,L,C):
    current_LP_def = '{Index:' + str(Index) + ',\n"Attributes": [' + ",".join(str(atts) for atts in Attributes) + '],\n"Direction":' + Direction + ',\n"R":' + str(R) + ',\n"L":' + str(L) + ',\n"C":' + str(C) +'}'
    return current_LP_def,"LumpedPort"

def BoundaryCondition_Impedance(Attributes,Rs):
    current_Im_def = '{"Attributes": [' + ",".join(str(atts) for atts in Attributes) + '],\n"Rs":' + str(Rs) + '}'
    return current_Im_def,"Impedance"

def PostProcessing_Boundary_Dielectric(Index,Attributes,Type,Thickness,Permittivity,LossTan):
    current  = '{Index:' + str(Index) + ',\n"Attributes": [' + ",".join(str(atts) for atts in Attributes) + '],\n"Type":' + Type + ',\n"Thickness":' + str(Thickness) + ',\n"Permittivity":' + str(Permittivity) + ',\n"LossTan":' + str(LossTan) +'}'
    return current,"Dielectric"

def PostProcessing_Domain_Energy(Index,Attributes):
    current  = '{Index:' + str(Index) + ',\n"Attributes": [' + ",".join(str(atts) for atts in Attributes) + ']}'
    return current,"Energy"
