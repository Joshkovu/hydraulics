"""
geometry.py
-----------
Cross-sectional hydraulic geometry properties.
Distinguishes between standard rectangular (includes side wall friction)
and wide rectangular (R = y, unit width).
"""

import math


def rectangular(b, y):
    if y <= 0 or b <= 0:
        raise ValueError("Dimensions must be positive.")
    A = b * y
    P = b + 2.0 * y
    R = A / P
    T = b
    return {"A": A, "P": P, "R": R, "T": T}


def wide_rectangular(y, **kwargs):
    """
    Wide rectangular channel per unit width (b = 1.0 m).
    Hydraulic radius R = y (ignoring side walls).
    """
    if y <= 0:
        raise ValueError("Depth y must be positive.")
    A = y
    P = 1.0
    R = y
    T = 1.0
    return {"A": A, "P": P, "R": R, "T": T}


def triangular(theta, y):
    """Triangular channel using semi-vertical angle theta (radians)."""
    if y <= 0 or theta <= 0 or theta >= math.pi / 2:
        raise ValueError("Depth and semi-vertical angle must be valid positive values.")
    A = (y ** 2) * math.tan(theta)
    T = 2.0 * y * math.tan(theta)
    P = 2.0 * y / math.cos(theta)
    R = A / P
    return {"A": A, "P": P, "R": R, "T": T}


def trapezoidal(b, z, y):
    if y <= 0 or b <= 0 or z <= 0:
        raise ValueError("Dimensions must be positive.")
    A = (b + z * y) * y
    P = b + 2.0 * y * math.sqrt(1.0 + z ** 2)
    R = A / P
    T = b + 2.0 * z * y
    return {"A": A, "P": P, "R": R, "T": T}


def circular(d, y):
    if y <= 0 or d <= 0 or y > d:
        raise ValueError("Invalid depth for circular channel.")
    theta = 2.0 * math.acos(1.0 - (2.0 * y / d))
    A = ((d ** 2) / 8.0) * (theta - math.sin(theta))
    P = (d / 2.0) * theta
    R = A / P
    T = d * math.sin(theta / 2.0)
    return {"A": A, "P": P, "R": R, "T": T}


def semi_circular(d, y):
    return circular(d, y)
