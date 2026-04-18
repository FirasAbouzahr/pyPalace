# Using pyPalace to execute AWS Palace simulations


The directories above walk you through how to use pyPalace to generate AWS Palace config files for various simulation types and example devices. Once we have a config object ready to go, we can also use pyPalace to actually run AWS Palace and execute a simulation, either locally or on a high-performance computer (HPC) with Slurm. This assumes MPI, Palace, and other dependencies are already added to your path, or in the case of an HPC, you've loaded all the proper modules in. 

We define the the path to palace-x86_64.bin and feed an instance of a Simulation object a Config instance.

```python
palace = "/path/to/palace_install/bin/palace-x86_64.bin"

my_sim = Simulation(your_config_object,palace) # create simulation object
```

To run AWS Palace on your local machine, call:

```python
my_sim.run(n = 10) # n = number of MPI processes
```

Or we can call the same .run() but with supplied HPC options to run on an HPC using the slurm manager:

```python
HPC_options = Simulation.HPC_options(
                                    partition="short", # #SBATCH --partition=short
                                    time="00:30:00", # #SBATCH --time=00:30:00
                                    nodes=1, # #SBATCH --nodes=1
                                    ntasks_per_node=32, # #SBATCH --ntasks-per-node=30
                                    mem=64, # #SBATCH --mem=64G
                                    job_name="test-job", # #SBATCH --job-name=test-job
                                    custom=["account=p#####"]) # custom directives you want to add to the job script, for example at my university we need to add account
                                
# executes sbatch
my_sim.run(n=30, # number of MPI processes,
           HPC_options=HPC_options # Slurm directives (e.g, request HPC resources)
           ) 
```
