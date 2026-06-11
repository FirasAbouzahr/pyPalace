"""
Drop-in DCM fix for pyPalace 0.1.3 tutorial environments.

Usage (one cell, before fitting):

    from dcm_patch_v013 import apply
    apply()

Then call ``resonator_analysis.get_resonator_parameters_driven`` as usual.
No-op on pyPalace >= 0.1.4. Remove this import after the env is upgraded.
"""

from __future__ import annotations

import inspect

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import least_squares


class _DCM:
    @staticmethod
    def fit_to_circle(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
        design = np.column_stack((2 * x, 2 * y, np.ones_like(x)))
        rhs = x**2 + y**2
        a, b, c = np.linalg.lstsq(design, rhs, rcond=None)[0]
        return float(a), float(b), float(np.sqrt(a**2 + b**2 + c))

    @staticmethod
    def angle_model(f, f0, kappa, theta0, sign):
        return theta0 + sign * 2 * np.arctan(2 * (f - f0) / kappa)

    @staticmethod
    def _model(f, ax, ay, radius, f0, kappa, theta0, sign):
        return ax + 1j * ay + radius * np.exp(1j * _DCM.angle_model(f, f0, kappa, theta0, sign))

    @staticmethod
    def _parse_sij(s_ij: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        freq_ghz = np.asarray(s_ij.iloc[:, 0], dtype=float)
        mag_db = np.asarray(s_ij.iloc[:, 1], dtype=float)
        phase_deg = np.asarray(s_ij.iloc[:, 2], dtype=float)
        order = np.argsort(freq_ghz)
        return freq_ghz[order] * 1e9, mag_db[order], phase_deg[order]

    @staticmethod
    def _kappa_from_mag(f: np.ndarray, mag_db: np.ndarray) -> float:
        dip = int(np.argmin(mag_db))
        edge = max(2, len(mag_db) // 10)
        baseline = float(np.median(np.r_[mag_db[:edge], mag_db[-edge:]]))
        half = 0.5 * (baseline + float(mag_db[dip]))
        below = np.where(mag_db < half)[0]
        df_min = float(np.min(np.diff(f))) if len(f) > 1 else 1e6
        if len(below) >= 2:
            return max(float(f[below[-1]] - f[below[0]]), df_min)
        return max(float(f[-1] - f[0]) / 10.0, df_min)

    @staticmethod
    def _trim(f, mag_db, phase_deg, *, min_points: int = 8):
        dip = int(np.argmin(mag_db))
        f0 = f[dip]
        half_width = max(3.0 * _DCM._kappa_from_mag(f, mag_db), 0.05 * float(f[-1] - f[0]))
        mask = np.abs(f - f0) <= half_width
        if mask.sum() < min_points:
            keep = np.argsort(np.abs(f - f0))[:max(min_points, 4)]
            mask = np.zeros_like(f, dtype=bool)
            mask[keep] = True
        return f[mask], mag_db[mask], phase_deg[mask]

    @staticmethod
    def fit(s_ij: pd.DataFrame, *, auto_trim: bool = True, min_points: int = 8):
        f, mag_db, phase_deg = _DCM._parse_sij(s_ij)
        if len(f) < max(min_points, 6):
            raise ValueError(f"DCM needs at least {max(min_points, 6)} points; got {len(f)}.")

        if auto_trim:
            f, mag_db, phase_deg = _DCM._trim(f, mag_db, phase_deg, min_points=min_points)

        s21 = (10 ** (mag_db / 20.0)) * np.exp(1j * np.deg2rad(phase_deg))
        dip_idx = int(np.argmin(mag_db))
        f_dip = float(f[dip_idx])
        f_span = float(f[-1] - f[0])
        df_min = float(np.min(np.diff(f))) if len(f) > 1 else 1e6
        kappa_guess = float(np.clip(_DCM._kappa_from_mag(f, mag_db), df_min, max(f_span, df_min)))

        ax, ay, radius = _DCM.fit_to_circle(s21.real, s21.imag)
        if radius <= 0 or not np.isfinite(radius):
            raise ValueError("DCM circle fit failed.")

        center = ax + 1j * ay
        f0_guess = float(f[dip_idx])
        theta0_guess = float(np.angle(s21[dip_idx] - center))

        best = None
        for sign in (1.0, -1.0):
            p0 = [ax, ay, radius, f0_guess, kappa_guess, theta0_guess]
            lower = [-np.inf, -np.inf, 0.0, float(f[0]), df_min, -np.pi]
            upper = [np.inf, np.inf, np.inf, float(f[-1]), max(kappa_guess * 10.0, f_span), np.pi]

            def residuals(params, freqs, data, s):
                model = _DCM._model(freqs, *params[:3], params[3], params[4], params[5], s)
                diff = model - data
                return np.r_[diff.real, diff.imag]

            try:
                result = least_squares(
                    residuals, p0, args=(f, s21, sign), bounds=(lower, upper), max_nfev=10000
                )
            except Exception:
                continue

            fit_ax, fit_ay, fit_r, f0, kappa, theta0 = map(float, result.x)
            pred = _DCM._model(f, fit_ax, fit_ay, fit_r, f0, kappa, theta0, sign)
            rmse_db = float(
                np.sqrt(np.mean((20 * np.log10(np.maximum(np.abs(pred), 1e-30)) - mag_db) ** 2))
            )
            score = rmse_db + 5.0 * float(kappa >= 0.99 * upper[4])
            if best is None or score < best["score"]:
                best = {
                    "f0": f0,
                    "kappa": kappa,
                    "theta0": theta0,
                    "sign": sign,
                    "ax": fit_ax,
                    "ay": fit_ay,
                    "radius": fit_r,
                    "rmse_db": rmse_db,
                    "score": score,
                }

        if best is None:
            raise RuntimeError(
                "DCM fit did not converge. Narrow MinFreq/MaxFreq around the resonance."
            )

        pred = _DCM._model(
            f, best["ax"], best["ay"], best["radius"],
            best["f0"], best["kappa"], best["theta0"], best["sign"],
        )
        iq_rmse = float(np.sqrt(np.mean(np.abs(pred - s21) ** 2)))
        return best, f, s21, f_dip, iq_rmse


def get_resonator_parameters_driven(
    s_ij,
    show: bool = False,
    save: str | None = None,
    *,
    auto_trim: bool = True,
    min_points: int = 8,
):
    best, f, s21, f_dip, iq_rmse = _DCM.fit(s_ij, auto_trim=auto_trim, min_points=min_points)

    if show or save is not None:
        f_plot = np.linspace(f.min(), f.max(), 500)
        pred = _DCM._model(
            f_plot, best["ax"], best["ay"], best["radius"],
            best["f0"], best["kappa"], best["theta0"], best["sign"],
        )
        fig, ax = plt.subplots()
        ax.scatter(
            (f - best["f0"]) / 1e3,
            20 * np.log10(np.abs(s21)),
            label="simulation data",
            color="mediumblue",
        )
        ax.plot(
            (f_plot - best["f0"]) / 1e3,
            20 * np.log10(np.maximum(np.abs(pred), 1e-30)),
            label="DCM fit",
            color="crimson",
        )
        ax.set_xlabel(r"$\Delta f$ [kHz]")
        ax.set_ylabel(r"$|S_{21}|$ [dB]")
        ax.legend(fontsize=10)
        if save is not None:
            fig.savefig(save)
        if show:
            plt.show()
        else:
            plt.close(fig)

    return {
        "frequency_GHz": best["f0"] / 1e9,
        "kappa_kHz": best["kappa"] / 1e3,
        "frequency_dip_GHz": f_dip / 1e9,
        "fit_rmse": iq_rmse,
        "fit_rmse_db": best["rmse_db"],
    }


def _already_fixed() -> bool:
    from pypalace.utils import DCM_backend

    return "auto_trim" in inspect.signature(DCM_backend.DCM_fit).parameters


def apply() -> bool:
    """
    Patch ``resonator_analysis.get_resonator_parameters_driven`` for pyPalace 0.1.3.

    Returns True if the patch was applied, False if the installed version is already fixed.
    """
    if _already_fixed():
        return False

    from pypalace.analysis import resonator_analysis

    resonator_analysis.get_resonator_parameters_driven = get_resonator_parameters_driven
    return True
