"""Units and constants. Internal units are SI (m, kg, s, N, rad)."""
import math

MM_PER_M = 1000.0
G_STD = 9.80665          # m/s^2, standard gravity
RHO_SEAWATER = 1025.0    # kg/m^3 (illustrative default)
RHO_FRESH = 998.0        # kg/m^3 (approx., ~20 degC)


def mm_to_m(x):
    return x / MM_PER_M


def m_to_mm(x):
    return x * MM_PER_M


def deg(x):
    return x * 180.0 / math.pi


def rad(x):
    return x * math.pi / 180.0
