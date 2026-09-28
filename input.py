import math

"""
input.py
--------
User input prompts, input sanitization, and numerical range/type validation.
"""


def get_choice(prompt, valid_choices):
    while True:
        choice = input(prompt).strip()
        if choice in valid_choices:
            return choice
        print(f"Invalid option. Please choose from {valid_choices}.")


def get_positive(prompt):
    while True:
        try:
            val = float(input(prompt).strip())
            if val > 0:
                return val
            print("Value must be strictly positive.")
        except ValueError:
            print("Invalid input. Please enter a numerical value.")


def get_slope():
    while True:
        raw_input = input("Enter bed slope S (e.g., 0.001 or 0.1%): ").strip()
        try:
            if "%" in raw_input:
                val = float(raw_input.replace("%", "")) / 100.0
            else:
                val = float(raw_input)

            if val > 0:
                return val
            print("Slope must be positive.")
        except ValueError:
            print("Invalid input. Please enter a numerical value.")


def get_slope_cases():
    """Ask for the number of slope cases, then collect every slope."""
    count = get_case_count("How many slope cases do you want to analyse? ")
    slopes = []
    for i in range(1, count + 1):
        slopes.append(get_slope())
    return slopes


def get_discharge(shape):
    """Rectangular and wide rectangular allow Q or q; other shapes use Q."""
    if shape not in ("rectangular", "wide_rectangular"):
        val = get_positive("Enter total discharge Q (m^3/s): ")
        return {"kind": "Q", "value": val}

    print("\nSelect Discharge Specification:")
    print("1. Total Discharge (Q in m^3/s)")
    print("2. Unit Discharge (q in m^2/s)")
    choice = get_choice("Choose (1/2): ", ["1", "2"])

    if choice == "1":
        val = get_positive("Enter total discharge Q (m^3/s): ")
        return {"kind": "Q", "value": val}

    val = get_positive("Enter discharge per unit width q (m^2/s): ")
    return {"kind": "q", "value": val}



def get_trapezoidal_side():
    """Get trapezoidal side geometry and convert it to internal z (H:V)."""
    print("\nSpecify trapezoidal side geometry:")
    print("1. Side slope z (H:V)")
    print("2. Angle with horizontal")
    print("3. Angle with vertical")
    choice = get_choice("Choose (1/2/3): ", ["1", "2", "3"])

    if choice == "1":
        return get_positive("Enter side slope z (H:V): ")

    while True:
        try:
            angle = float(input("Enter angle (degrees): ").strip())
            if 0 < angle < 90:
                if choice == "2":
                    return 1.0 / math.tan(math.radians(angle))
                return math.tan(math.radians(angle))
            print("Angle must be greater than 0° and less than 90°.")
        except ValueError:
            print("Invalid input. Please enter a numerical angle.")

def get_geometry(shape, discharge_info=None):
    """Collect only the geometric dimensions required by the selected case.

    Rule: after Q/q is selected, a rectangular channel using q is treated per
    unit width, so bed width b is not requested. Trapezoidal b remains required
    because it is an essential part of that channel's cross-section.
    """
    dims = {}
    if discharge_info is not None and not isinstance(discharge_info, dict):
        raise ValueError("discharge_info must be a discharge dictionary or None.")
    if isinstance(discharge_info, dict):
        if discharge_info.get("kind") not in ("Q", "q"):
            raise ValueError("Invalid discharge specification.")
        value = discharge_info.get("value")
        if not isinstance(value, (int, float)) or value <= 0:
            raise ValueError("Discharge value must be a positive number.")
    unit_discharge = isinstance(discharge_info, dict) and discharge_info.get("kind") == "q"

    if shape == "rectangular":
        if unit_discharge:
            print("\n[Unit discharge q selected -> rectangular channel analysed per unit width; b is not required.]" )
            dims["b"] = 1.0
        else:
            dims["b"] = get_positive("Enter channel bed width b (m): ")

    elif shape == "wide_rectangular":
        if unit_discharge:
            print("\n[Unit discharge q selected -> wide rectangular channel per unit width.]" )
            dims["b"] = 1.0
        else:
            dims["b"] = get_positive("Enter channel bed width b (m): ")

    elif shape == "triangular":
        dims["theta"] = math.radians(get_positive("Enter semi-vertical angle theta (degrees): "))

    elif shape == "trapezoidal":
        dims["b"] = get_positive("Enter bottom width b (m): ")
        dims["z"] = get_trapezoidal_side()

    elif shape in ("circular", "semi_circular"):
        dims["d"] = get_positive("Enter channel diameter d (m): ")

    return dims


def get_roughness():
    print("\nSelect Roughness Coefficients:")
    print("1. Manning's n")
    print("2. Chezy's C")
    choice = get_choice("Choose roughness specification (1/2): ", ["1", "2"])
    if choice == "1":
        val = get_positive("Enter Manning's n: ")
        return {"kind": "n", "value": val}
    else:
        val = get_positive("Enter Chezy's C: ")
        return {"kind": "C", "value": val}


def get_case_count(prompt="Enter number of cases: "):
    while True:
        try:
            val = int(input(prompt).strip())
            if val > 0:
                return val
            print("Count must be an integer greater than zero.")
        except ValueError:
            print("Invalid input. Please enter an integer.")


def get_weir_height():
    return get_positive("Enter weir height P (m): ")


def get_limiting_weir_height():
    return get_positive("Enter limiting weir height Plim (m): ")


def get_target_rise():
    return get_positive("Enter target upstream rise in water depth (m): ")


def get_bed_change_cases():
    count = get_case_count("How many bed change cases do you want to evaluate? ")
    cases = []
    print("Enter delta z for each case (positive for bed rise, negative for bed fall):")
    for i in range(1, count + 1):
        while True:
            try:
                val = float(input(f"Case {i} delta z (m): ").strip())
                cases.append(val)
                break
            except ValueError:
                print("Invalid input. Please enter a numerical value.")
    return cases


def get_yes_no(prompt):
    while True:
        ans = input(prompt).strip().upper()
        if ans in ("Y", "YES"):
            return True
        if ans in ("N", "NO"):
            return False
        print("Please enter Y or N.")
