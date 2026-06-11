import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

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
    def _angle_model_fixed_sign(sign):
        def model(f, f0, kappa, theta0):
            return DCM_backend.angle_model(f, f0, kappa, theta0, sign)

        return model

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
    def _kappa_guess_from_mag(f: np.ndarray, mag_db: np.ndarray) -> float:
        """Rough linewidth (Hz) from |S21| half-max width."""
        f0_idx = int(np.argmin(mag_db))
        n_edge = max(2, len(mag_db) // 10)
        baseline = float(np.median(np.r_[mag_db[:n_edge], mag_db[-n_edge:]]))
        half = 0.5 * (baseline + float(mag_db[f0_idx]))
        below = np.where(mag_db < half)[0]
        df_min = float(np.min(np.diff(f))) if len(f) > 1 else 1e6

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
    def _notch_power(f: np.ndarray, f0: float, kappa: float, depth: float, base: float) -> np.ndarray:
        return base - depth / (1 + (2 * (f - f0) / kappa) ** 2)

    @staticmethod
    def _notch_mag_db(f: np.ndarray, f0: float, kappa: float, depth: float, base: float) -> np.ndarray:
        power = DCM_backend._notch_power(f, f0, kappa, depth, base)
        return 10 * np.log10(np.maximum(power, 1e-30))

    @staticmethod
    def _fit_magnitude_notch(
        f: np.ndarray, mag_db: np.ndarray
    ) -> tuple[float, float, float, float, float, float]:
        """Lorentzian notch fit in linear power when the DCM phase arc is too short."""
        power = 10 ** (mag_db / 10.0)
        f0_guess = float(f[int(np.argmin(mag_db))])
        kappa_guess = DCM_backend._kappa_guess_from_mag(f, mag_db)
        n_edge = max(2, len(power) // 10)
        base_guess = float(np.median(np.r_[power[:n_edge], power[-n_edge:]]))
        depth_guess = float(max(base_guess - power.min(), 1e-30))
        f_span = float(f[-1] - f[0])
        df_min = float(np.min(np.diff(f))) if len(f) > 1 else 1e6

        popt, _ = curve_fit(
            DCM_backend._notch_power,
            f,
            power,
            p0=[f0_guess, kappa_guess, depth_guess, base_guess],
            bounds=(
                [float(f[0]), df_min, 0.0, 0.0],
                [float(f[-1]), max(f_span * 10.0, df_min * 10.0), base_guess * 2.0, base_guess * 2.0],
            ),
            maxfev=10000,
        )
        f0_fit, kappa_fit, depth_fit, base_fit = map(float, popt)
        pred = DCM_backend._notch_power(f, f0_fit, kappa_fit, depth_fit, base_fit)
        rmse = float(np.sqrt(np.mean((pred - power) ** 2)))
        return f0_fit, kappa_fit, depth_fit, base_fit, rmse

    @staticmethod
    def _fit_phase_arc(
        f: np.ndarray, phi: np.ndarray, mag_db: np.ndarray
    ) -> tuple[float, float, float, float, float]:
        """Fit (f0, kappa, theta0, sign) to unwrapped phase; return fit + rmse."""
        f0_guess = float(f[int(np.argmin(mag_db))])
        f_span = float(f[-1] - f[0])
        df_min = float(np.min(np.diff(f))) if len(f) > 1 else 1e6

        dphi_df = np.abs(np.gradient(phi, f))
        if np.max(dphi_df) > 1e-12:
            kappa_guess = 4.0 / np.max(dphi_df)
        else:
            kappa_guess = DCM_backend._kappa_guess_from_mag(f, mag_db)

        kappa_guess = float(np.clip(kappa_guess, df_min, max(f_span, df_min)))
        phi_guess = float(phi[int(np.argmin(np.abs(f - f0_guess)))])

        f_lo, f_hi = float(f[0]), float(f[-1])
        kappa_lo = df_min
        kappa_hi = max(f_span * 2.0, df_min * 10.0)

        best: tuple[float, float, float, float, float] | None = None

        for sign in (1.0, -1.0):
            model = DCM_backend._angle_model_fixed_sign(sign)
            try:
                popt, _ = curve_fit(
                    model,
                    f,
                    phi,
                    p0=[f0_guess, kappa_guess, phi_guess],
                    bounds=([f_lo, kappa_lo, -np.inf], [f_hi, kappa_hi, np.inf]),
                    maxfev=5000,
                )
            except Exception:
                continue

            f0_fit, kappa_fit, theta0_fit = map(float, popt)
            resid = model(f, f0_fit, kappa_fit, theta0_fit) - phi
            rmse = float(np.sqrt(np.mean(resid**2)))

            if best is None or rmse < best[4]:
                best = (f0_fit, kappa_fit, theta0_fit, sign, rmse)

        if best is None:
            raise RuntimeError(
                "DCM phase fit did not converge. Use a narrower frequency window "
                "and finer FreqStep around the resonance (see Example 03)."
            )

        return best

    @staticmethod
    def _validate_fit(
        f: np.ndarray,
        mag_db: np.ndarray,
        f0_fit: float,
        kappa_fit: float,
        rmse: float,
        phi: np.ndarray,
    ) -> None:
        f_dip = float(f[int(np.argmin(mag_db))])
        f_span = float(f[-1] - f[0])
        phi_span = float(np.ptp(phi))

        if f_span <= 0:
            raise ValueError("S_ij frequency column must span more than one distinct point.")

        if abs(f0_fit - f_dip) > 0.25 * f_span:
            raise ValueError(
                f"DCM fit failed sanity check: f0_fit={f0_fit/1e9:.6f} GHz but "
                f"|S21| dip is at {f_dip/1e9:.6f} GHz. Narrow MinFreq/MaxFreq "
                f"around the resonance and reduce FreqStep."
            )

        q_loaded = f0_fit / kappa_fit if kappa_fit > 0 else 0.0
        if kappa_fit <= 0 or q_loaded < 10:
            raise ValueError(
                f"DCM fit failed sanity check: kappa={kappa_fit/1e3:.3f} kHz "
                f"(Q_loaded={q_loaded:.1f}). Data likely has too few points through "
                f"the resonance for a reliable linewidth."
            )

        if phi_span < 0.1:
            raise ValueError(
                "DCM fit failed sanity check: phase on the normalized circle "
                "barely changes across the sweep. Refine the frequency grid near f0."
            )

        if rmse > 0.5:
            raise ValueError(
                f"DCM fit failed sanity check: phase residual RMSE={rmse:.3f} rad "
                f"is too large for a reliable kappa."
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

        a, b, R = DCM_backend.fit_to_circle(S21_complex.real, S21_complex.imag)
        if R <= 0 or not np.isfinite(R):
            raise ValueError("DCM circle fit failed (non-positive or invalid radius).")

        shift = a + 1j * b
        S21_norm = (S21_complex - shift) / R
        phi = np.unwrap(np.arctan2(S21_norm.imag, S21_norm.real))
        phi_span = float(np.ptp(phi))

        method = "DCM"
        notch_depth = np.nan
        notch_base = np.nan
        theta0_fit = 0.0
        sign_fit = 1.0

        use_dcm = phi_span >= 0.5
        if use_dcm:
            try:
                f0_fit, kappa_fit, theta0_fit, sign_fit, rmse = DCM_backend._fit_phase_arc(
                    f, phi, mag_db
                )
                DCM_backend._validate_fit(f, mag_db, f0_fit, kappa_fit, rmse, phi)
            except (RuntimeError, ValueError):
                use_dcm = False

        if not use_dcm:
            method = "magnitude"
            f0_fit, kappa_fit, notch_depth, notch_base, rmse = DCM_backend._fit_magnitude_notch(
                f, mag_db
            )
            q_loaded = f0_fit / kappa_fit if kappa_fit > 0 else 0.0
            if kappa_fit <= 0 or q_loaded < 10:
                raise ValueError(
                    f"Resonator fit failed: kappa={kappa_fit/1e3:.3f} kHz "
                    f"(Q_loaded={q_loaded:.1f})."
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
            rmse,
            f_dip,
            method,
            notch_depth,
            notch_base,
        )
