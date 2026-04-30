import pandas as pd
import numpy as np
import scqubits as scq
from scipy.constants import e,hbar,h,pi
phi0 = 2.0678338484619295e-15

class EPR:

    ## from https://arxiv.org/pdf/2010.00620 (equation 9)
    def calculate_anharmonicity(p_q,f_q,LJ): # f_q in GHz (default of Palace), Ej in Joules, Lj in Henries

        EJ = phi0**2/((2*pi)**2*LJ)

        w_q = 2 * np.pi * f_q * 10**9
        alpha_q = p_q**2 * (hbar * w_q**2)/(8 * EJ) # calculate alpha
        alpha_q = (alpha_q / (2*pi))
        
        return -alpha_q
    
    ## from https://arxiv.org/pdf/2010.00620 (equation 11)
    def calculate_dispersive_shift(p_q,p_r,f_q,f_r,LJ): # unitless, unitless, GHz, GHz, Henries
        

        EJ = phi0**2/((2*pi)**2*LJ)

        w_q = 2 * pi * f_q * 10**9
        w_r = 2 * pi * f_r * 10**9

        chi = p_q * p_r * (hbar * w_q * w_r) / (4 * EJ) # calculate chi
        chi = (chi / (2*pi))
 
        return -chi
    
    ## from https://arxiv.org/pdf/2010.00620
    def calculate_lamb_shift(alpha_q,chi):
        return alpha_q - chi/2
    
    ## from https://arxiv.org/pdf/2312.13483 (equation 9)
    def calculate_coupling_strength(f_q,f_r,alpha_q,chi):
        delta = (f_r - f_q) * 10**9
        sigma = (f_q + f_r) * 10**9
        denom = alpha_q/(delta *(delta - alpha_q)) + alpha_q/(sigma*(sigma + alpha_q))
        g = np.sqrt(chi/denom/2)
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
        
        
#class DrivenAnalysis:
#
#    def get_scatter_column
