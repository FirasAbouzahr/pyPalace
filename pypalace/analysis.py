"""
Quantum analysis utilities for extracting qubit parameters from
electromagnetic simulation results.

This module provides tools for computing quantities such as anharmonicity,
dispersive shifts, coupling strengths, and Hamiltonian parameters using
methods based on energy participation ratios (EPR) and lumped oscillator
models (LOM).
"""


import pandas as pd
import numpy as np
import scqubits as scq
from scipy.constants import e,hbar,h,pi
phi0 = 2.0678338484619295e-15

class EPR:

    """
    Utilities for computing qubit parameters using the energy participation
    ratio (EPR) formalism.

    These methods implement standard relations between electromagnetic
    simulation outputs and circuit Hamiltonian parameters.
    """

    ## from https://arxiv.org/pdf/2010.00620 (equation 9)
    @staticmethod
    def calculate_anharmonicity(p_q,f_q,LJ): # f_q in GHz (default of Palace), Ej in Joules, Lj in Henries
        
        """
        Compute the qubit anharmonicity from the EPR method.

        Parameters
        ----------
        p_q : float
            Qubit energy participation ratio (unitless).
        f_q : float
            Qubit frequency in GHz.
        LJ : float
            Josephson inductance in Henries.

        Returns
        -------
        float
            Qubit anharmonicity in Hz (negative for transmons).

        Notes
        -----
        Based on Eq. (9) of https://arxiv.org/pdf/2010.00620.
        """

        EJ = phi0**2/((2*pi)**2*LJ)

        w_q = 2 * np.pi * f_q * 10**9
        alpha_q = p_q**2 * (hbar * w_q**2)/(8 * EJ) # calculate alpha
        alpha_q = (alpha_q / (2*pi))
        
        return -alpha_q
        
    @staticmethod
    def calculate_dispersive_shift(p_q, p_r, f_q, f_r, LJ):
    
        """
        Compute the dispersive shift (chi) between a qubit and resonator from the EPR method.

        Parameters
        ----------
        p_q : float
            Qubit participation ratio (unitless).
        p_r : float
            Resonator participation ratio (unitless).
        f_q : float
            Qubit frequency in GHz.
        f_r : float
            Resonator frequency in GHz.
        LJ : float
            Josephson inductance in Henries.

        Returns
        -------
        float
            Dispersive shift (chi) in Hz.

        Notes
        -----
        Based on Eq. (11) of https://arxiv.org/pdf/2010.00620.
        """
    
    ## from https://arxiv.org/pdf/2010.00620
    @staticmethod
    def calculate_lamb_shift(alpha_q,chi):
        return alpha_q - chi/2
    
    @staticmethod
    def calculate_coupling_strength(f_q, f_r, alpha_q, chi):
    
        """
        Compute the qubit–resonator coupling strength from the EPR method.

        Parameters
        ----------
        f_q : float
            Qubit frequency in GHz.
        f_r : float
            Resonator frequency in GHz.
        alpha_q : float
            Qubit anharmonicity (in Hz).
        chi : float
            Dispersive shift (in Hz).

        Returns
        -------
        float
            Coupling strength g in Hz.

        Notes
        -----
        Based on Eq. (9) of https://arxiv.org/pdf/2312.13483.
        """
        
        
        delta = (f_r - f_q) * 10**9
        sigma = (f_q + f_r) * 10**9
        denom = alpha_q/(delta *(delta - alpha_q)) + alpha_q/(sigma*(sigma + alpha_q))
        g = np.sqrt(chi/denom/2)
        return g
        
class LOM:

    """
    Utilities for extracting qubit Hamiltonian parameters using a
    lumped oscillator model (LOM).

    These methods map capacitance and inductance values to effective
    transmon parameters using scqubits.
    """
    
    @staticmethod
    def get_Hamiltonian_parameters(C_Sigma,LJ):
    
        """
        Compute transmon Hamiltonian parameters from circuit values.

        Parameters
        ----------
        C_Sigma : float
            Total capacitance in Farads.
        LJ : float
            Josephson inductance in Henries.

        Returns
        -------
        dict
            Dictionary containing:
            - ``frequency_GHz`` : qubit transition frequency
            - ``anharmonicity_MHz`` : qubit anharmonicity

        Notes
        -----
        Uses :mod:`scqubits` to compute transmon energy levels.
        """
    
        EJ = phi0**2/((2*np.pi)**2*LJ) / h * 1e-6 # in MHz
        EC = e**2/(2*C_Sigma) / h * 1e-6 # in MHz
        
        qubit = scq.Transmon(EJ=EJ,
                        EC=EC,
                        ng=0,
                        ncut=31)
                        
        f_q = qubit.E01() / 1000 # in GHz
        alpha = qubit.anharmonicity() # in MHz
        
        return {"frequency_GHz":f_q,"anharmonicity_MHz":alpha}
        
