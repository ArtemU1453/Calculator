import math

MAX_BIG_ROLL_LENGTH_M = 22000

RANGE_MATERIAL_WIDTH = (550, 910)
RANGE_ROLL_WIDTH = (20, 310)
RANGE_ROLL_LENGTH = (30, 1100)
MAX_ROLL_WIDTH_REDUCTION = 0.03
SETUP_LENGTH_M = 10


def _cycles_per_hour_by_width(roll_width_mm):
    if 25 <= roll_width_mm < 45:
        return 11
    if 45 <= roll_width_mm <= 150:
        return 12
    return None


def _cycles_per_hour_by_length(roll_length_m):
    if roll_length_m <= 300:
        return 12
    if roll_length_m <= 450:
        return 11
    if roll_length_m <= 600:
        return 10
    return 8


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
    additional_width_mm=None,
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
    additional_width_override = None
    if additional_width_mm is not None:
        try:
            additional_width_override = float(additional_width_mm)
        except (TypeError, ValueError):
            raise ValueError("\u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0439 \u0434\u043e\u043f. \u0440\u0430\u0437\u043c\u0435\u0440.")
        if additional_width_override <= 0:
            additional_width_override = None
        elif not (
            RANGE_ROLL_WIDTH[0] <= additional_width_override <= RANGE_ROLL_WIDTH[1]
        ):
            raise ValueError("\u0414\u043e\u043f. \u0440\u0430\u0437\u043c\u0435\u0440 \u0434\u043e\u043b\u0436\u0435\u043d \u0431\u044b\u0442\u044c \u043e\u0442 20 \u0434\u043e 310 \u043c\u043c.")

    if additional_width_override is None:
        roll_width_mm, main_count, remaining_width, was_adjusted = (
            _apply_roll_width_adjustment(useful_width_mm, roll_width_mm)
        )
    else:
        main_count = int(useful_width_mm // roll_width_mm)
        remaining_width = useful_width_mm - main_count * roll_width_mm
        was_adjusted = False

    additional_width = None
    if additional_width_override is not None:
        if additional_width_override - remaining_width > 1e-6:
            raise ValueError(
                f"\u0414\u043e\u043f. \u0440\u0430\u0437\u043c\u0435\u0440 {additional_width_override:.1f} \u043c\u043c "
                f"\u0431\u043e\u043b\u044c\u0448\u0435 \u043e\u0441\u0442\u0430\u0442\u043a\u0430 {remaining_width:.1f} \u043c\u043c."
            )
        additional_width = additional_width_override
    elif (not was_adjusted) and RANGE_ROLL_WIDTH[0] <= remaining_width <= RANGE_ROLL_WIDTH[1]:
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

    width_rate = _cycles_per_hour_by_width(roll_width_mm)
    length_rate = _cycles_per_hour_by_length(roll_length_m)
    if width_rate is None:
        cycles_per_hour = length_rate
    else:
        cycles_per_hour = min(width_rate, length_rate)
    estimated_hours = cycles_needed / cycles_per_hour if cycles_per_hour else None

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
        "cycles_per_hour": cycles_per_hour,
        "estimated_hours": estimated_hours,
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
