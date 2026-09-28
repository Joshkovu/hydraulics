"""Controller for the five-module open-channel hydraulics robot."""

import input as inp
import solver


SHAPES = {
    "1": ("rectangular", "Rectangular"),
    "2": ("wide_rectangular", "Wide Rectangular"),
    "3": ("triangular", "Triangular"),
    "4": ("trapezoidal", "Trapezoidal"),
    "5": ("circular", "Circular"),
    "6": ("semi_circular", "Semi-circular"),
}

CATEGORIES = {
    "1": "UF Analysis",
    "2": "Weirs",
    "3": "Hydraulic Jumps",
    "4": "Contractions",
    "5": "Depressions",
}

UF_CALCULATIONS = {
    "1": "Critical Depth",
    "2": "Critical Slope",
    "3": "Normal Depth",
    "4": "Froude Number",
    "5": "Specific Energy",
    "6": "General Analysis",
}


def show_menu(title, options):
    print("\n" + "=" * 55)
    print(title)
    print("=" * 55)
    for key, value in options.items():
        print(f"{key}. {value}")


def select_shape():
    show_menu("CHANNEL SHAPE", {k: v[1] for k, v in SHAPES.items()})
    choice = inp.get_choice("Choose shape: ", list(SHAPES))
    return SHAPES[choice][0]


def select_category():
    show_menu("CALCULATION CATEGORY", CATEGORIES)
    return inp.get_choice("Choose category: ", list(CATEGORIES))


def print_choking_basis(E_approach, P_or_dz, Ec, choked, is_contraction=False):
    available = E_approach - P_or_dz
    if is_contraction:
        print(f"\nApproach specific energy,          E_approach = {E_approach:.6f} m")
        print(f"Bed change,                        dz         = {P_or_dz:+.6f} m")
        print(f"Energy available at narrow section, E_approach - dz = {available:.6f} m")
        print(f"Minimum energy required,           Ec         = {Ec:.6f} m")
        comparison = "<" if available < Ec else (">" if available > Ec else "=")
        print(f"(E_approach - dz) {comparison} Ec  ->  {'CHOKING OCCURS' if choked else 'no choking'}")
    else:
        print(f"\nApproach specific energy,     E_approach = {E_approach:.6f} m")
        print(f"Obstacle elevation change,    dz_net     = {P_or_dz:.6f} m")
        print(f"Energy available past crest,  E_approach - dz_net = {available:.6f} m")
        print(f"Minimum energy required,      Ec         = {Ec:.6f} m")
        comparison = "<" if available < Ec else (">" if available > Ec else "=")
        print(f"(E_approach - dz_net) {comparison} Ec  ->  {'CHOKING OCCURS' if choked else 'no choking'}")


def run_uf(shape):
    show_menu("UF ANALYSIS", UF_CALCULATIONS)
    choice = inp.get_choice("Choose UF calculation: ", list(UF_CALCULATIONS))
    discharge = inp.get_discharge(shape)
    dims = inp.get_geometry(shape, discharge_info=discharge)

    try:
        if choice == "1":
            yc = solver.critical_depth(shape, dims, discharge)
            print(f"\nCritical depth, yc = {yc:.6f} m")

        elif choice == "2":
            resistance = inp.get_roughness()
            yc, Sc = solver.compute_critical_slope(shape, dims, discharge, resistance)
            print(f"\nCritical depth, yc  = {yc:.6f} m")
            print(f"Critical slope, Sc  = {Sc:.6f}")

        elif choice == "3":
            slopes = inp.get_slope_cases()
            resistance = inp.get_roughness()

            for i, slope in enumerate(slopes, 1):
                try:
                    yn = solver.normal_depth(shape, dims, discharge, resistance, slope)
                    print(f"\nCase {i}: S = {slope}")
                    print(f"Normal depth, yn = {yn:.6f} m")
                except (ValueError, solver.SolverError) as exc:
                    print(f"\nCase {i}: calculation failed: {exc}")

        elif choice == "4":
            y = inp.get_positive("Enter flow depth y: ")
            Fr, regime = solver.compute_froude(shape, dims, discharge, y)
            print(f"\nFroude number, Fr = {Fr:.6f}")
            print(f"Flow regime = {regime}")

        elif choice == "5":
            y = inp.get_positive("Enter flow depth y: ")
            E = solver.compute_specific_energy(shape, dims, discharge, y)
            print(f"\nSpecific energy, E = {E:.6f} m")

        elif choice == "6":
            run_uf_general(shape, dims, discharge)

    except (ValueError, solver.SolverError) as exc:
        print(f"\nCalculation could not be completed: {exc}")


def run_uf_general(shape, dims, discharge):
    slopes = inp.get_slope_cases()
    resistance = inp.get_roughness()

    try:
        yc, Sc = solver.compute_critical_slope(shape, dims, discharge, resistance)
        print(f"\nCritical depth, yc = {yc:.6f} m")
        print(f"Critical slope, Sc = {Sc:.6f}")

        for i, slope in enumerate(slopes, 1):
            yn, Fr, E, regime = solver.compute_uf_general_case(shape, dims, discharge, resistance, slope)
            print(f"\nCase {i}: S = {slope}")
            print(f"Normal depth, yn  = {yn:.6f} m")
            print(f"Froude number, Fr = {Fr:.6f}")
            print(f"Specific energy, E = {E:.6f} m")
            print(f"Flow regime        = {regime}")

    except (ValueError, solver.SolverError) as exc:
        print(f"\nGeneral analysis could not be completed: {exc}")


def run_weirs(shape):
    show_menu("WEIRS", {
        "1": "Flow Transitions / Flow Regimes",
        "2": "GVF Step Method",
    })
    choice = inp.get_choice("Choose calculation: ", ["1", "2"])
    discharge = inp.get_discharge(shape)
    dims = inp.get_geometry(shape, discharge_info=discharge)

    if choice == "1":
        slopes = inp.get_slope_cases()
        resistance = inp.get_roughness()
        P = inp.get_weir_height()

        for case_no, slope in enumerate(slopes, 1):
            try:
                print(f"\n--- Slope Case {case_no}: S = {slope} ---")
                res = solver.compute_weir_transitions(shape, dims, discharge, slope, resistance, P)

                # Flow transition contains the choking check AND the final
                # station depths, so there is no separate weir-depth/choking
                # calculation to repeat.
                print_choking_basis(res["E_approach"], P, res["Ec"], res["choked"])
                print(f"\n{'Station':<14}{'Depth (m)':<14}{'Froude Fr':<12}{'Regime':<14}")
                print(f"{'Upstream':<14}{res['y_up']:<14.6f}{res['Fr_up']:<12.6f}{res['regime_up']:<14}")
                print(f"{'At crest':<14}{res['yw']:<14.6f}{res['Fr_w']:<12.6f}{res['regime_w']:<14}")
                print(f"{'Downstream':<14}{res['y_down']:<14.6f}{res['Fr_d']:<12.6f}{res['regime_d']:<14}")

                if res["choked"]:
                    print(f"\nRise in upstream water level = {res['y_up'] - res['yn']:.6f} m")

            except (ValueError, solver.SolverError) as exc:
                print(f"\nSlope Case {case_no}: Weir calculation could not be completed: {exc}")

    elif choice == "2":
        slopes = inp.get_slope_cases()
        resistance = inp.get_roughness()
        P = inp.get_limiting_weir_height()
        target_rise = inp.get_target_rise()
        steps = inp.get_case_count("Enter number of steps: ")

        for case_no, slope in enumerate(slopes, 1):
            try:
                table, total_x = solver.compute_weir_gvf(shape, dims, discharge, slope, resistance, P, target_rise, steps)
                print(f"\n--- Slope Case {case_no}: S = {slope} ---")
                print(f"{'Step':<6}{'Distance (m)':<16}{'Depth y (m)':<15}{'Rise (m)':<12}")
                for step, x, y, rise in table:
                    print(f"{step:<6}{x:<16.3f}{y:<15.6f}{rise:<12.4f}")
                print(f"\nDistance upstream where rise = {target_rise:.4f} m: {total_x:.3f} m")
            except (ValueError, solver.SolverError) as exc:
                print(f"\nSlope Case {case_no}: GVF step calculation could not be completed: {exc}")


def run_jumps(shape):
    show_menu("HYDRAULIC JUMPS", {"1": "Conjugate Depth"})
    choice = inp.get_choice("Choose calculation: ", ["1"])
    discharge = inp.get_discharge(shape)
    dims = inp.get_geometry(shape, discharge_info=discharge)

    try:
        if choice == "1":
            y1 = inp.get_positive("Enter initial supercritical depth y1 (m): ")
            res = solver.compute_conjugate_depth(shape, dims, discharge, y1)

            print(f"\nInitial depth, y1             = {res['y1']:.6f} m")
            print(f"Initial Froude number, Fr1    = {res['Fr1']:.6f}")
            print(f"Conjugate depth, y2           = {res['y2']:.6f} m")
            print(f"Post-jump Froude number, Fr2  = {res['Fr2']:.6f}")
            print(f"Energy head loss, dE          = {res['head_loss']:.6f} m")
    except (ValueError, solver.SolverError) as exc:
        print(f"\nHydraulic jump calculation could not be completed: {exc}")


def run_contractions(shape):
    show_menu("CONTRACTIONS", {
        "1": "Depth just upstream of narrow section",
        "2": "Critical depth and critical energy at narrow section",
        "3": "Bed Changes",
    })
    choice = inp.get_choice("Choose calculation: ", ["1", "2", "3"])
    discharge = inp.get_discharge(shape)

    if choice == "1":
        dims = inp.get_geometry(shape, discharge_info=discharge)
        slopes = inp.get_slope_cases()
        resistance = inp.get_roughness()
        for case_no, slope in enumerate(slopes, 1):
            try:
                yn = solver.normal_depth(shape, dims, discharge, resistance, slope)
                print(f"\nSlope Case {case_no}: S = {slope}")
                print(f"Far-upstream (normal) depth, yn = {yn:.6f} m")
            except (ValueError, solver.SolverError) as exc:
                print(f"\nSlope Case {case_no}: calculation could not be completed: {exc}")

    elif choice == "2":
        print("\nEnter narrow-section dimensions:")
        narrow_dims = inp.get_geometry(shape, discharge_info=discharge)
        try:
            yc, Ec = solver.compute_contraction_critical(shape, narrow_dims, discharge)
            print(f"\nCritical depth at narrow section, yc = {yc:.6f} m")
            print(f"Critical specific energy,          Ec = {Ec:.6f} m")
        except (ValueError, solver.SolverError) as exc:
            print(f"\nCalculation could not be completed: {exc}")

    elif choice == "3":
        slopes = inp.get_slope_cases()
        resistance = inp.get_roughness()
        dims=inp.get_geometry(shape,discharge_info=discharge)
        print("\nEnter narrow-section dimensions:")
        narrow_dims = inp.get_geometry(shape, discharge_info=discharge)
        changes = inp.get_bed_change_cases()

        for case_no, slope in enumerate(slopes,1):
            print(f"\n--- Slope Case{case_no}: S={slope} ---")
            for i, dz in enumerate(changes,1):
                label = "Bed rise" if dz > 0 else "Bed fall" if dz < 0 else "Constant bed"
                print(f"\n--- Case {i}: delta z = {dz:+.4f} m ({label}) ---")

                try:
                    res = solver.compute_contraction_bed_change(
                        shape, dims, narrow_dims, discharge,
                        slope, resistance, dz
                    )

                    print_choking_basis(
                        res["E_approach"],
                        dz,
                        res["Ec_narrow"],
                        res["choked"],
                        is_contraction=True
                    )

                    print(f"Upstream depth,       y1 = {res['y_up']:.6f} m")
                    print(f"Narrow-section depth, y2 = {res['y_narrow']:.6f} m")
                    print(f"Downstream depth,     y3 = {res['y_down']:.6f} m")

                except (ValueError, solver.SolverError) as exc:
                    print(f"\nCase {i}: Calculation could not be completed: {exc}")


def run_depressions(shape):
    show_menu("DEPRESSIONS", {"1": "Depression with no weir", "2": "Depression with weir (Stations A-E)"})
    choice = inp.get_choice("Choose calculation: ", ["1", "2"])
    discharge = inp.get_discharge(shape)
    dims = inp.get_geometry(shape, discharge_info=discharge)

    slopes = inp.get_slope_cases()
    resistance = inp.get_roughness()
    dz = inp.get_positive("Enter bed depression depth dz (m): ")

    try:
        if choice == "1":
            for case_no, slope in enumerate(slopes, 1):
                res = solver.compute_depression_no_weir(shape, dims, discharge, slope, resistance, dz)
                print(f"\n--- Slope Case {case_no}: S = {slope} ---")
                print(f"Water depth at A (Upstream, yn)     = {res['yn']:.3f} m")
                print(f"Water depth at C (In depression)     = {res['y_dep']:.3f} m")
                print(f"Water depth at E (Downstream, yn)   = {res['yn']:.3f} m")

        elif choice == "2":
            P = inp.get_weir_height()
            for case_no, slope in enumerate(slopes, 1):
                res = solver.compute_depression_with_weir_full(shape, dims, discharge, slope, resistance, dz, P)
                print(f"\n--- Slope Case {case_no}: S = {slope} ---")
                print_choking_basis(res["E_approach"], res["dz_net"], res["Ec"], res["choked"])

                print("\nStation Depths:")
                print(f"  Depth at A (Upstream backwater depth)               = {res['yA']:.3f} m")
                print(f"  Depth at B (Inside depression before weir crest)    = {res['yB']:.3f} m")
                print(f"  Depth at C (At weir crest)                          = {res['yC']:.3f} m")
                print(f"  Depth at D (Inside depression downstream of crest)  = {res['yD']:.3f} m")
                print(f"  Depth at E (Far downstream normal depth)            = {res['yE']:.3f} m")

    except (ValueError, solver.SolverError) as exc:
        print(f"\nDepression calculation could not be completed: {exc}")


def run():
    print("\nOPEN-CHANNEL HYDRAULICS ROBOT")
    while True:
        # Input order: Shape -> Category -> Calculation -> Q/q -> required geometry
        shape = select_shape()
        category = select_category()

        if category == "1":
            run_uf(shape)
        elif category == "2":
            run_weirs(shape)
        elif category == "3":
            run_jumps(shape)
        elif category == "4":
            run_contractions(shape)
        elif category == "5":
            run_depressions(shape)

        if not inp.get_yes_no("\nDo you want another calculation? (Y/N): "):
            print("Program ended.")
            break


if __name__ == "__main__":
    run()
