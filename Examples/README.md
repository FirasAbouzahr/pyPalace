# Using pyPalace to execute AWS Palace simulations


The directories above walk you through how to use pyPalace to generate AWS Palace config files for various simulation types and example devices. Once we have a config file ready to go, we can also use pyPalace to actually run AWS Palace and execute a simulation, either locally or on a high-performance computer (HPC) with Slurm. This assumes MPI, Palace, and other dependencies are already added to your path, or in the case of an HPC, you've loaded all the proper modules in. 

First we define our the paths to palace-x86_64.bin and the AWS Palace config file that we generated above. We also create an instance of the Simulation object.

```python
palace = "/path/to/palace_install/bin/palace-x86_64.bin"
config = "/path/to/example_config.json"

my_sim = Simulation(palace) # create simulation object
```

To run AWS Palace on your local machine, we next call:

```python
my_sim.run_palace(n = 32, # number of MPI processes
                  path_to_json=config # path to palace config file
                  )
```

Or we call the following to run AWS Palace on an HPC:

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
my_sim.run_palace_HPC(n=30, # number of MPI processes
                      config, # path to palace config file
                      HPC_options=HPC_options # Slurm directives (e.g, request HPC resources)
                      ) # execute sbatch
```
