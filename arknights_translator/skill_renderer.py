
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP


PLACEHOLDER_PATTERN = re.compile(
    r"\{([A-Za-z_][A-Za-z0-9_@]*)(?::([^{}]+))?\}"
)

GAME_TAG_PATTERN = re.compile(r"</>|<[@$][^>]+>")


def format_number(value: float) -> str:
    number = Decimal(str(value))

    if number == number.to_integral_value():
        return str(int(number))

    return format(number.normalize(), "f")


def format_percent(value: float, precision: int) -> str:
    number = Decimal(str(value)) * 100
    quantizer = Decimal(1).scaleb(-precision)

    number = number.quantize(
        quantizer,
        rounding=ROUND_HALF_UP
    )

    if precision == 0:
        return f"{int(number)}%"

    return f"{number:.{precision}f}%"


def build_parameter_map(blackboard: list) -> dict:
    parameters = {}

    for item in blackboard or []:
        if not isinstance(item, dict):
            continue

        key = item.get("key")
        value = item.get("value")

        if key and value is not None:
            parameters[key] = value

    return parameters


def render_description(
    description: str,
    blackboard: list,
) -> tuple[str, list[str]]:

    parameters = build_parameter_map(blackboard)
    missing_keys = []

    def replace_placeholder(match):
        key = match.group(1)
        format_spec = match.group(2)

        if key not in parameters:
            missing_keys.append(key)
            return match.group(0)

        value = parameters[key]

        if format_spec:
            percent_match = re.fullmatch(
                r"(\d*)%",
                format_spec
            )

            if percent_match:
                precision = int(
                    percent_match.group(1) or "0"
                )

                return format_percent(
                    float(value),
                    precision
                )

            # Unsupported formats are left untouched.
            missing_keys.append(
                f"{key}:{format_spec}"
            )
            return match.group(0)

        try:
            return format_number(float(value))
        except (TypeError, ValueError):
            missing_keys.append(key)
            return match.group(0)

    text = PLACEHOLDER_PATTERN.sub(
        replace_placeholder,
        description or ""
    )

    text = GAME_TAG_PATTERN.sub("", text)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = "\n".join(
        line.strip()
        for line in text.split("\n")
    )

    return text.strip(), list(dict.fromkeys(missing_keys))
