"""
solver.py
---------
Computational engine for hydraulics.
Performs numerical root-solving via scipy.optimize.brentq and direct formula evaluations.
Communicates directly with formulas.py and geometry.py.
"""

from scipy.optimize import brentq
from scipy.integrate import quad
import formulas
import geometry


class SolverError(Exception):
    pass


# --- Numerical Root Solver ---

def dynamic_brentq(func, lower=1e-8, upper=1.0, growth=2.0, max_upper=None, max_steps=100):
    if lower <= 0 or upper <= lower:
        raise SolverError("Invalid initial bracket.")

    a, b = lower, upper
    if max_upper is None:
        max_upper = 1e7
    if max_upper < upper:
        raise SolverError("Maximum bracket bound cannot be below the initial upper bound.")

    try:
        fa = func(a)
    except Exception as exc:
        raise SolverError(f"Could not evaluate lower bound: {exc}") from exc

    if fa == 0:
        return a

    for _ in range(max_steps):
        try:
            fb = func(b)
        except Exception as exc:
            raise SolverError(f"Could not evaluate upper bound: {exc}") from exc

        if fb == 0:
            return b

        if fa * fb < 0:
            try:
                return brentq(func, a, b)
            except Exception as exc:
                raise SolverError(f"Root solver failed: {exc}") from exc

        next_b = b * growth
        if next_b > max_upper:
            next_b = max_upper
        if next_b <= b:
            break
        b = next_b

    raise SolverError("No sign-changing bracket was found in the dynamic range.")


# --- Geometry & Discharge Dispatch Helpers ---

def get_geometry_dict(shape, dims, y):
    geom_fn = {
        "rectangular": geometry.rectangular,
        "wide_rectangular": geometry.wide_rectangular,
        "triangular": geometry.triangular,
        "trapezoidal": geometry.trapezoidal,
        "circular": geometry.circular,
        "semi_circular": geometry.semi_circular,
    }[shape]
    return geom_fn(**dims, y=y)


def discharge_for_depth(discharge, g):
    if discharge["kind"] == "Q":
        return discharge["value"]
    return discharge["value"] * g["T"]


def maximum_depth(shape, dims):
    """Return the physical maximum flow depth for the section."""
    if shape == "circular":
        return dims["d"]
    if shape == "semi_circular":
        # A semi-circular open channel is limited to its radius.
        return dims["d"] / 2.0
    return None


def physical_bounds(shape, dims, lower, upper):
    """Keep numerical root brackets inside the physical depth domain."""
    eps = 1e-9
    max_y = maximum_depth(shape, dims)
    if max_y is not None:
        safe_max = max_y * (1.0 - eps)
        upper = min(upper, safe_max)
        lower = min(lower, safe_max)
    if lower <= 0 or upper <= lower:
        raise SolverError("No valid physical depth interval is available for this calculation.")
    return lower, upper


def centroid_depth(shape, dims, y):
    """Depth of the centroid below the free surface."""
    g = get_geometry_dict(shape, dims, y)

    def top_width(depth):
        return get_geometry_dict(shape, dims, depth)["T"]

    # First moment of area about the free surface.
    first_moment = quad(
        lambda z: (y - z) * top_width(z),
        0.0,
        y,
        limit=100,
    )[0]
    return first_moment / g["A"]


# --- Root Solving Wrappers ---

def critical_depth(shape, dims, discharge):
    def residual(y):
        g = get_geometry_dict(shape, dims, y)
        Q = discharge_for_depth(discharge, g)
        return formulas.critical_residual(Q, g["A"], g["T"])

    max_y = maximum_depth(shape, dims)
    upper = max_y or 1.0
    safe_upper = upper * (1.0 - 1e-9) if max_y else upper
    return dynamic_brentq(residual, 1e-8, safe_upper, max_upper=safe_upper if max_y else None)


def normal_depth(shape, dims, discharge, resistance, slope):
    def residual(y):
        g = get_geometry_dict(shape, dims, y)
        Q = discharge_for_depth(discharge, g)
        return formulas.resistance_discharge(g["A"], g["R"], resistance, slope) - Q

    max_y = maximum_depth(shape, dims)
    upper = max_y or max(1.0, dims.get("b", 1.0))
    if max_y:
        upper *= (1.0 - 1e-9)
    return dynamic_brentq(residual, 1e-8, upper, max_upper=upper if max_y else None)


def depth_for_energy(shape, dims, discharge, target_E, lower, upper):
    lower, upper = physical_bounds(shape, dims, lower, upper)

    def residual(y):
        g = get_geometry_dict(shape, dims, y)
        Q = discharge_for_depth(discharge, g)
        return formulas.specific_energy(Q, g["A"], y) - target_E

    return dynamic_brentq(residual, lower, upper, max_upper=upper if maximum_depth(shape, dims) else None)


# --- High-Level Hydraulics Calculators ---

def compute_critical_slope(shape, dims, discharge, resistance):
    yc = critical_depth(shape, dims, discharge)
    g = get_geometry_dict(shape, dims, yc)
    Q = discharge_for_depth(discharge, g)
    Sc = formulas.critical_slope(Q, g["A"], g["R"], resistance)
    return yc, Sc


def compute_froude(shape, dims, discharge, y):
    g = get_geometry_dict(shape, dims, y)
    Q = discharge_for_depth(discharge, g)
    Fr = formulas.froude_number(Q, g["A"], g["T"])
    regime = formulas.classify_flow(Fr)
    return Fr, regime


def compute_specific_energy(shape, dims, discharge, y):
    g = get_geometry_dict(shape, dims, y)
    Q = discharge_for_depth(discharge, g)
    return formulas.specific_energy(Q, g["A"], y)


def compute_uf_general_case(shape, dims, discharge, resistance, slope):
    yn = normal_depth(shape, dims, discharge, resistance, slope)
    gn = get_geometry_dict(shape, dims, yn)
    Qn = discharge_for_depth(discharge, gn)
    Fr = formulas.froude_number(Qn, gn["A"], gn["T"])
    E = formulas.specific_energy(Qn, gn["A"], yn)
    regime = formulas.classify_flow(Fr)
    return yn, Fr, E, regime


def compute_weir_choking_analysis(shape, dims, discharge, slope, resistance, P):
    yn = normal_depth(shape, dims, discharge, resistance, slope)
    yc = critical_depth(shape, dims, discharge)

    gn = get_geometry_dict(shape, dims, yn)
    gc = get_geometry_dict(shape, dims, yc)
    Qn = discharge_for_depth(discharge, gn)
    Qc = discharge_for_depth(discharge, gc)

    E_approach = formulas.specific_energy(Qn, gn["A"], yn)
    Ec = formulas.critical_specific_energy(Qc, yc, gc["A"])
    choked = formulas.is_choked(E_approach, P, Ec)

    return {
        "yn": yn,
        "yc": yc,
        "E_approach": E_approach,
        "Ec": Ec,
        "choked": choked,
    }


def weir_station_depths(shape, dims, discharge, E_approach, P, yc, Ec, yn, choked):
    if choked:
        yw = yc
        y_down = depth_for_energy(shape, dims, discharge, P + Ec, 1e-8, yc * 0.9999)
    else:
        yw = depth_for_energy(shape, dims, discharge, E_approach - P, yc * 1.0001, max(5.0, yn * 4))
        y_down = yn
    return yw, y_down


def compute_weir_transitions(shape, dims, discharge, slope, resistance, P):
    # First establish the original approach condition and test choking.
    base = compute_weir_choking_analysis(shape, dims, discharge, slope, resistance, P)

    # The final station depths are selected only AFTER the choking decision.
    yw, y_down = weir_station_depths(
        shape, dims, discharge, base["E_approach"], P, base["yc"], base["Ec"], base["yn"], base["choked"]
    )

    if base["choked"]:
        # Choking creates a backwater upstream. Therefore the upstream
        # transition depth is NOT the original normal depth. It is the
        # subcritical depth having the total energy required to reach
        # critical flow at the crest.
        y_up = depth_for_energy(
            shape, dims, discharge, P + base["Ec"],
            base["yc"] * 1.0001, max(5.0, base["yn"] * 4)
        )
    else:
        y_up = base["yn"]

    gu = get_geometry_dict(shape, dims, y_up)
    gw = get_geometry_dict(shape, dims, yw)
    gd = get_geometry_dict(shape, dims, y_down)

    Qu = discharge_for_depth(discharge, gu)
    Qw = discharge_for_depth(discharge, gw)
    Qd = discharge_for_depth(discharge, gd)

    Fr_up = formulas.froude_number(Qu, gu["A"], gu["T"])
    Fr_w = formulas.froude_number(Qw, gw["A"], gw["T"])
    Fr_d = formulas.froude_number(Qd, gd["A"], gd["T"])

    return {
        **base,
        "y_up": y_up,
        "yw": yw,
        "y_down": y_down,
        "Fr_up": Fr_up,
        "Fr_w": Fr_w,
        "Fr_d": Fr_d,
        "regime_up": formulas.classify_flow(Fr_up),
        "regime_w": formulas.classify_flow(Fr_w),
        "regime_d": formulas.classify_flow(Fr_d),
    }
def compute_weir_gvf(shape, dims, discharge, slope, resistance, P, target_rise, steps):
    yn = normal_depth(shape, dims, discharge, resistance, slope)
    yc = critical_depth(shape, dims, discharge)

    gc = get_geometry_dict(shape, dims, yc)
    Qc = discharge_for_depth(discharge, gc)
    Ec = formulas.critical_specific_energy(Qc, yc, gc["A"])

    gn = get_geometry_dict(shape, dims, yn)
    Qn = discharge_for_depth(discharge, gn)
    E_approach = formulas.specific_energy(Qn, gn["A"], yn)

    choked = formulas.is_choked(E_approach, P, Ec)

    if not choked:
        raise SolverError(
            "The weir does not cause choking, so the GVF backwater calculation is not applicable."
        )

    y_control = depth_for_energy(
        shape,
        dims,
        discharge,
        P + Ec,
        yc * 1.0001,
        max(5.0, yn * 4)
    )

    y_target = yn + target_rise
    dy = (y_target - y_control) / steps

    results = []
    y = y_control
    x = 0.0

    results.append((0, x, y, y - yn))

    for i in range(1, steps + 1):
        y_next = y + dy

        g1 = get_geometry_dict(shape, dims, y)
        g2 = get_geometry_dict(shape, dims, y_next)

        Q1 = discharge_for_depth(discharge, g1)
        Q2 = discharge_for_depth(discharge, g2)

        E1 = formulas.specific_energy(Q1, g1["A"], y)
        E2 = formulas.specific_energy(Q2, g2["A"], y_next)

        Sf1 = formulas.friction_slope(
            Q1, g1["A"], g1["R"], resistance
        )
        Sf2 = formulas.friction_slope(
            Q2, g2["A"], g2["R"], resistance
        )

        Sf_avg = (Sf1 + Sf2) / 2

        denom = slope - Sf_avg

        # As the profile approaches normal depth, S0 - Sf tends to zero
        # and the direct-step distance becomes numerically singular.
        # Stop cleanly rather than producing an unbounded step or
        # crashing the robot.
        if abs(denom) < 1e-10 or abs(y_next - yn) < 1e-8:
            break

        x += (E2 - E1) / denom
        y = y_next

        results.append((i, x, y, y - yn))

    return results, x

def compute_contraction_critical(shape, narrow_dims, discharge):
    yc = critical_depth(shape, narrow_dims, discharge)
    gc = get_geometry_dict(shape, narrow_dims, yc)
    Qc = discharge_for_depth(discharge, gc)
    Ec = formulas.critical_specific_energy(Qc, yc, gc["A"])
    return yc, Ec


def compute_contraction_bed_change(shape, wide_dims, narrow_dims, discharge, slope, resistance, dz):
    yn = normal_depth(shape, wide_dims, discharge, resistance, slope)
    gn = get_geometry_dict(shape, wide_dims, yn)
    Qn = discharge_for_depth(discharge, gn)
    E_approach = formulas.specific_energy(Qn, gn["A"], yn)

    yc_narrow, Ec_narrow = compute_contraction_critical(shape, narrow_dims, discharge)
    yc_wide = critical_depth(shape, wide_dims, discharge)

    choked = formulas.is_choked(E_approach, dz, Ec_narrow)

    if choked:
        H = dz + Ec_narrow
        y_narrow = yc_narrow
        y_up = depth_for_energy(shape, wide_dims, discharge, H, yc_wide * 1.0001, max(5.0, yn * 4))
        y_down = depth_for_energy(shape, wide_dims, discharge, H, 1e-8, yc_wide * 0.9999)
    else:
        y_up = yn
        y_narrow = depth_for_energy(shape, narrow_dims, discharge, E_approach - dz, yc_narrow * 1.0001, max(5.0, yn * 4))
        y_down = yn

    return {
        "E_approach": E_approach,
        "Ec_narrow": Ec_narrow,
        "choked": choked,
        "y_up": y_up,
        "y_narrow": y_narrow,
        "y_down": y_down,
    }


# --- HYDRAULIC JUMPS SOLVER METHODS ---

def compute_conjugate_depth(shape, dims, discharge, y1):
    g1 = get_geometry_dict(shape, dims, y1)
    Q = discharge_for_depth(discharge, g1)
    Fr1 = formulas.froude_number(Q, g1["A"], g1["T"])

    if Fr1 <= 1.0:
        raise SolverError(f"Flow depth y1 = {y1:.4f}m is subcritical (Fr = {Fr1:.4f}). Jump requires Fr1 > 1.0.")

    if shape in ("rectangular", "wide_rectangular"):
        y2 = formulas.rectangular_conjugate_depth(y1, Fr1)
    else:
        # For non-rectangular sections, conjugate depth comes from momentum
        # conservation, not from equal specific energy.
        ybar1 = centroid_depth(shape, dims, y1)

        def momentum_residual(y):
            g2_local = get_geometry_dict(shape, dims, y)
            ybar2_local = centroid_depth(shape, dims, y)
            return formulas.general_momentum_residual(Q, g1["A"], ybar1, g2_local["A"], ybar2_local)

        lower = y1 * (1.0 + 1e-6)
        upper = maximum_depth(shape, dims) or max(5.0, y1 * 10.0)
        if maximum_depth(shape, dims):
            upper *= (1.0 - 1e-9)
        y2 = dynamic_brentq(momentum_residual, lower, upper)

    g2 = get_geometry_dict(shape, dims, y2)
    Fr2 = formulas.froude_number(Q, g2["A"], g2["T"])
    head_loss = formulas.jump_head_loss(Q, y1, g1["A"], y2, g2["A"])
 

    return {
        "y1": y1,
        "Fr1": Fr1,
        "y2": y2,
        "Fr2": Fr2,
        "head_loss": abs(head_loss),
    }


# --- DEPRESSIONS SOLVER METHODS ---

def compute_depression_no_weir(shape, dims, discharge, slope, resistance, dz):
    """dz is depth of depression (positive float value representing bed drop)."""
    yn = normal_depth(shape, dims, discharge, resistance, slope)
    gn = get_geometry_dict(shape, dims, yn)
    Qn = discharge_for_depth(discharge, gn)
    E_approach = formulas.specific_energy(Qn, gn["A"], yn)

    E_dep = formulas.depression_energy_balance(E_approach, dz)
    yc = critical_depth(shape, dims, discharge)

    y_dep = depth_for_energy(shape, dims, discharge, E_dep, yc * 1.0001, max(5.0, yn * 4))

    return {
        "yn": yn,
        "dz": abs(dz),
        "E_approach": E_approach,
        "E_dep": E_dep,
        "y_dep": y_dep,
    }


def compute_depression_with_weir_full(shape, dims, discharge, slope, resistance, dz, P):
    """
    Evaluates multi-station depths (A, B, C, D, E) for a depression with a broad-crested weir.
    - dz: depth of depression (m)
    - P: height of weir measured from bottom of depression (m)
    """
    yn = normal_depth(shape, dims, discharge, resistance, slope)
    gn = get_geometry_dict(shape, dims, yn)
    Qn = discharge_for_depth(discharge, gn)
    E_approach = formulas.specific_energy(Qn, gn["A"], yn)

    yc = critical_depth(shape, dims, discharge)
    gc = get_geometry_dict(shape, dims, yc)
    Qc = discharge_for_depth(discharge, gc)
    Ec = formulas.critical_specific_energy(Qc, yc, gc["A"])

    # Net weir elevation relative to original channel bed
    dz_net = P - abs(dz)
    
    # Check choking condition past weir crest
    choked = formulas.is_choked(E_approach, dz_net, Ec)

    if choked:
        # Station C: Critical depth on the weir crest
        yC = yc
        
        # Required total energy head relative to original channel bed
        H_req = dz_net + Ec
        
        # Station A: Upstream backwater depth
        yA = depth_for_energy(shape, dims, discharge, H_req, yc * 1.0001, max(5.0, yn * 4))
        
        # Station B: Subcritical depth in depression before crest (measured from depression bed)
        E_B = H_req + abs(dz)
        yB = depth_for_energy(shape, dims, discharge, E_B, yc * 1.0001, max(5.0, yn * 4))

        # Station D: Supercritical depth downstream in depression (measured from depression bed)
        yD = depth_for_energy(shape, dims, discharge, E_B, 1e-8, yc * 0.9999)
        
        # Station E: Supercritical depth after the bed returns to the original level.
        # No hydraulic jump is assumed, so remain on the supercritical branch.
        E_E = H_req
        yE = depth_for_energy(shape, dims, discharge, E_E, 1e-8, yc * 0.9999)
    else:
        # Unchoked flow
        yA = yn
        
        # Water depth over the weir crest
        E_C = E_approach - dz_net
        yC = depth_for_energy(shape, dims, discharge, E_C, yc * 1.0001, max(5.0, yn * 4))
        
        # Water depth in depression before crest
        E_B = E_approach + abs(dz)
        yB = depth_for_energy(shape, dims, discharge, E_B, yc * 1.0001, max(5.0, yn * 4))
        
        yD = yB
        yE = yn

    return {
        "yn": yn,
        "yc": yc,
        "E_approach": E_approach,
        "Ec": Ec,
        "dz_net": dz_net,
        "choked": choked,
        "yA": yA,
        "yB": yB,
        "yC": yC,
        "yD": yD,
        "yE": yE,
    }
