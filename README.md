# pyPalace

Definitions of function parameters come straight from [AWS Palace](https://awslabs.github.io/palace/stable/). So I won't go over specifics of parameters here in too much details. Some functions are still missing and or incomplete (e.g., Lumped Port does not yet take Rs,Ls,Cs values).

## pyPalace.builder

builder functions are used to define blocks that go into the 5 main components of a Palace configuration file: config["Problem"],config["Model"],config["Domains"],config["Boundaries"],config["Solver"]

Any parameters in the builder functions which have **None** as their default values will not be included in the config file and hence will revert to their default values set by Palace unless specificed expliticly in the function calls. See the example below.

### pyPalace.builder.Domains

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Domains (see below).

#### Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None) 
*Attributes*: Array/list
*Permeability*: float
*Permittivity*: float
*LossTan*: float
*Conductivity*: float
*LondonDepth*: float
*MaterialAxes*: array/list

* Defines the material properities to be assigned to volume blocks/domains from your mesh file.
* Not optional

#### Postprocessing_Energy(Index,Attributes):
* Computes the electric and magnetic field energies in the specific domain attributes.
* Optional

#### Postprocessing_Probe(Index,Center):
* Computes the electric and magnetic flux density
* Optional

### pyPalace.builder.Boundaries

#### PEC(Attributes)
* Defines which surface blocks/domains should have perfect electric conductor boundary conditions
* This instance should only be defined once - so put all your 

    
    def PMC(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"PMC"
        
    def Absorbing(Attributes,Order):
        dict = {"Attributes":Attributes,
                "Order":Order}
        return dict,"Absorbing"
        
    def Conductivity(Attributes,Conductivity,Permeability,Thickness=None)
    
        dict = {"Attributes":Attributes,
                "Conductivity":Conductivity,
                "Permeability":Permeability}
        
        if Thickness != None:
            dict["Thickness"] = Thickness
        
        return dict,"Conductivity"
        
    def Ground(Attributes):
        dict = {"Attributes":Attributes}
        return dict,"Ground"
    

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Boundaries (see below).


