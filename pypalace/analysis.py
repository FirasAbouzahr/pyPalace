"""
Quantum analysis utilities for extracting 
superconducting circuit Hamiltonian parameters 
from electromagnetic simulation results.
"""

import pandas as pd
import numpy as np
import scqubits as scq
from scipy.constants import e,hbar,h,pi
import matplotlib.pyplot as plt
from .utils import *
phi0 = 2.0678338484619295e-15

class EPR:

    """
    
    Utilities for computing qubit parameters using the energy participation
    ratio (EPR) method.
    
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
            Qubit frequency in Hz.
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

        w_q = 2 * np.pi * f_q
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
            Qubit frequency in Hz.
        f_r : float
            Resonator frequency in Hz.
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
        
        EJ = phi0**2/((2*pi)**2*LJ)
        w_q = 2 * np.pi * f_q
        w_r = 2 * np.pi * f_r
        
        chi = p_q * p_r * (hbar * w_q * w_r)/(4*EJ)
        
        return -chi / (2*np.pi)
    
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
            Qubit frequency in Hz.
        f_r : float
            Resonator frequency in Hz.
        alpha_q : float
            Qubit anharmonicity in Hz.
        chi : float
            Dispersive shift in Hz.

        Returns
        -------
        float
            Coupling strength g in Hz.

        Notes
        -----
        Based on Eq. (9) of https://arxiv.org/pdf/2312.13483.
        """
        
        
        alpha_q = 2*pi*alpha_q
        delta = 2*pi*(f_r - f_q)
        sigma = 2*pi*(f_q + f_r)
        chi = 2*pi*chi
        denom = alpha_q/(delta *(delta - alpha_q)) + alpha_q/(sigma*(sigma + alpha_q))
        g = np.sqrt(chi/denom/2)
        
        return g/(2*pi)
        
class LOM:

    """
    Utilities for extracting qubit Hamiltonian parameters using a
    lumped oscillator model (LOM).

    These methods map capacitance and inductance values to effective
    transmon parameters using scqubits and analytic expressions.
    """
    
    @staticmethod
    def calculate_C_Sigma(capacitance_matrix, topology):
    
        """
        Compute transmon total effective capacitance (C_Sigma).

        Parameters
        ----------
        capacitance_matrix : pandas.DataFrame
            Maxwell capacitance matrix obtained from :meth:`pypalace.simulation.Simulation.get_capacitance_matrix`.
        topology : str
            Either ``"grounded"`` or ``"floating"``.
            
        Returns
        -------
        float
            Transmon total effective capacitance (C_Sigma) in Farads.

        Notes
        -----
        For now this method only works for a transmon qubit with a single coupler.
        
        Assumed matrix orderings (naming convention of elements does not matter, only order):
        - ``"grounded"``: ``[island, coupler, ground]``
        - ``"floating"``: ``[pad1, pad2, coupler, ground]``
        """

        C = capacitance_matrix.to_numpy(dtype=float)
        topology = topology.lower()

        if topology == "grounded":
            if C.shape != (3, 3):
                raise ValueError(
                    "For topology='grounded', expected a 3x3 matrix ordered as "
                    "[island, coupler, ground]."
                )
            # Maxwell diagonal contains island capacitance to all other conductors.
            return float(C[0, 0])

        elif topology == "floating":
            if C.shape != (4, 4):
                raise ValueError(
                    "For topology='floating', expected a 4x4 matrix ordered as "
                    "[pad1, pad2, coupler, ground]."
                )

            C1 = -C[2, 0]  # coupler to pad1
            C3 = -C[2, 1]  # coupler to pad2
            C4 = -C[3, 0]  # ground to pad1
            C2 = -C[3, 1]  # ground to pad2
            Ct = -C[0, 1]  # pad1 to pad2

            return float(Ct + 1.0 / (1.0 / (C1 + C4) + 1.0 / (C3 + C2)))

        else:
            raise ValueError("topology must be either 'grounded' or 'floating'.")
            
    @staticmethod
    def calculate_coupling_strength(qubit_capacitance_matrix,LJ,f_r,C_r,topology):
        """
        Compute qubit-resonator coupling strength g.

        Parameters
        ----------
        qubit_capacitance_matrix : pandas.DataFrame
            Maxwell capacitance matrix of transmon qubit + coupler system obtained from :meth:`pypalace.simulation.Simulation.get_capacitance_matrix`.
        LJ : float
            Josephson inductance in Henries.
        f_r : float
            Resonator frequency in Hz.
        C_r : float
            Resonator capacitance as an effective lumped capacitance, can be obtained from :meth:`pypalace.analysis.LOM.calculate_C_r`.
        topology : str
            Either ``"grounded"`` or ``"floating"``.

        Returns
        -------
        float
            Coupling strength ``g`` in Hz.
        """

        C = qubit_capacitance_matrix.to_numpy(dtype=float)
        topology = topology.lower()

        C_sigma = LOM.calculate_C_Sigma(qubit_capacitance_matrix, topology)
        E_C = e**2 / (2 * C_sigma)
        EJ = phi0**2/((2*pi)**2*LJ)
        omega_r = 2*pi*f_r
        
        if topology == "grounded":
            C_g = -C[0, 1]  # island to coupler
            
            g = -(C_g / C_sigma) * np.sqrt(hbar * omega_r * e**2 / C_r) * (EJ / (8 * E_C)) ** 0.25 / hbar

            return abs(g)/(2*pi)

        elif topology == "floating":
            C1 = -C[2, 0]  # coupler to pad1
            C3 = -C[2, 1]  # coupler to pad2
            C4 = -C[3, 0]  # ground to pad1
            C2 = -C[3, 1]  # ground to pad2
            Ct = -C[0, 1]  # pad1 to pad2

            beta = abs(C1 * C2 - C4 * C3) / (
                Ct * (C2 + C3 + C4 + C1) + (C2 + C3) * (C4 + C1)
            )

            M01 = (1 / np.sqrt(2)) * (EJ / (8 * E_C)) ** 0.25
            V_rms = np.sqrt(hbar * omega_r / (2 * C_r))

            g = (2 / hbar) * beta * e * V_rms * M01

            return abs(g)/(2*pi)

        else:
            raise ValueError("topology must be either 'grounded' or 'floating'.")
            
    @staticmethod
    def calculate_dispersive_shift(f_q, f_r, alpha_q, g):
        """
        Compute the dispersive shift (chi) between a qubit and resonator from the LOM method.

        Parameters
        ----------
        f_q : float
            Qubit frequency in Hz.
        f_r : float
            Resonator frequency in Hz.
        alpha_q : float
            Qubit anharmonicity in Hz.
        g : float
            g in Hz.

        Returns
        -------
        float
            Coupling strength chi in Hz.
            
        Notes
        -----
        Based on Eq. (9) of https://arxiv.org/pdf/2312.13483
        """

        w_q = 2*pi*f_q
        w_r = 2*pi*f_r
        g = 2*pi*g
        alpha_q = 2*pi*alpha_q
        Delta = w_r-w_q
        Sigma = w_r + w_q
        chi = 2*g**2 * (alpha_q/(Delta*(Delta - alpha_q)) + alpha_q/(Sigma*(Sigma+alpha_q)))
        
        return chi/(2*pi)
    
    @staticmethod
    def get_qubit_Hamiltonian_parameters(C_Sigma,LJ):
    
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
        
        return {"frequency_GHz":float(f_q),"anharmonicity_MHz":float(alpha)}
        
    @staticmethod
    def calculate_C_r(f_r,m,Zc=50):
        """
        Compute resonator capacitance as an effective lumped capacitance.

        Parameters
        ----------
        f_r : float
            Resonator frequency [Hz]
        m : int
            m = 2 for quarter-wavelength resonators and m = 4 for half-wavelength resonators.
        Zc : float
            Waveguide’s characteristic impedance in Ohms, default is 50 Ohms.

        Returns
        -------
        float
            Resonator capacitance
            
        Notes
        -----
        Taken from Equation 8 of SQuADDS paper (https://quantum-journal.org/papers/q-2024-09-09-1465/)
        """
        wr = 2*np.pi * f_r
        return np.pi / (m * wr * Zc)

class resonator_analysis:
    
    def get_resonator_parameters_driven(S_ij,show=False,save=None):

        """
        Extracts f_r and kappa from a frequency-domain driven simulation of a superconducting resonator.

        Fit complex S21 data via the Diameter Correction Method (DCM)

        Parameters
        ----------
        S_ij : pandas.DataFrame
            DataFrame containing frequency, magnitude (dB), and phase (degrees). Otained from pypalace.Simulation.get_Sij.
        
        show : bool, optional
            If True (default), display the S21 plot.

        save : str or None, optional
            If provided, save the plot to the specified file path
            If None (default), the plot is not saved.
        
        Returns
        -------
        dictionary
            DataFrame containing frequency, magnitude (dB), and phase (degrees).

        Raises
        ------
        ValueError
            If the simulation type is not driven or if the specified port indices are invalid.
        """
        
        f0_fit, kappa_fit, theta0_fit, sign_fit, shift, R, f, S21_complex = DCM_backend.DCM_fit(S_ij)
        
        if show == True or save != None:
            f_plot = np.linspace(f.min(),f.max(),500)
            theta_fit = DCM_backend.angle_model(f_plot, f0_fit, kappa_fit, theta0_fit, sign_fit)
            unit_fit = np.exp(1j * theta_fit)
            original_fit = shift + R * unit_fit
            
            y_plot = 20*np.log10(np.abs(original_fit))
            trough_loc = np.where(y_plot == y_plot.min())
            freq_center = f_plot[trough_loc[0][0]]
            
            f = (f - freq_center)/1e3
            f_plot = (f_plot - freq_center)/1e3

            fig,ax = plt.subplots()
            plt.scatter(f,20*np.log10(np.abs(S21_complex)),label="simulation data",color="mediumblue")
            plt.plot(f_plot,y_plot,label="fit",color="crimson")
            plt.xlabel(r"$\Delta$ [kHz]")
            plt.ylabel(r"$||S_{21}||$ [dB]")
            plt.legend(fontsize = 10)
            
            if save != None:
                plt.savefig(save)
                
            if show == True:
                plt.show()
            
        return {"frequency_GHz":f0_fit/1e9,"kappa_kHz":kappa_fit/1e3}
