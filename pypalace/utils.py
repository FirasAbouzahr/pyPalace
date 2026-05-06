import numpy as np
from scipy.optimize import curve_fit

''' backend functions for DCM fitting '''
''' DCM fitting is in a preliminary state - updates to come '''

class DCM_backend:

    @staticmethod
    def fit_to_circle(x,y):
        A = np.column_stack((2*x, 2*y,np.ones_like(x)))
        B = x**2 + y**2
        params, *_ = np.linalg.lstsq(A, B, rcond=None)
        a, b, c = params
        R = np.sqrt(a**2 + b**2 + c)
        return a,b,R
    
    @staticmethod
    def resonator_lineshape(f, Q, Qc, f0, phi):
        return 1-(Q*np.exp(-1j*phi)/Qc)/(1+2j*Q*(f-f0)/f0)
    
    @staticmethod
    def angle_model(f, f0, kappa, theta0, sign):
        return theta0 + sign * 2*np.arctan(2*(f-f0)/kappa)
    
    @staticmethod
    def DCM_fit(S_ij):
    
        f = S_ij.iloc[:, 0].to_numpy() * 1e9
        mag = S_ij.iloc[:, 1].to_numpy()
        phase = S_ij.iloc[:, 2].to_numpy()
        
        # get complex data
        S21_complex = (10**(mag / 20.0)* np.exp(1j * np.deg2rad(phase)))
        
        # fit to circle to find center coordinates & radius
        a,b,R = DCM_backend.fit_to_circle(S21_complex.real,S21_complex.imag)
        shift = a + 1j * b
        
        # center the circle & normalize to unit circle
        S21_complex_00_normalized = (S21_complex - shift)/R

        x,y = S21_complex_00_normalized.real,S21_complex_00_normalized.imag
        phi = np.unwrap(np.arctan2(y, x))
        
        # estimate good fit parameters to help the fitter
        f0_guess = f[np.argmax(np.abs(mag))]
        kappa_guess = 4 / np.max(np.abs(np.gradient(phi, f)))
        phi_guess = phi[0]
        sign_guess = 1
        p0 = [f0_guess, kappa_guess, phi_guess, sign_guess]
        
        # fit
        p,c = curve_fit(DCM_backend.angle_model, f, phi, p0=p0)
        
        f0_fit, kappa_fit, theta0_fit, sign_fit = p
        
        return f0_fit, kappa_fit, theta0_fit, sign_fit, shift, R,f,S21_complex


            
        
