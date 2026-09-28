"""Hydraulic equations. Root solving and dispatch are handled by solver.py."""

import math

G = 9.81


def velocity(Q, A):
    if A <= 0:
        raise ValueError("Area must be positive.")
    return Q / A


def specific_energy(Q, A, y):
    return y + (velocity(Q, A) ** 2) / (2 * G)


def froude_number(Q, A, T):
    if A <= 0 or T <= 0:
        raise ValueError("Invalid geometry for Froude number.")
    hydraulic_depth = A / T
    return velocity(Q, A) / math.sqrt(G * hydraulic_depth)


def classify_flow(Fr):
    """Classify flow using an explicit numerical tolerance around Fr = 1."""
    tol = 1e-3
    if Fr < 1.0 - tol:
        return "Subcritical"
    if Fr > 1.0 + tol:
        return "Supercritical"
    return "Critical"


def resistance_discharge(A, R, resistance, S):
    if A <= 0 or R <= 0 or S <= 0:
        raise ValueError("Invalid geometry or slope for resistance calculation.")
    if resistance["kind"] == "n":
        return (1.0 / resistance["value"]) * A * (R ** (2 / 3)) * math.sqrt(S)
    elif resistance["kind"] == "C":
        return resistance["value"] * A * math.sqrt(R * S)
    raise ValueError("Invalid resistance specification.")


def critical_residual(Q, A, T):
    if T <= 0:
        raise ValueError("Top width must be positive.")
    return (Q ** 2) * T / (G * (A ** 3)) - 1.0


def critical_specific_energy(Q, y, A):
    """Specific energy evaluated directly at the critical depth."""
    if Q <= 0 or y <= 0 or A <= 0:
        raise ValueError("Discharge, depth, and area must be valid positive values.")
    return specific_energy(Q, A, y)


def friction_slope(Q, A, R, resistance):
    """Local friction slope Sf for the given depth and resistance law."""
    if Q < 0 or A <= 0 or R <= 0:
        raise ValueError("Discharge, area, and hydraulic radius must be valid.")
    if resistance["kind"] == "n":
        return ((Q * resistance["value"]) / (A * (R ** (2 / 3)))) ** 2
    if resistance["kind"] == "C":
        return (Q / (resistance["value"] * A)) ** 2 / R
    raise ValueError("Invalid resistance specification.")


def is_choked(E_approach, P_or_dz, Ec):
    """True if the weir height or bed change forces critical flow at the control section."""
    return (E_approach - P_or_dz) < Ec


def critical_slope(Q, A, R, resistance):
    """Friction slope evaluated at critical-flow conditions."""
    return friction_slope(Q, A, R, resistance)


# --- HYDRAULIC JUMP FORMULAS ---

def rectangular_conjugate_depth(y1, Fr1):
    """Calculates y2 given y1 and initial Froude number Fr1 for rectangular channels."""
    if Fr1 <= 1.0:
        raise ValueError("Initial Froude number must be supercritical (Fr1 > 1.0) for a hydraulic jump.")
    return (y1 / 2.0) * (math.sqrt(1.0 + 8.0 * (Fr1 ** 2)) - 1.0)


def jump_head_loss(Q, y1, A1, y2, A2):
    """Generic hydraulic-jump energy loss from the specific-energy balance."""
    if Q < 0 or y1 <= 0 or y2 <= 0 or A1 <= 0 or A2 <= 0:
        raise ValueError("Invalid hydraulic-jump inputs.")
    E1 = specific_energy(Q, A1, y1)
    E2 = specific_energy(Q, A2, y2)
    return E1 - E2

def general_momentum_residual(Q, A1, y1_bar, A2, y2_bar):
    """General momentum conservation residual across a hydraulic jump: (M1 - M2 = 0)."""
    M1 = (Q ** 2) / (G * A1) + A1 * y1_bar
    M2 = (Q ** 2) / (G * A2) + A2 * y2_bar
    return M1 - M2


# --- DEPRESSION FORMULAS ---

def depression_energy_balance(E_approach, dz):
    """
    Available specific energy inside a depression (dz is bed drop magnitude).
    E_dep = E_approach + dz
    """
    return E_approach + abs(dz)
