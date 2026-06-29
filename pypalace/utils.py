import numpy as np
import pandas as pd
from scipy.optimize import curve_fit, least_squares

''' backend functions for DCM fitting '''


class DCM_backend:

    @staticmethod
    def fit_to_circle(x, y):
        A = np.column_stack((2 * x, 2 * y, np.ones_like(x)))
        B = x**2 + y**2
        params, *_ = np.linalg.lstsq(A, B, rcond=None)
        a, b, c = params
        R = np.sqrt(a**2 + b**2 + c)
        return a, b, R

    @staticmethod
    def resonator_lineshape(f, Q, Qc, f0, phi):
        return 1 - (Q * np.exp(-1j * phi) / Qc) / (1 + 2j * Q * (f - f0) / f0)

    @staticmethod
    def angle_model(f, f0, kappa, theta0, sign):
        return theta0 + sign * 2 * np.arctan(2 * (f - f0) / kappa)

    @staticmethod
    def _dcm_complex_model(
        f: np.ndarray, ax: float, ay: float, R: float, f0: float, kappa: float, theta0: float, sign: float
    ) -> np.ndarray:
        phi = DCM_backend.angle_model(f, f0, kappa, theta0, sign)
        return ax + 1j * ay + R * np.exp(1j * phi)

    @staticmethod
    def _parse_sij(S_ij: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if S_ij.shape[1] < 3:
            raise ValueError(
                "S_ij must have three columns: frequency (GHz), |S| (dB), arg(S) (deg). "
                "Use Simulation.get_Sij()."
            )

        f_ghz = np.asarray(S_ij.iloc[:, 0], dtype=float)
        mag_db = np.asarray(S_ij.iloc[:, 1], dtype=float)
        phase_deg = np.asarray(S_ij.iloc[:, 2], dtype=float)

        if not (np.all(np.isfinite(f_ghz)) and np.all(np.isfinite(mag_db)) and np.all(np.isfinite(phase_deg))):
            raise ValueError("S_ij contains non-finite values.")

        order = np.argsort(f_ghz)
        return f_ghz[order] * 1e9, mag_db[order], phase_deg[order]

    @staticmethod
    def _frequency_step_hz(f: np.ndarray) -> float:
        if len(f) < 2:
            return 1e6
        return float(np.min(np.diff(f)))

    @staticmethod
    def _kappa_guess_from_mag(f: np.ndarray, mag_db: np.ndarray) -> float:
        """Rough linewidth (Hz) from |S21| half-max width."""
        f0_idx = int(np.argmin(mag_db))
        n_edge = max(2, len(mag_db) // 10)
        baseline = float(np.median(np.r_[mag_db[:n_edge], mag_db[-n_edge:]]))
        half = 0.5 * (baseline + float(mag_db[f0_idx]))
        df_min = DCM_backend._frequency_step_hz(f)

        crossings: list[float] = []
        for idx in range(len(f) - 1):
            y0 = float(mag_db[idx] - half)
            y1 = float(mag_db[idx + 1] - half)
            if y0 == 0.0:
                crossings.append(float(f[idx]))
            elif y0 * y1 < 0.0:
                frac = y0 / (y0 - y1)
                crossings.append(float(f[idx] + frac * (f[idx + 1] - f[idx])))

        if len(crossings) >= 2:
            return max(float(max(crossings) - min(crossings)), df_min)

        below = np.where(mag_db < half)[0]
        if len(below) >= 2:
            return max(float(f[below[-1]] - f[below[0]]), df_min)

        return max(float(f[-1] - f[0]) / 10.0, df_min)

    @staticmethod
    def _trim_around_dip(
        f: np.ndarray, mag_db: np.ndarray, phase_deg: np.ndarray, *, min_points: int = 8
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Keep points near the |S21| dip so wide coarse sweeps do not break DCM."""
        f0_idx = int(np.argmin(mag_db))
        f0 = f[f0_idx]
        kappa_mag = DCM_backend._kappa_guess_from_mag(f, mag_db)
        f_span = float(f[-1] - f[0])
        half_width = max(3.0 * kappa_mag, 0.05 * f_span)

        mask = np.abs(f - f0) <= half_width
        if mask.sum() < min_points:
            order = np.argsort(np.abs(f - f0))[:max(min_points, 4)]
            mask = np.zeros_like(f, dtype=bool)
            mask[order] = True

        return f[mask], mag_db[mask], phase_deg[mask]

    @staticmethod
    def _dcm_complex_residuals(params, f, S21, sign):
        ax, ay, R, f0, kappa, theta0 = params
        model = DCM_backend._dcm_complex_model(f, ax, ay, R, f0, kappa, theta0, sign)
        diff = model - S21
        return np.r_[diff.real, diff.imag]

    @staticmethod
    def _fit_dcm_complex(
        f: np.ndarray, S21: np.ndarray, mag_db: np.ndarray
    ) -> tuple[float, float, float, float, float, float, float, float, float]:
        """
        Fit the full DCM model in the IQ plane:
        S21(f) = (a + ib) + R * exp(i * (theta0 + sign * 2 arctan(2*(f-f0)/kappa)))
        """
        f0_idx = int(np.argmin(mag_db))
        f0_guess = float(f[f0_idx])
        f_span = float(f[-1] - f[0])
        df_min = DCM_backend._frequency_step_hz(f)
        kappa_guess = float(
            np.clip(DCM_backend._kappa_guess_from_mag(f, mag_db), df_min, max(f_span, df_min))
        )

        a, b, R0 = DCM_backend.fit_to_circle(S21.real, S21.imag)
        if R0 <= 0 or not np.isfinite(R0):
            raise ValueError("DCM circle fit failed (non-positive or invalid radius).")

        center = a + 1j * b
        theta0_guess = float(np.angle(S21[f0_idx] - center))

        best: tuple[float, float, float, float, float, float, float, float, float] | None = None

        for sign in (1.0, -1.0):
            p0 = [a, b, R0, f0_guess, kappa_guess, theta0_guess]
            lower = [-np.inf, -np.inf, 0.0, float(f[0]), df_min, -np.pi]
            upper = [np.inf, np.inf, np.inf, float(f[-1]), max(kappa_guess * 10.0, f_span), np.pi]

            try:
                result = least_squares(
                    DCM_backend._dcm_complex_residuals,
                    p0,
                    args=(f, S21, sign),
                    bounds=(lower, upper),
                    max_nfev=10000,
                )
            except Exception:
                continue

            ax, ay, R, f0_fit, kappa_fit, theta0_fit = map(float, result.x)
            pred = DCM_backend._dcm_complex_model(f, ax, ay, R, f0_fit, kappa_fit, theta0_fit, sign)
            rmse_db = float(
                np.sqrt(np.mean((20 * np.log10(np.maximum(np.abs(pred), 1e-30)) - mag_db) ** 2))
            )
            at_kappa_upper = kappa_fit >= 0.99 * upper[4]
            at_kappa_lower = kappa_fit <= 1.05 * df_min
            f0_penalty = abs(f0_fit - f0_guess) / max(f_span, df_min)
            score = (
                rmse_db
                + 5.0 * float(at_kappa_upper)
                + 5.0 * float(at_kappa_lower)
                + f0_penalty
            )

            if best is None or score < best[8]:
                best = (
                    f0_fit,
                    kappa_fit,
                    theta0_fit,
                    sign,
                    ax,
                    ay,
                    R,
                    rmse_db,
                    score,
                )

        if best is None:
            raise RuntimeError(
                "DCM fit did not converge. Narrow MinFreq/MaxFreq around the "
                "resonance and use a finer FreqStep (see Example 03)."
            )

        f0_fit, kappa_fit, theta0_fit, sign_fit, ax, ay, R, rmse_db, _ = best
        shift = ax + 1j * ay
        iq_rmse = float(
            np.sqrt(np.mean(np.abs(DCM_backend._dcm_complex_model(f, ax, ay, R, f0_fit, kappa_fit, theta0_fit, sign_fit) - S21) ** 2))
        )
        return f0_fit, kappa_fit, theta0_fit, sign_fit, shift, R, rmse_db, iq_rmse

    @staticmethod
    def _validate_fit(
        f: np.ndarray,
        mag_db: np.ndarray,
        f0_fit: float,
        kappa_fit: float,
        rmse_db: float,
        df_min: float | None = None,
    ) -> None:
        f_dip = float(f[int(np.argmin(mag_db))])
        f_span = float(f[-1] - f[0])
        if df_min is None:
            df_min = DCM_backend._frequency_step_hz(f)

        if f_span <= 0:
            raise ValueError("S_ij frequency column must span more than one distinct point.")

        if abs(f0_fit - f_dip) > 0.25 * f_span:
            raise ValueError(
                f"DCM fit failed sanity check: f0_fit={f0_fit/1e9:.6f} GHz but "
                f"|S21| dip is at {f_dip/1e9:.6f} GHz. Narrow MinFreq/MaxFreq "
                f"around the resonance and reduce FreqStep."
            )

        if df_min > 0 and kappa_fit <= 1.05 * df_min:
            raise ValueError(
                f"DCM fit pinned kappa to the frequency-grid limit "
                f"({kappa_fit/1e3:.3f} kHz; FreqStep≈{df_min/1e3:.3f} kHz). "
                f"Use a finer FreqStep and narrow MinFreq/MaxFreq so several "
                f"points sample the linewidth (see Example 03)."
            )

        q_loaded = f0_fit / kappa_fit if kappa_fit > 0 else 0.0
        if kappa_fit <= 0 or q_loaded < 10:
            raise ValueError(
                f"DCM fit failed sanity check: kappa={kappa_fit/1e3:.3f} kHz "
                f"(Q_loaded={q_loaded:.1f}). Refine the frequency grid near f0."
            )

        if rmse_db > 15.0:
            raise ValueError(
                f"DCM fit failed sanity check: |S21| residual RMSE={rmse_db:.2f} dB "
                f"is too large for a reliable linewidth."
            )

    @staticmethod
    def DCM_fit(S_ij: pd.DataFrame, *, auto_trim: bool = True, min_points: int = 8):
        f, mag_db, phase_deg = DCM_backend._parse_sij(S_ij)

        if len(f) < max(min_points, 6):
            raise ValueError(
                f"DCM needs at least {max(min_points, 6)} frequency points; got {len(f)}."
            )

        if auto_trim:
            f, mag_db, phase_deg = DCM_backend._trim_around_dip(
                f, mag_db, phase_deg, min_points=min_points
            )

        S21_complex = (10 ** (mag_db / 20.0)) * np.exp(1j * np.deg2rad(phase_deg))
        f_dip = float(f[int(np.argmin(mag_db))])
        df_min = DCM_backend._frequency_step_hz(f)

        (
            f0_fit,
            kappa_fit,
            theta0_fit,
            sign_fit,
            shift,
            R,
            rmse_db,
            iq_rmse,
        ) = DCM_backend._fit_dcm_complex(f, S21_complex, mag_db)

        DCM_backend._validate_fit(
            f, mag_db, f0_fit, kappa_fit, rmse_db, df_min=df_min
        )

        return (
            f0_fit,
            kappa_fit,
            theta0_fit,
            sign_fit,
            shift,
            R,
            f,
            S21_complex,
            iq_rmse,
            f_dip,
            rmse_db,
            df_min,
        )
