# pyPalace

Definitions of function parameters come straight from [AWS Palace](https://awslabs.github.io/palace/stable/). So I won't go over specifics of parameters here in too much details. Some functions are still missing and or incomplete (e.g., Lumped Port does not yet take Rs,Ls,Cs values).

## pyPalace.builder

builder functions are used to define blocks that go into the 5 main components of a Palace configuration file: config["Problem"],config["Model"],config["Domains"],config["Boundaries"],config["Solver"]

Any parameters in the builder functions which have **None** as their default values will not be included in the config file and hence will revert to their default values set by Palace unless specificed expliticly in the function calls. See the example below.

### pyPalace.builder.Domains

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Domains (see below).

#### Material(Attributes,Permeability,Permittivity,LossTan=None,Conductivity=None,LondonDepth=None,MaterialAxes=None) 

Defines the material properities to be assigned to volume blocks/domains from your mesh file. See [domains["Materials"]](https://awslabs.github.io/palace/stable/config/domains/#domains[%22Materials%22])

* *Attributes*: Array/list 
* *Permeability*: float 
* *Permittivity*: float 
* *LossTan*: float 
* *Conductivity*: float 
* *LondonDepth*: float 
* *MaterialAxes*: array/list 

#### Postprocessing_Energy(Index,Attributes):

Computes the electric and magnetic field energies in the specific domain attributes.

* *Index*: integer
* *Attributes*: Array/list 

#### Postprocessing_Probe(Index,Center):
Computes the electric and magnetic flux density

* *Index*: integer
* *Center*: array/list

### pyPalace.builder.Boundaries

All these functions, once or if used, will eventually be entered as paramters in pyPalace.Config.add_Boundaries (see below).

#### PEC(Attributes)
Defines which surface blocks/domains will have a perfect electric conductor boundary condition.

* *Attributes*: Array/list 

#### PMC(Attributes)
Defines which surface blocks/domains will have a perfect magnetic conductor boundary condition.

* *Attributes*: Array/list

#### Absorbing(Attributes,Order):
Defines which surface blocks/domains will have an absorbing boundary condition.

* *Attributes*: Array/list
* *Order*: integer
        
#### Conductivity(Attributes,Conductivity,Permeability,Thickness=None)
Defines which surface blocks/domains will have a conducting boundary condition.

* *Attributes*: Array/list
* *Conductivity*: float
* *Permeability*: float
* *Thickness*: float
           
#### Ground(Attributes)
Defines which surface blocks/domains will have a grounded boundary condition.

* *Attributes*: Array/list

#### LumpedPort(Index,Attributes,Direction,R,L,C) 
Defines which surface blocks/domains will have a lumped port boundary condition.

* *Index*: integer
* *Attributes*: Array/list
* *Direction*: string or array/list
* *R*: float
* *L*: float
* *C*: float


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
    

