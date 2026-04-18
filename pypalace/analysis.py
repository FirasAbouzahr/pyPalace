import pandas as pd
import numpy as np
import scqubits as scq
from scipy.constants import e,hbar,h,pi
phi0 = 2.0678338484619295e-15

class EPR:

    ## from https://arxiv.org/pdf/2010.00620 (equation 9)
    def calculate_anharmonicity(p_q,f_q,Ej = None,Lj = None): # f_q in GHz (default of Palace), Ej in Joules, Lj in Henries

        if Ej == None and Lj == None:
            raise ValueError("Please enter a value for either Ej or Lj")
        elif Ej != None and Lj != None:
            print("Both Ej and Lj defined, defaulting to calculation using Ej")
        elif Ej == None and Lj != None:
            Ej = phi0**2/((2*pi)**2*Lj)

        w_q = 2 * np.pi * f_q * 10**9
        alpha_q = p_q**2 * (hbar * w_q**2)/(8 * Ej) # calculate alpha
        alpha_q = (alpha_q / (2*pi)) * 10**-6 # convert to MHz
        
        return -alpha_q
    
    ## from https://arxiv.org/pdf/2010.00620 (equation 11)
    def calculate_dispersive_shift(p_q,p_r,f_q,f_r,Ej = None,Lj = None):
        
        if Ej == None and Lj == None:
            raise ValueError("Please enter a value for either Ej or Lj")
        elif Ej != None and Lj != None:
            print("Both Ej and Lj defined, defaulting to calculation using Ej")
        elif Ej == None and Lj != None:
            Ej = phi0**2/((2*pi)**2*Lj)

        w_q = 2 * pi * f_q * 10**9
        w_r = 2 * pi * f_r * 10**9

        chi = p_q * p_r * (hbar * w_q * w_r) / (4 * Ej) # calculate chi
        chi = (chi / (2*pi)) * 10**-6 # convert to MHz
 
        return -chi
    
    ## from https://arxiv.org/pdf/2010.00620
    def calculate_lamb_shift(alpha_q,chi):
        return alpha_q - chi/2
    
    ## from https://arxiv.org/pdf/2312.13483 (equation 9)
    def calculate_coupling_strength(f_q,f_r,alpha_q,chi):
        delta = (f_r - f_q)*1000
        sigma = (f_q + f_r)*1000
        denom = alpha_q/(delta *(delta - alpha_q)) + alpha_q/(sigma*(sigma + alpha_q))
        g = np.sqrt(chi/denom/2)
        return g

    def calculate_lamb_shift(alpha_q,chi):
        return alpha_q - chi/2

    def get_anharmonicity(self,qubit_mode,JJ_LumpedPort_index):
        
        with open(self.path_to_json, "r") as f:
            this_config = json.load(f)
        
        output_folder = this_config["Problem"]["Output"]

        # extract the JJ's indunctance (Lj) from config file based on LumpedPort index given
        for lp in this_config["Boundaries"]["LumpedPort"]:
            if lp["Index"] == JJ_LumpedPort_index:
                Lj = lp["L"]

        # convert to Ej
        Ej = phi0**2/((2*np.pi)**2*Lj)

        eigenvals = pd.read_csv(output_folder + "/eig.csv",usecols = [0,1])
        eigenvals.columns = ["m","f"]
        EPR = pd.read_csv(output_folder + "/port-EPR.csv")
        EPR.columns = ["m","p"]

        f_q = eigenvals[eigenvals.m == qubit_mode].f.iloc[0]
        p_q = EPR[EPR.m == qubit_mode].p.iloc[0]

        alpha_q = Simulation.calculate_anharmonicity(p_q,f_q,Ej)

        return alpha_q

    def get_dispersive_shift(self,qubit_mode,resonator_mode,JJ_LumpedPort_index):
        
        with open(self.path_to_json, "r") as f:
            this_config = json.load(f)
        
        output_folder = this_config["Problem"]["Output"]

        # extract the JJ's indunctance (Lj) from config file based on LumpedPort index given
        for lp in this_config["Boundaries"]["LumpedPort"]:
            if lp["Index"] == JJ_LumpedPort_index:
                Lj = lp["L"]

        # convert to Ej
        Ej = phi0**2/((2*np.pi)**2*Lj)

        eigenvals = pd.read_csv(output_folder + "/eig.csv",usecols = [0,1])
        eigenvals.columns = ["m","f"]
        EPR = pd.read_csv(output_folder + "/port-EPR.csv")
        EPR.columns = ["m","p"]

        f_q = eigenvals[eigenvals.m == qubit_mode].f.iloc[0]
        f_r = eigenvals[eigenvals.m == resonator_mode].f.iloc[0]
        p_q = EPR[EPR.m == qubit_mode].p.iloc[0]
        p_r = EPR[EPR.m == resonator_mode].p.iloc[0]

        chi = Simulation.calculate_dispersive_shift(p_q,p_r,f_q,f_r,Ej)

        return chi

    def get_lamb_shift(self,alpha_q,chi):
        return Simulation.calculate_lamb_shift(alpha_q,chi)

    def get_coupling_strength(self,qubit_mode,resonator_mode,JJ_LumpedPort_index):
        
        with open(self.path_to_json, "r") as f:
            this_config = json.load(f)
        
        output_folder = this_config["Problem"]["Output"]

        # extract the JJ's indunctance (Lj) from config file based on LumpedPort index given
        for lp in this_config["Boundaries"]["LumpedPort"]:
            if lp["Index"] == JJ_LumpedPort_index:
                Lj = lp["L"]

        # convert to Ej
        Ej = phi0**2/((2*np.pi)**2*Lj)

        eigenvals = pd.read_csv(output_folder + "/eig.csv",usecols = [0,1])
        eigenvals.columns = ["m","f"]
        EPR = pd.read_csv(output_folder + "/port-EPR.csv")
        EPR.columns = ["m","p"]

        f_q = eigenvals[eigenvals.m == qubit_mode].f.iloc[0]
        f_r = eigenvals[eigenvals.m == resonator_mode].f.iloc[0]
        p_q = EPR[EPR.m == qubit_mode].p.iloc[0]
        p_r = EPR[EPR.m == resonator_mode].p.iloc[0]

        alpha_q = Simulation.calculate_anharmonicity(p_q,f_q,Ej)
        chi = Simulation.calculate_dispersive_shift(p_q,p_r,f_q,f_r,Ej)
        g = Simulation.calculate_coupling_strength(f_q,f_r,alpha_q,chi)
        return g
        
class LOM:
    def get_Hamiltonian_parameters(C_Sigma,LJ):
    
        EJ = phi0**2/((2*np.pi)**2*LJ) / h * 1e-6 # in MHz
        EC = e**2/(2*C_Sigma) / h * 1e-6 # in MHz
        
        qubit = scq.Transmon(EJ=EJ,
                        EC=EC,
                        ng=0,
                        ncut=31)
                        
        f_q = qubit.E01() / 1000 # in GHz
        alpha = qubit.anharmonicity() # in MHz
        
        return {"frequency_GHz":f_q,"anharmonicity_MHz":alpha}

#class flux:
#    
#    def
