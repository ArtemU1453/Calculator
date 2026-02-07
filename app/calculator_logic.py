import math

MAX_BIG_ROLL_LENGTH_M = 22000

RANGE_MATERIAL_WIDTH = (550, 910)
RANGE_ROLL_WIDTH = (20, 310)
RANGE_ROLL_LENGTH = (30, 1100)
MAX_ROLL_WIDTH_REDUCTION = 0.03
SETUP_LENGTH_M = 10


def _apply_roll_width_adjustment(useful_width_mm, roll_width_mm):
    main_count = int(useful_width_mm // roll_width_mm)
    remaining_width = useful_width_mm - main_count * roll_width_mm

    if not (RANGE_ROLL_WIDTH[0] <= remaining_width <= RANGE_ROLL_WIDTH[1]):
        return roll_width_mm, main_count, remaining_width, False

    if main_count < 1:
        return roll_width_mm, main_count, remaining_width, False

    min_width = roll_width_mm * (1 - MAX_ROLL_WIDTH_REDUCTION)
    width_needed = useful_width_mm / (main_count + 1)

    if (
        width_needed >= min_width
        and RANGE_ROLL_WIDTH[0] <= width_needed <= RANGE_ROLL_WIDTH[1]
    ):
        adjusted_width = round(width_needed, 1)
        if adjusted_width < min_width:
            return roll_width_mm, main_count, remaining_width, False
        adjusted_count = main_count + 1
        adjusted_remaining = useful_width_mm - adjusted_count * adjusted_width
        if abs(adjusted_remaining) < 1e-6:
            adjusted_remaining = 0
        return adjusted_width, adjusted_count, adjusted_remaining, True

    return roll_width_mm, main_count, remaining_width, False


def _validate_inputs(
    material_width_mm,
    useful_width_mm,
    roll_width_mm,
    roll_length_m,
    big_roll_length_m,
):
    if not (RANGE_MATERIAL_WIDTH[0] <= material_width_mm <= RANGE_MATERIAL_WIDTH[1]):
        raise ValueError("Ширина материала должна быть от 550 до 910 мм.")
    if useful_width_mm > material_width_mm:
        raise ValueError("Полезная ширина не может быть больше общей.")
    if not (RANGE_ROLL_WIDTH[0] <= roll_width_mm <= RANGE_ROLL_WIDTH[1]):
        raise ValueError("Ширина рулона должна быть от 20 до 310 мм.")
    if not (RANGE_ROLL_LENGTH[0] <= roll_length_m <= RANGE_ROLL_LENGTH[1]):
        raise ValueError("Длина рулона должна быть от 30 до 1100 м.")
    if big_roll_length_m <= 0 or big_roll_length_m > MAX_BIG_ROLL_LENGTH_M:
        raise ValueError("Намотка Джамба должна быть от 1 до 22000 м.")
    if big_roll_length_m < roll_length_m:
        raise ValueError("Намотка Джамба должна быть не меньше длины рулона.")


def calculate(
    material_width_mm,
    useful_width_mm,
    roll_width_mm,
    roll_length_m,
    big_roll_length_m,
    order_rolls,
):
    _validate_inputs(
        material_width_mm,
        useful_width_mm,
        roll_width_mm,
        roll_length_m,
        big_roll_length_m,
    )

    if order_rolls is None or int(order_rolls) <= 0:
        raise ValueError("Количество рулонов в заказе должно быть больше нуля.")
    order_rolls = int(order_rolls)

    roll_width_input_mm = roll_width_mm
    roll_width_mm, main_count, remaining_width, was_adjusted = (
        _apply_roll_width_adjustment(useful_width_mm, roll_width_mm)
    )

    additional_width = None
    if (not was_adjusted) and RANGE_ROLL_WIDTH[0] <= remaining_width <= RANGE_ROLL_WIDTH[1]:
        additional_width = remaining_width

    available_length_m = big_roll_length_m - SETUP_LENGTH_M
    if available_length_m < roll_length_m:
        raise ValueError("Недостаточная длина большого рулона с учетом 10 м расхода.")

    length_count = int(available_length_m // roll_length_m)
    length_waste_m = available_length_m - length_count * roll_length_m

    if main_count <= 0:
        raise ValueError("Недостаточно ширины для нарезки рулонов.")

    rolls_per_cycle = main_count
    cycles_needed = int(math.ceil(order_rolls / main_count))
    cycles_used = min(cycles_needed, length_count)

    total_main_rolls = main_count * cycles_used
    total_additional_rolls = cycles_used if additional_width else 0
    total_rolls = total_main_rolls + total_additional_rolls

    surplus_main_rolls = max(0, total_main_rolls - order_rolls)
    surplus_additional_rolls = total_additional_rolls if additional_width else 0
    surplus_rolls = surplus_main_rolls + surplus_additional_rolls
    shortage_rolls = max(0, order_rolls - total_main_rolls)

    used_length_m = cycles_used * roll_length_m + SETUP_LENGTH_M
    if shortage_rolls > 0:
        # If material is insufficient for the full order, count the leftover length as waste.
        used_length_m = big_roll_length_m

    total_area_m2 = (material_width_mm / 1000) * used_length_m
    useful_width_sum_mm = main_count * roll_width_mm + (additional_width or 0)
    useful_area_m2 = (useful_width_sum_mm / 1000) * (cycles_used * roll_length_m)
    waste_area_m2 = total_area_m2 - useful_area_m2
    waste_percent = (waste_area_m2 / total_area_m2) * 100 if total_area_m2 > 0 else 0

    edge_waste_mm = material_width_mm - useful_width_mm
    waste_per_side_mm = edge_waste_mm / 2 if edge_waste_mm > 0 else 0

    return {
        "material_width_mm": material_width_mm,
        "useful_width_mm": useful_width_mm,
        "roll_width_input_mm": roll_width_input_mm,
        "roll_width_mm": roll_width_mm,
        "roll_length_m": roll_length_m,
        "big_roll_length_m": big_roll_length_m,
        "order_rolls": order_rolls,
        "main_count": main_count,
        "remaining_width_mm": remaining_width,
        "additional_width_mm": additional_width,
        "was_adjusted": was_adjusted,
        "rolls_per_cycle": rolls_per_cycle,
        "cycles_needed": cycles_needed,
        "cycles_used": cycles_used,
        "used_length_m": used_length_m,
        "length_count": length_count,
        "length_waste_m": length_waste_m,
        "total_main_rolls": total_main_rolls,
        "total_additional_rolls": total_additional_rolls,
        "total_rolls": total_rolls,
        "surplus_rolls": surplus_rolls,
        "surplus_main_rolls": surplus_main_rolls,
        "surplus_additional_rolls": surplus_additional_rolls,
        "shortage_rolls": shortage_rolls,
        "total_area_m2": round(total_area_m2, 1),
        "useful_area_m2": round(useful_area_m2, 1),
        "waste_area_m2": round(waste_area_m2, 1),
        "waste_percent": round(waste_percent, 1),
        "waste_per_side_mm": waste_per_side_mm,
    }
