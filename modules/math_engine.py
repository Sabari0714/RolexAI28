"""
Rolex AI Local Mathematics & Engineering Engine.

Design goals:
- 100% local deterministic calculations
- No internet
- No external AI
- No eval()
- AST whitelist for arithmetic expressions
- Natural-language calculation support
- Electrical, RPM, mechanical and unit calculations
"""

import ast
import math
import operator
import re


# ============================================================
# SAFE ARITHMETIC
# ============================================================

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_FUNCTIONS = {
    "sqrt": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(x) ** (1.0 / 3.0), x),
    "abs": abs,
    "sin": lambda x: math.sin(math.radians(x)),
    "cos": lambda x: math.cos(math.radians(x)),
    "tan": lambda x: math.tan(math.radians(x)),
    "asin": lambda x: math.degrees(math.asin(x)),
    "acos": lambda x: math.degrees(math.acos(x)),
    "atan": lambda x: math.degrees(math.atan(x)),
    "log": math.log10,
    "ln": math.log,
    "exp": math.exp,
}

_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


class MathEngineError(ValueError):
    pass


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise MathEngineError("Boolean values are not allowed")
        if isinstance(node.value, (int, float)):
            if not math.isfinite(float(node.value)):
                raise MathEngineError("Invalid number")
            return node.value
        raise MathEngineError("Invalid constant")

    if isinstance(node, ast.Name):
        name = node.id.lower()
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        raise MathEngineError("Unknown constant")

    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if not op:
            raise MathEngineError("Operator not allowed")
        return op(_safe_eval(node.operand))

    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if not op:
            raise MathEngineError("Operator not allowed")

        left = _safe_eval(node.left)
        right = _safe_eval(node.right)

        if isinstance(node.op, ast.Pow):
            if abs(float(right)) > 1000:
                raise MathEngineError("Exponent too large")

        try:
            value = op(left, right)
        except (ZeroDivisionError, OverflowError, ValueError):
            raise MathEngineError("Invalid mathematical operation")

        if not math.isfinite(float(value)):
            raise MathEngineError("Result is not finite")

        return value

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise MathEngineError("Function not allowed")

        fn = _FUNCTIONS.get(node.func.id.lower())

        if fn is None:
            raise MathEngineError("Unknown function")

        if len(node.args) != 1:
            raise MathEngineError("Function requires one argument")

        try:
            value = fn(_safe_eval(node.args[0]))
        except (ValueError, ZeroDivisionError, OverflowError):
            raise MathEngineError("Invalid function input")

        if not math.isfinite(float(value)):
            raise MathEngineError("Result is not finite")

        return value

    raise MathEngineError("Expression not allowed")


def safe_expression(expression):
    expression = expression.strip()

    if not expression:
        raise MathEngineError("Empty expression")

    if len(expression) > 300:
        raise MathEngineError("Expression too long")

    expression = expression.replace(",", "")
    expression = expression.replace("×", "*")
    expression = expression.replace("÷", "/")
    expression = expression.replace("−", "-")
    expression = expression.replace("–", "-")
    expression = expression.replace("^", "**")

    # √25 -> sqrt(25)
    expression = re.sub(
        r"√\s*(\d+(?:\.\d+)?)",
        r"sqrt(\1)",
        expression,
    )

    # Reject characters that cannot belong to our language.
    if not re.fullmatch(
        r"[0-9A-Za-z_+\-*/().,%\s]+",
        expression,
    ):
        raise MathEngineError("Unsupported characters")

    tree = ast.parse(expression, mode="eval")
    return _safe_eval(tree)


# ============================================================
# FORMATTING
# ============================================================

def _fmt(value):
    value = float(value)

    if not math.isfinite(value):
        raise MathEngineError("Invalid result")

    if abs(value) < 1e-12:
        value = 0.0

    if value.is_integer():
        return str(int(value))

    return f"{value:.12g}"


def _result(label, value, unit=""):
    text = _fmt(value)

    if unit:
        return f"{label}: {text} {unit}"

    return f"{label}: {text}"


# ============================================================
# PERCENTAGE
# ============================================================

def _percentage(q):
    m = re.fullmatch(
        r"\s*([+-]?\d+(?:\.\d+)?)\s*%\s*(?:of|in)\s*"
        r"([+-]?\d+(?:\.\d+)?)\s*",
        q,
        re.I,
    )

    if m:
        percent = float(m.group(1))
        base = float(m.group(2))
        return _result(
            "Percentage",
            percent * base / 100,
        )

    m = re.fullmatch(
        r"\s*([+-]?\d+(?:\.\d+)?)\s*%\s*",
        q,
    )

    if m:
        return _result(
            "Percentage",
            float(m.group(1)) / 100,
        )

    m = re.search(
        r"percentage\s+(?:change|increase|decrease)\s+from\s+"
        r"([+-]?\d+(?:\.\d+)?)\s+to\s+"
        r"([+-]?\d+(?:\.\d+)?)",
        q,
        re.I,
    )

    if m:
        old = float(m.group(1))
        new = float(m.group(2))

        if old == 0:
            raise MathEngineError("Cannot calculate percentage change from zero")

        change = ((new - old) / abs(old)) * 100

        return _result("Percentage change", change, "%")

    return None


# ============================================================
# ELECTRICAL
# ============================================================

def _number_unit(q, unit):
    # unit is a raw regex pattern, e.g. (?:v|volt|volts)
    pattern = r"([+-]?\d+(?:\.\d+)?)\s*" + unit + r"(?=\s|$|[^A-Za-z])"
    m = re.search(pattern, q, re.I)
    return float(m.group(1)) if m else None

def _electrical(q):
    voltage = _number_unit(q, r"(?:v|volt|volts)")
    current = _number_unit(q, r"(?:a|amp|amps|ampere|amperes)")
    resistance = _number_unit(q, r"(?:ohm|ohms|Ω)")
    power = _number_unit(q, r"(?:w|watt|watts)")
    time = _number_unit(q, r"(?:s|sec|secs|second|seconds|h|hr|hour|hours)")

    low = q.lower()

    # Explicit electrical question keywords.
    electrical_hint = any(
        word in low
        for word in (
            "voltage",
            "current",
            "resistance",
            "resistor",
            "power",
            "ohm",
            "watt",
            "electrical",
            "electric",
        )
    )

    if not electrical_hint and not any(
        x is not None
        for x in (voltage, current, resistance, power)
    ):
        return None

    # Respect the quantity explicitly requested by the user.
    if voltage is not None and current is not None:
        if re.search(r"\bresistance\b|\bresistor\b|\bohm\b|Ω", low):
            if current != 0:
                return _result("Resistance", voltage / current, "Ω")

        if re.search(r"\bpower\b|\bwatt\b", low):
            return _result("Power", voltage * current, "W")

    # V = I * R
    if current is not None and resistance is not None:
        return _result(
            "Voltage",
            current * resistance,
            "V",
        )

    if voltage is not None and current is not None:
        return _result(
            "Power",
            voltage * current,
            "W",
        )

    if voltage is not None and resistance is not None:
        return _result(
            "Current",
            voltage / resistance,
            "A",
        )

    if voltage is not None and power is not None:
        return _result(
            "Current",
            power / voltage,
            "A",
        )

    if current is not None and power is not None:
        return _result(
            "Voltage",
            power / current,
            "V",
        )

    if power is not None and current is not None:
        return _result(
            "Resistance",
            power / (current * current),
            "Ω",
        )

    if power is not None and voltage is not None:
        return _result(
            "Resistance",
            (voltage * voltage) / power,
            "Ω",
        )

    # Energy = power × time.
    if power is not None and time is not None:
        seconds = time

        if re.search(r"\b(?:h|hr|hour|hours)\b", q, re.I):
            seconds *= 3600

        return _result(
            "Energy",
            power * seconds,
            "J",
        )

    return None


# ============================================================
# RPM / ROTATIONAL
# ============================================================

def _rpm(q):
    low = q.lower()

    rpm = _number_unit(q, r"(?:rpm|rev/min|revolutions?\s*/?\s*min)")
    rps = _number_unit(q, r"(?:rps|rev/s|revolutions?\s*/?\s*s)")
    hz = _number_unit(q, r"(?:hz|hertz)")

    if rpm is not None:
        if "rps" in low or "revolutions per second" in low:
            return _result("RPS", rpm / 60, "r/s")

        return _result("RPM", rpm, "RPM")

    if rps is not None:
        return _result("RPM", rps * 60, "RPM")

    if hz is not None and any(
        x in low for x in ("rpm", "revolution", "rotation")
    ):
        return _result("RPM", hz * 60, "RPM")

    # "1500 rpm to rps"
    m = re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*rpm.*\bto\b.*rps",
        low,
    )

    if m:
        return _result(
            "RPS",
            float(m.group(1)) / 60,
            "r/s",
        )

    # Gear/pulley ratio.
    m = re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*rpm.*"
        r"(?:ratio|gear ratio|pulley ratio)\s*"
        r"([+-]?\d+(?:\.\d+)?)\s*[:/]\s*"
        r"([+-]?\d+(?:\.\d+)?)",
        low,
    )

    if m:
        input_rpm = float(m.group(1))
        a = float(m.group(2))
        b = float(m.group(3))

        if b == 0:
            raise MathEngineError("Ratio denominator cannot be zero")

        return _result(
            "Output RPM",
            input_rpm * a / b,
            "RPM",
        )

    return None


# ============================================================
# MECHANICAL
# ============================================================

def _mechanical(q):
    low = q.lower()

    mass = _number_unit(q, r"(?:kg|kilogram|kilograms)")
    acceleration = _number_unit(
        q,
        r"(?:m/s2|m/s²|m/s\^2|meter/s2|metre/s2)",
    )
    velocity = _number_unit(
        q,
        r"(?:m/s|mps|meter/second|metre/second)",
    )
    distance = _number_unit(
        q,
        r"(?:m|meter|meters|metre|metres)",
    )
    force = _number_unit(
        q,
        r"(?:n|newton|newtons)",
    )
    torque = _number_unit(
        q,
        r"(?:nm|n-m|newton-meter|newton-metre)",
    )
    power = _number_unit(
        q,
        r"(?:kw|kilowatt|kilowatts|w|watt|watts)",
    )

    if "force" in low and mass is not None and acceleration is not None:
        return _result(
            "Force",
            mass * acceleration,
            "N",
        )

    if "distance" in low and velocity is not None and acceleration is not None:
        # s = ut + 1/2 at² cannot be solved without time.
        return None

    # P = torque × angular velocity
    rpm = _number_unit(q, r"(?:rpm)")

    if torque is not None and rpm is not None:
        omega = 2 * math.pi * rpm / 60
        return _result(
            "Mechanical power",
            torque * omega,
            "W",
        )

    # Torque from power and RPM.
    if power is not None and rpm is not None:
        if "kw" in low or "kilowatt" in low:
            watts = power * 1000
        else:
            watts = power

        omega = 2 * math.pi * rpm / 60

        if omega == 0:
            raise MathEngineError("RPM cannot be zero")

        return _result(
            "Torque",
            watts / omega,
            "N·m",
        )

    # Efficiency.
    m = re.search(
        r"(?:efficiency|eta).*?"
        r"([+-]?\d+(?:\.\d+)?)\s*(?:input|in).*?"
        r"([+-]?\d+(?:\.\d+)?)\s*(?:output|out)",
        low,
    )

    if m:
        input_power = float(m.group(1))
        output_power = float(m.group(2))

        if input_power == 0:
            raise MathEngineError("Input cannot be zero")

        return _result(
            "Efficiency",
            output_power / input_power * 100,
            "%",
        )

    return None


# ============================================================
# GEOMETRY
# ============================================================

def _geometry(q):
    low = q.lower()

    nums = [
        float(x)
        for x in re.findall(
            r"[+-]?\d+(?:\.\d+)?",
            low,
        )
    ]

    if "area" in low and "circle" in low and nums:
        r = nums[0]
        return _result("Circle area", math.pi * r * r)

    if "circumference" in low and "circle" in low and nums:
        r = nums[0]
        return _result(
            "Circumference",
            2 * math.pi * r,
        )

    if "area" in low and "rectangle" in low and len(nums) >= 2:
        return _result(
            "Rectangle area",
            nums[0] * nums[1],
        )

    if "volume" in low and "cylinder" in low and len(nums) >= 2:
        r, h = nums[0], nums[1]
        return _result(
            "Cylinder volume",
            math.pi * r * r * h,
        )

    if "volume" in low and "sphere" in low and nums:
        r = nums[0]
        return _result(
            "Sphere volume",
            4 * math.pi * r**3 / 3,
        )

    if "hypotenuse" in low and len(nums) >= 2:
        return _result(
            "Hypotenuse",
            math.sqrt(nums[0] ** 2 + nums[1] ** 2),
        )

    return None


# ============================================================
# UNIT CONVERSION
# ============================================================

_LENGTH = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "km": 1000.0,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    "ft": 0.3048,
    "feet": 0.3048,
    "foot": 0.3048,
    "yd": 0.9144,
    "mile": 1609.344,
    "miles": 1609.344,
}

_MASS = {
    "mg": 0.001,
    "g": 1.0,
    "kg": 1000.0,
    "lb": 453.59237,
    "lbs": 453.59237,
}

_ENERGY = {
    "j": 1.0,
    "kj": 1000.0,
    "mj": 1_000_000.0,
    "wh": 3600.0,
    "kwh": 3_600_000.0,
}

_POWER = {
    "w": 1.0,
    "kw": 1000.0,
    "mw": 1_000_000.0,
}

_PRESSURE = {
    "pa": 1.0,
    "kpa": 1000.0,
    "mpa": 1_000_000.0,
    "bar": 100000.0,
    "psi": 6894.757293168,
}


def _convert(q):
    low = q.lower().strip()

    m = re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*"
        r"([a-zA-Z]+)\s+(?:to|in)\s+"
        r"([a-zA-Z]+)",
        low,
    )

    if not m:
        return None

    value = float(m.group(1))
    source = m.group(2).lower()
    target = m.group(3).lower()

    groups = (
        ("length", _LENGTH),
        ("mass", _MASS),
        ("energy", _ENERGY),
        ("power", _POWER),
        ("pressure", _PRESSURE),
    )

    for name, table in groups:
        if source in table and target in table:
            base = value * table[source]
            result = base / table[target]

            return _result(
                "Conversion",
                result,
                target,
            )

    # Temperature.
    if source in ("c", "celsius") and target in ("f", "fahrenheit"):
        return _result(
            "Temperature",
            value * 9 / 5 + 32,
            "°F",
        )

    if source in ("f", "fahrenheit") and target in ("c", "celsius"):
        return _result(
            "Temperature",
            (value - 32) * 5 / 9,
            "°C",
        )

    if source in ("c", "celsius") and target in ("k", "kelvin"):
        return _result(
            "Temperature",
            value + 273.15,
            "K",
        )

    if source in ("k", "kelvin") and target in ("c", "celsius"):
        return _result(
            "Temperature",
            value - 273.15,
            "°C",
        )

    # RPM / RPS.
    if source == "rpm" and target in ("rps", "hz"):
        return _result("Conversion", value / 60, target)

    if source in ("rps", "hz") and target == "rpm":
        return _result("Conversion", value * 60, "RPM")

    return None


# ============================================================
# NATURAL LANGUAGE NORMALIZATION
# ============================================================

def _normalize_math_words(q):
    text = q.lower().strip()

    replacements = (
        ("multiplied by", "*"),
        ("multiply by", "*"),
        ("times", "*"),
        ("divided by", "/"),
        ("divide by", "/"),
        ("plus", "+"),
        ("minus", "-"),
        ("subtract", "-"),
        ("added to", "+"),
        ("into", "*"),
    )

    for old, new in replacements:
        text = text.replace(old, f" {new} ")

    text = re.sub(
        r"\bwhat is\b",
        "",
        text,
    )

    text = re.sub(
        r"\bcalculate\b",
        "",
        text,
    )

    text = re.sub(
        r"\bcompute\b",
        "",
        text,
    )

    text = re.sub(
        r"\bsolve\b",
        "",
        text,
    )

    text = text.replace("×", "*")
    text = text.replace("÷", "/")
    text = text.replace("^", "**")

    return " ".join(text.split())


# ============================================================
# MAIN ENTRY
# ============================================================

def calculate(prompt):
    """
    Return a deterministic local calculation answer.

    Returns None when the input is not confidently recognized
    as a mathematical/engineering request.
    """

    if not isinstance(prompt, str):
        return None

    original = prompt.strip()

    if not original or len(original) > 500:
        return None

    q = _normalize_math_words(original)

    # Explicit percentage first.
    try:
        value = _percentage(q)
        if value is not None:
            return value
    except MathEngineError:
        return None

    # RPM / rotational formulas.
    # Check before generic unit conversion so requests such as
    # "1500 rpm to rps" use the dedicated RPM result format.
    try:
        value = _rpm(q)
        if value is not None:
            return value
    except MathEngineError:
        return None

    # Unit conversion.
    try:
        value = _convert(q)
        if value is not None:
            return value
    except MathEngineError:
        return None

    # Electrical formulas.
    try:
        value = _electrical(q)
        if value is not None:
            return value
    except (MathEngineError, ZeroDivisionError):
        return None

    # Mechanical formulas.
    try:
        value = _mechanical(q)
        if value is not None:
            return value
    except MathEngineError:
        return None

    # Geometry.
    try:
        value = _geometry(q)
        if value is not None:
            return value
    except MathEngineError:
        return None

    # Pure arithmetic expression.
    expression = q.strip().rstrip("?!.")

    # Remove common trailing words.
    expression = re.sub(
        r"\b(answer|result)\s*$",
        "",
        expression,
        flags=re.I,
    ).strip()

    # Do not interpret arbitrary prose as math.
    if not re.fullmatch(
        r"[0-9A-Za-z_+\-*/().,%\s×÷^√]+",
        expression,
    ):
        return None

    # Require a number and an actual math signal.
    if not re.search(r"\d", expression):
        return None

    if not re.search(
        r"[+\-*/%^×÷^√()]|\b(?:sqrt|cbrt|sin|cos|tan|asin|acos|atan|log|ln|abs|exp|pi|e)\b",
        expression,
        re.I,
    ):
        return None

    try:
        return _result(
            "Answer",
            safe_expression(expression),
        )
    except Exception:
        return None



# ============================================================
# GIANT LOCAL CALCULATION ENGINE
# ============================================================
# Deterministic local calculations.
# This layer NEVER calls internet services or external AI.
# ============================================================

def _giant_number(q, pattern):
    m = re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*" + pattern,
        q,
        re.I,
    )
    return float(m.group(1)) if m else None


def _giant_numbers(q):
    return [
        float(x)
        for x in re.findall(
            r"(?<![A-Za-z])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?",
            q,
        )
    ]


def _giant_stats(q):
    low = q.lower()

    # mean / average
    m = re.search(
        r"(?:mean|average)\s+(?:of\s+)?(.+)",
        low,
        re.I,
    )
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            return _result("Mean", sum(nums) / len(nums))

    # median
    m = re.search(r"median\s+(?:of\s+)?(.+)", low, re.I)
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            nums.sort()
            n = len(nums)
            value = (
                nums[n // 2]
                if n % 2
                else (nums[n // 2 - 1] + nums[n // 2]) / 2
            )
            return _result("Median", value)

    # sum
    m = re.search(r"(?:sum|total)\s+(?:of\s+)?(.+)", low, re.I)
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            return _result("Sum", sum(nums))

    # minimum
    m = re.search(r"(?:minimum|min)\s+(?:of\s+)?(.+)", low, re.I)
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            return _result("Minimum", min(nums))

    # maximum
    m = re.search(r"(?:maximum|max)\s+(?:of\s+)?(.+)", low, re.I)
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            return _result("Maximum", max(nums))

    # range
    m = re.search(r"range\s+(?:of\s+)?(.+)", low, re.I)
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            return _result("Range", max(nums) - min(nums))

    # variance
    m = re.search(r"variance\s+(?:of\s+)?(.+)", low, re.I)
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            mean = sum(nums) / len(nums)
            return _result(
                "Variance",
                sum((x - mean) ** 2 for x in nums) / len(nums),
            )

    # standard deviation
    m = re.search(
        r"(?:standard\s+deviation|std(?:ev)?|sd)\s+(?:of\s+)?(.+)",
        low,
        re.I,
    )
    if m:
        nums = _giant_numbers(m.group(1))
        if nums:
            mean = sum(nums) / len(nums)
            variance = sum((x - mean) ** 2 for x in nums) / len(nums)
            return _result("Standard deviation", math.sqrt(variance))

    return None


def _giant_combinatorics(q):
    low = q.lower()

    m = re.search(
        r"(\d+)\s*(?:choose|combination|combinations|c)\s*(\d+)",
        low,
    )
    if m:
        n, r = int(m.group(1)), int(m.group(2))
        if r < 0 or r > n:
            raise MathEngineError("Invalid combination")
        return _result("Combination", math.comb(n, r))

    m = re.search(
        r"(\d+)\s*(?:permutation|permutations|permute|p)\s*(\d+)",
        low,
    )
    if m:
        n, r = int(m.group(1)), int(m.group(2))
        if r < 0 or r > n:
            raise MathEngineError("Invalid permutation")
        return _result("Permutation", math.perm(n, r))

    m = re.fullmatch(
        r"\s*(?:factorial\s*)?(\d+)\s*!\s*",
        low,
    )
    if m:
        n = int(m.group(1))
        if n > 10000:
            raise MathEngineError("Factorial too large")
        return _result("Factorial", math.factorial(n))

    m = re.fullmatch(
        r"\s*factorial\s+(\d+)\s*",
        low,
    )
    if m:
        n = int(m.group(1))
        if n > 10000:
            raise MathEngineError("Factorial too large")
        return _result("Factorial", math.factorial(n))

    m = re.search(
        r"(?:gcd|greatest\s+common\s+divisor)\s+(.+)",
        low,
    )
    if m:
        nums = [int(x) for x in _giant_numbers(m.group(1))]
        if len(nums) >= 2:
            return _result(
                "GCD",
                math.gcd(*nums),
            )

    m = re.search(
        r"(?:lcm|least\s+common\s+multiple)\s+(.+)",
        low,
    )
    if m:
        nums = [int(x) for x in _giant_numbers(m.group(1))]
        if len(nums) >= 2:
            return _result(
                "LCM",
                math.lcm(*nums),
            )

    return None


def _giant_finance(q):
    low = q.lower()
    nums = _giant_numbers(low)

    # Simple interest: principal, rate, time
    if "simple interest" in low and len(nums) >= 3:
        p, r, t = nums[:3]
        interest = p * r * t / 100
        return _result("Simple interest", interest)

    # Compound interest
    if "compound interest" in low and len(nums) >= 3:
        p, r, t = nums[:3]
        amount = p * (1 + r / 100) ** t
        return _result("Compound interest", amount - p)

    # Compound amount
    if "compound amount" in low and len(nums) >= 3:
        p, r, t = nums[:3]
        amount = p * (1 + r / 100) ** t
        return _result("Compound amount", amount)

    return None


def _giant_physics(q):
    low = q.lower()

    mass = _giant_number(q, r"(?:kg|kilogram|kilograms)")
    acceleration = _giant_number(
        q,
        r"(?:m/s2|m/s²|m/s\^2)",
    )
    velocity = _giant_number(
        q,
        r"(?:m/s|mps|meter/second|metre/second)",
    )
    distance = _giant_number(
        q,
        r"(?:m|meter|meters|metre|metres)",
    )
    force = _giant_number(
        q,
        r"(?:n|newton|newtons)",
    )
    time = _giant_number(
        q,
        r"(?:s|sec|secs|second|seconds)",
    )

    if "force" in low and mass is not None and acceleration is not None:
        return _result("Force", mass * acceleration, "N")

    if "momentum" in low and mass is not None and velocity is not None:
        return _result("Momentum", mass * velocity, "kg·m/s")

    if (
        "kinetic energy" in low
        and mass is not None
        and velocity is not None
    ):
        return _result(
            "Kinetic energy",
            0.5 * mass * velocity ** 2,
            "J",
        )

    if (
        "work" in low
        and force is not None
        and distance is not None
    ):
        return _result(
            "Work",
            force * distance,
            "J",
        )

    if (
        "power" in low
        and force is not None
        and velocity is not None
    ):
        return _result(
            "Power",
            force * velocity,
            "W",
        )

    if "density" in low:
        m = _giant_number(
            q,
            r"(?:kg|kilogram|kilograms)",
        )
        v = _giant_number(
            q,
            r"(?:m3|m³|cubic\s*m)",
        )
        if m is not None and v is not None and v != 0:
            return _result("Density", m / v, "kg/m³")

    return None


def _giant_geometry(q):
    low = q.lower()
    nums = _giant_numbers(low)

    if not nums:
        return None

    if "square" in low:
        a = nums[0]
        if "area" in low:
            return _result("Square area", a * a)
        if "perimeter" in low:
            return _result("Square perimeter", 4 * a)

    if "triangle" in low:
        if "area" in low and len(nums) >= 2:
            return _result(
                "Triangle area",
                0.5 * nums[0] * nums[1],
            )

        if "perimeter" in low and len(nums) >= 3:
            return _result(
                "Triangle perimeter",
                sum(nums[:3]),
            )

    if "cube" in low:
        a = nums[0]
        if "volume" in low:
            return _result("Cube volume", a ** 3)
        if "surface" in low:
            return _result("Cube surface area", 6 * a ** 2)

    if "cuboid" in low or "rectangular prism" in low:
        if len(nums) >= 3:
            a, b, c = nums[:3]
            if "volume" in low:
                return _result("Cuboid volume", a * b * c)
            if "surface" in low:
                return _result(
                    "Cuboid surface area",
                    2 * (a*b + b*c + a*c),
                )

    if "cone" in low and "volume" in low and len(nums) >= 2:
        r, h = nums[:2]
        return _result(
            "Cone volume",
            math.pi * r * r * h / 3,
        )

    return None



def _giant_mechanical(q):
    low = q.lower()

    torque = _giant_number(
        q,
        r"(?:nm|n-m|newton-meter|newton-metre)",
    )

    rpm = _giant_number(
        q,
        r"(?:rpm|rev/min|revolutions?\s*/?\s*min)",
    )

    power_kw = _giant_number(
        q,
        r"(?:kw|kilowatt|kilowatts)",
    )

    power_w = _giant_number(
        q,
        r"(?:w|watt|watts)",
    )

    # Torque + RPM -> mechanical power
    if torque is not None and rpm is not None and (
        "power" in low or "watt" in low
    ):
        omega = 2 * math.pi * rpm / 60
        return _result(
            "Mechanical power",
            torque * omega,
            "W",
        )

    # Power + RPM -> torque
    if rpm is not None and (
        power_kw is not None or power_w is not None
    ) and (
        "torque" in low or "moment" in low
    ):
        watts = (
            power_kw * 1000
            if power_kw is not None
            else power_w
        )

        omega = 2 * math.pi * rpm / 60

        if omega == 0:
            raise MathEngineError("RPM cannot be zero")

        return _result(
            "Torque",
            watts / omega,
            "N·m",
        )

    # Explicit torque value
    if torque is not None and "torque" in low:
        return _result("Torque", torque, "N·m")

    # RPM -> angular velocity
    if rpm is not None and (
        "angular velocity" in low
        or "angular speed" in low
        or "omega" in low
    ):
        omega = 2 * math.pi * rpm / 60
        return _result("Angular velocity", omega, "rad/s")

    return None


def _giant_roots(q):
    low = q.lower()

    m = re.search(
        r"(?:nth\s+root|root)\s+(\d+)\s+(?:of|from)\s+"
        r"([+-]?\d+(?:\.\d+)?)",
        low,
    )
    if m:
        n = int(m.group(1))
        value = float(m.group(2))
        if n <= 0:
            raise MathEngineError("Root index must be positive")
        if value < 0 and n % 2 == 0:
            raise MathEngineError("Even root of negative number")
        result = (
            math.copysign(abs(value) ** (1 / n), value)
            if value < 0
            else value ** (1 / n)
        )
        return _result("Root", result)

    return None


def _giant_angle(q):
    low = q.lower()
    nums = _giant_numbers(low)

    if not nums:
        return None

    if "radian" in low and "degree" in low:
        if "to degree" in low or "to degrees" in low:
            return _result("Angle", math.degrees(nums[0]), "°")

        if "to radian" in low or "to radians" in low:
            return _result("Angle", math.radians(nums[0]), "rad")

    return None


def _giant_speed(q):
    low = q.lower()

    d = _giant_number(
        q,
        r"(?:km|kilometer|kilometers)",
    )
    h = _giant_number(
        q,
        r"(?:h|hr|hour|hours)",
    )

    if "speed" in low and d is not None and h is not None:
        return _result("Speed", d / h, "km/h")

    return None


# ============================================================
# GIANT CALCULATE DISPATCH
# ============================================================

_GIANT_OLD_CALCULATE = calculate


def calculate(prompt):
    """
    Rolex AI Giant Local Calculation Engine.

    Priority:
        1. deterministic giant formulas
        2. existing proven math engine
        3. None for unsupported/non-math input

    No network.
    No external AI.
    No arbitrary eval().
    """

    if not isinstance(prompt, str):
        return None

    original = prompt.strip()

    if not original or len(original) > 500:
        return None

    q = _normalize_math_words(original)

    # Advanced math families.
    for handler in (
        _giant_combinatorics,
        _giant_stats,
        _giant_finance,
        _giant_physics,
        _giant_mechanical,
        _giant_geometry,
        _giant_roots,
        _giant_angle,
        _giant_speed,
    ):
        try:
            result = handler(q)
            if result is not None:
                return result
        except (MathEngineError, ZeroDivisionError, ValueError, OverflowError):
            return None

    # Existing 24/24-tested engine remains the final deterministic layer.
    return _GIANT_OLD_CALCULATE(original)

# ============================================================
# ROLEX AI — ALGEBRA + ADVANCED MATHEMATICS LAYER
# Local deterministic calculation only
# ============================================================

import math as _math
import re as _re


def _algebra_clean(expr):
    expr = expr.strip()
    expr = expr.replace("−", "-").replace("–", "-")
    expr = expr.replace("×", "*").replace("·", "*")
    expr = expr.replace("^", "**")
    expr = _re.sub(r"\s+", "", expr)
    return expr


def _algebra_poly(expr):
    """
    Convert a limited algebra expression into:
        a*x^2 + b*x + c
    Supports:
        x
        -x
        2x
        2*x
        x^2
        2x^2
        x+5
        3x-7
        simple parentheses are handled by expansion where possible.

    Returns (a, b, c) or None.
    """
    expr = _algebra_clean(expr)

    if not expr:
        return None

    # Reject unsupported symbols/functions.
    if _re.search(r"[^0-9xX+*/().\-]", expr):
        return None

    expr = expr.lower()

    # Handle simple multiplication of a numeric coefficient and x.
    # Expand only simple products such as 2*(x+3).
    m = _re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\*([^()]+)", expr)
    if m:
        k = float(m.group(1))
        inner = _algebra_poly(m.group(2))
        if inner is not None:
            return (
                k * inner[0],
                k * inner[1],
                k * inner[2],
            )

    # Remove harmless outer parentheses.
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        valid = True
        for i, ch in enumerate(expr):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(expr) - 1:
                    valid = False
                    break
        if valid:
            expr = expr[1:-1]
        else:
            break

    # Convert implicit multiplication: 2x -> 2*x, x2 is rejected.
    expr = _re.sub(r"(\d)(x)", r"\1*x", expr)

    # Split into signed terms.
    terms = _re.findall(r"[+-]?[^+-]+", expr)

    if not terms:
        return None

    a = b = c = 0.0

    for term in terms:
        if not term:
            continue

        # Remove simple parentheses around a term.
        term = term.strip("()")

        # x^2
        m = _re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d+)?)?)\*?x\*\*2",
            term
        )
        if m:
            coeff = m.group(1)
            if coeff in ("", "+"):
                coeff = 1.0
            elif coeff == "-":
                coeff = -1.0
            else:
                coeff = float(coeff)
            a += coeff
            continue

        # x
        m = _re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d+)?)?)\*?x",
            term
        )
        if m:
            coeff = m.group(1)
            if coeff in ("", "+"):
                coeff = 1.0
            elif coeff == "-":
                coeff = -1.0
            else:
                coeff = float(coeff)
            b += coeff
            continue

        # Constant.
        if _re.fullmatch(r"[+-]?\d+(?:\.\d+)?", term):
            c += float(term)
            continue

        return None

    return a, b, c


def _giant_algebra(prompt):
    q = prompt.strip()

    if "=" not in q:
        return None

    # Only solve equations containing x.
    if not _re.search(r"\bx\b|[0-9]x", q, _re.I):
        return None

    parts = q.split("=")

    # Exactly one equation.
    if len(parts) != 2:
        return None

    left = _algebra_poly(parts[0])
    right = _algebra_poly(parts[1])

    if left is None or right is None:
        return None

    a = left[0] - right[0]
    b = left[1] - right[1]
    c = left[2] - right[2]

    eps = 1e-12

    # Linear equation: ax + b = 0
    if abs(a) < eps:
        if abs(b) < eps:
            if abs(c) < eps:
                return "Equation: infinitely many solutions"
            return "Equation: no solution"

        x = -c / b
        return f"x = {_fmt(x)}"

    # Quadratic equation: ax² + bx + c = 0
    discriminant = b * b - 4 * a * c

    if discriminant < -eps:
        real = -b / (2 * a)
        imag = _math.sqrt(-discriminant) / abs(2 * a)

        return (
            f"x = {_fmt(real)} ± {_fmt(imag)}i"
        )

    if abs(discriminant) < eps:
        x = -b / (2 * a)
        return f"x = {_fmt(x)}"

    root = _math.sqrt(discriminant)

    x1 = (-b + root) / (2 * a)
    x2 = (-b - root) / (2 * a)

    # Stable readable ordering.
    roots = sorted([x1, x2])

    return (
        f"x = {_fmt(roots[0])}, {_fmt(roots[1])}"
    )


def _giant_advanced_math(prompt):
    q = prompt.strip().lower()

    # Power.
    m = _re.search(
        r"\b(?:power|pow)\s+"
        r"([+-]?\d+(?:\.\d+)?)\s+"
        r"(?:to|by|\^)\s*"
        r"([+-]?\d+(?:\.\d+)?)\b",
        q
    )
    if m:
        base = float(m.group(1))
        exponent = float(m.group(2))
        try:
            return _result(
                "Power",
                base ** exponent,
                ""
            )
        except Exception:
            return None

    # log value base base
    m = _re.search(
        r"\blog(?:arithm)?\s+"
        r"([+-]?\d+(?:\.\d+)?)\s+"
        r"(?:base|b)\s*"
        r"([+-]?\d+(?:\.\d+)?)",
        q
    )
    if m:
        value = float(m.group(1))
        base = float(m.group(2))
        if value > 0 and base > 0 and base != 1:
            return _result("Log", _math.log(value, base), "")
        return None

    # ln value
    m = _re.search(
        r"\bln\s*?\s*([+-]?\d+(?:\.\d+)?)\s*?",
        q
    )
    if m:
        value = float(m.group(1))
        if value > 0:
            return _result("Natural log", _math.log(value), "")
        return None

    # log10 value
    m = _re.search(
        r"\blog10\s*?\s*([+-]?\d+(?:\.\d+)?)\s*?",
        q
    )
    if m:
        value = float(m.group(1))
        if value > 0:
            return _result("Log10", _math.log10(value), "")
        return None

    # Radian -> degree
    m = _re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*(?:rad|radian|radians)\s*(?:to|in)\s*(?:deg|degree|degrees)",
        q
    )
    if m:
        value = float(m.group(1))
        return _result(
            "Degrees",
            _math.degrees(value),
            "°"
        )

    # Degree -> radian
    m = _re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)\s*(?:to|in)\s*(?:rad|radian|radians)",
        q
    )
    if m:
        value = float(m.group(1))
        return _result(
            "Radians",
            _math.radians(value),
            "rad"
        )

    # nth root
    m = _re.search(
        r"(?:(\d+)(?:st|nd|rd|th)\s+root\s+of|root\s+"
        r"(\d+)\s+of)\s*([+-]?\d+(?:\.\d+)?)",
        q
    )
    if m:
        n = int(m.group(1) or m.group(2))
        value = float(m.group(3))

        if n <= 0:
            return None

        if value < 0 and n % 2 == 0:
            return None

        if value < 0:
            result = -((-value) ** (1.0 / n))
        else:
            result = value ** (1.0 / n)

        return _result(
            f"{n}th root",
            result,
            ""
        )

    # Scientific notation:
    # "6.02 x 10^23"
    m = _re.search(
        r"([+-]?\d+(?:\.\d+)?)\s*x\s*10\s*\^\s*([+-]?\d+)",
        q
    )
    if m:
        mantissa = float(m.group(1))
        exponent = int(m.group(2))
        return _result(
            "Scientific notation",
            mantissa * (10 ** exponent),
            ""
        )

    return None


# Preserve the current deterministic calculator.
_GIANT_ALGEBRA_OLD_CALCULATE = calculate


def calculate(prompt):
    original = prompt

    # 1. Algebra equations first.
    result = _giant_algebra(original)
    if result is not None:
        return result

    # 2. Advanced mathematics.
    result = _giant_advanced_math(original)
    if result is not None:
        return result

    # 3. Existing giant/local calculation engine.
    return _GIANT_ALGEBRA_OLD_CALCULATE(original)


# ============================================================
# ROLEX AI — LINEAR ALGEBRA EXTENSION
# Simultaneous equations + matrices + vectors
# ============================================================

import re as _la_re
import math as _la_math


def _la_numbers(text):
    return [
        float(x)
        for x in _la_re.findall(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",
            text
        )
    ]


def _la_fmt_matrix(M):
    rows = []
    for row in M:
        rows.append(
            "[" + ", ".join(_fmt(x) for x in row) + "]"
        )
    return "[" + "; ".join(rows) + "]"


def _giant_linear_algebra(prompt):
    q = prompt.strip().lower()

    # --------------------------------------------------------
    # 2x2 simultaneous equations
    #
    # Example:
    # 2x + 3y = 13
    # x - y = 1
    # --------------------------------------------------------

    if "=" in q and _la_re.search(r"\by\b", q):
        equations = [
            x.strip()
            for x in _la_re.split(r"[;\n]+", q)
            if "=" in x
        ]

        if len(equations) == 2:
            def coefficients(expr):
                expr = expr.replace(" ", "")
                expr = expr.replace("−", "-")
                expr = expr.replace("–", "-")

                # Normalize implicit multiplication.
                expr = _la_re.sub(r"(\d)([xy])", r"\1*\2", expr)

                # Move everything to left side.
                parts = expr.split("=")
                if len(parts) != 2:
                    return None

                left = parts[0]
                right = parts[1]

                # This parser intentionally supports simple
                # linear expressions only.
                def parse_side(side):
                    side = side.replace("-", "+-")
                    if side.startswith("+-"):
                        side = "-" + side[2:]

                    terms = side.split("+")
                    a = b = c = 0.0

                    for term in terms:
                        if not term:
                            continue

                        if "*" in term:
                            p = term.split("*")
                            if len(p) == 2:
                                coeff = p[0]
                                var = p[1]

                                try:
                                    value = float(
                                        coeff
                                    )
                                except Exception:
                                    return None

                                if var == "x":
                                    a += value
                                elif var == "y":
                                    b += value
                                else:
                                    return None
                                continue

                        if term in ("x", "+x"):
                            a += 1
                            continue

                        if term == "-x":
                            a -= 1
                            continue

                        if term in ("y", "+y"):
                            b += 1
                            continue

                        if term == "-y":
                            b -= 1
                            continue

                        if _la_re.fullmatch(
                            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",
                            term
                        ):
                            c += float(term)
                            continue

                        # 2x / 2y after normalization fallback.
                        m = _la_re.fullmatch(
                            r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))(x|y)",
                            term
                        )
                        if m:
                            value = float(m.group(1))
                            if m.group(2) == "x":
                                a += value
                            else:
                                b += value
                            continue

                        return None

                    return a, b, c

                L = parse_side(left)
                R = parse_side(right)

                if L is None or R is None:
                    return None

                return (
                    L[0] - R[0],
                    L[1] - R[1],
                    L[2] - R[2]
                )

            c1 = coefficients(equations[0])
            c2 = coefficients(equations[1])

            if c1 is not None and c2 is not None:
                a1, b1, c1v = c1
                a2, b2, c2v = c2

                # a1*x + b1*y = -c1
                # a2*x + b2*y = -c2
                determinant = a1 * b2 - a2 * b1

                if abs(determinant) > 1e-12:
                    x = ((-c1v) * b2 - (-c2v) * b1) / determinant
                    y = (a1 * (-c2v) - a2 * (-c1v)) / determinant

                    return (
                        f"x = {_fmt(x)}, y = {_fmt(y)}"
                    )

                # Parallel / identical equations.
                if (
                    abs(a1 * c2v - a2 * c1v) < 1e-12
                    and
                    abs(b1 * c2v - b2 * c1v) < 1e-12
                ):
                    return "System: infinitely many solutions"

                return "System: no solution"

    # --------------------------------------------------------
    # Matrix addition
    #
    # matrix add [1,2;3,4] [5,6;7,8]
    # --------------------------------------------------------

    m = _la_re.search(
        r"matrix\s+(?:add|addition)\s+"
        r"\[([^\]]+)\]\s+\[([^\]]+)\]",
        q
    )

    if m:
        def parse_matrix(s):
            rows = [
                r.strip()
                for r in s.split(";")
                if r.strip()
            ]

            matrix = []

            for row in rows:
                vals = _la_numbers(row)
                if not vals:
                    return None
                matrix.append(vals)

            if not matrix:
                return None

            width = len(matrix[0])
            if any(len(r) != width for r in matrix):
                return None

            return matrix

        A = parse_matrix(m.group(1))
        B = parse_matrix(m.group(2))

        if A is not None and B is not None:
            if len(A) == len(B) and len(A[0]) == len(B[0]):
                C = [
                    [
                        A[i][j] + B[i][j]
                        for j in range(len(A[0]))
                    ]
                    for i in range(len(A))
                ]

                return f"Matrix addition: {_la_fmt_matrix(C)}"

    # --------------------------------------------------------
    # Matrix multiplication
    # --------------------------------------------------------

    m = _la_re.search(
        r"matrix\s+(?:multiply|multiplication)\s+"
        r"\[([^\]]+)\]\s+\[([^\]]+)\]",
        q
    )

    if m:
        def parse_matrix2(s):
            rows = [
                r.strip()
                for r in s.split(";")
                if r.strip()
            ]

            result = [_la_numbers(r) for r in rows]

            if not result or any(not r for r in result):
                return None

            width = len(result[0])

            if any(len(r) != width for r in result):
                return None

            return result

        A = parse_matrix2(m.group(1))
        B = parse_matrix2(m.group(2))

        if A is not None and B is not None:
            if len(A[0]) == len(B):
                C = []

                for i in range(len(A)):
                    row = []

                    for j in range(len(B[0])):
                        value = sum(
                            A[i][k] * B[k][j]
                            for k in range(len(B))
                        )
                        row.append(value)

                    C.append(row)

                return f"Matrix multiplication: {_la_fmt_matrix(C)}"

    # --------------------------------------------------------
    # Vector addition
    # vector add [1,2,3] [4,5,6]
    # --------------------------------------------------------

    m = _la_re.search(
        r"vector\s+(?:add|addition)\s+"
        r"\[([^\]]+)\]\s+\[([^\]]+)\]",
        q
    )

    if m:
        A = _la_numbers(m.group(1))
        B = _la_numbers(m.group(2))

        if A and B and len(A) == len(B):
            C = [
                A[i] + B[i]
                for i in range(len(A))
            ]

            return (
                "Vector addition: ["
                + ", ".join(_fmt(x) for x in C)
                + "]"
            )

    # --------------------------------------------------------
    # Vector dot product
    # --------------------------------------------------------

    m = _la_re.search(
        r"vector\s+(?:dot|dot\s+product)\s+"
        r"\[([^\]]+)\]\s+\[([^\]]+)\]",
        q
    )

    if m:
        A = _la_numbers(m.group(1))
        B = _la_numbers(m.group(2))

        if A and B and len(A) == len(B):
            result = sum(
                A[i] * B[i]
                for i in range(len(A))
            )

            return f"Dot product: {_fmt(result)}"

    # --------------------------------------------------------
    # Vector magnitude
    # --------------------------------------------------------

    m = _la_re.search(
        r"vector\s+(?:magnitude|length)\s+"
        r"\[([^\]]+)\]",
        q
    )

    if m:
        A = _la_numbers(m.group(1))

        if A:
            result = _la_math.sqrt(
                sum(x * x for x in A)
            )

            return f"Vector magnitude: {_fmt(result)}"

    return None


# Preserve current engine.
_GIANT_LA_OLD_CALCULATE = calculate


def calculate(prompt):
    result = _giant_linear_algebra(prompt)

    if result is not None:
        return result

    return _GIANT_LA_OLD_CALCULATE(prompt)


# ============================================================
# ROLEX AI — CALCULUS ENGINE
# Local deterministic mathematics
# ============================================================

import math as _calc_math
import re as _calc_re


def _calc_normalize(expr):
    expr = expr.strip().lower()
    expr = expr.replace("−", "-").replace("–", "-")
    expr = expr.replace("×", "*").replace("·", "*")
    expr = expr.replace("^", "**")
    expr = _calc_re.sub(r"\s+", "", expr)
    return expr


def _calc_poly_derivative(expr):
    """
    Symbolic derivative for polynomial expressions in x.
    Supports:
      x
      x^n
      2x
      3x^2
      x^3 + 2x - 5
      -4x^4 + 3x^2 - x + 8
    """

    expr = _calc_normalize(expr)

    # Reject unsupported functions/symbols.
    if _calc_re.search(r"[^0-9x+\-*.]", expr):
        return None

    expr = _calc_re.sub(r"(\d)(x)", r"\1*x", expr)

    terms = _calc_re.findall(r"[+-]?[^+-]+", expr)

    result = []

    for term in terms:
        if not term:
            continue

        # x^n
        m = _calc_re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d+)?)?)\*?x\*\*(\d+)",
            term
        )

        if m:
            coeff_text = m.group(1)
            power = int(m.group(2))

            if coeff_text in ("", "+"):
                coeff = 1.0
            elif coeff_text == "-":
                coeff = -1.0
            else:
                coeff = float(coeff_text)

            if power == 0:
                continue

            new_coeff = coeff * power
            new_power = power - 1

            if new_power == 0:
                result.append(_fmt(new_coeff))
            elif new_power == 1:
                result.append(
                    f"{_fmt(new_coeff)}x"
                )
            else:
                result.append(
                    f"{_fmt(new_coeff)}x^{new_power}"
                )

            continue

        # ax
        m = _calc_re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d+)?)?)\*?x",
            term
        )

        if m:
            coeff_text = m.group(1)

            if coeff_text in ("", "+"):
                coeff = 1.0
            elif coeff_text == "-":
                coeff = -1.0
            else:
                coeff = float(coeff_text)

            result.append(_fmt(coeff))
            continue

        # Constant -> derivative 0
        if _calc_re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d+)?)",
            term
        ):
            continue

        return None

    if not result:
        return "0"

    # Clean positive signs for readable output.
    out = result[0]

    for item in result[1:]:
        if item.startswith("-"):
            out += " - " + item[1:]
        else:
            out += " + " + item

    return out


def _calc_poly_integral(expr):
    """
    Symbolic indefinite integral for polynomial expressions.
    """

    expr = _calc_normalize(expr)

    if _calc_re.search(r"[^0-9x+\-*.]", expr):
        return None

    expr = _calc_re.sub(r"(\d)(x)", r"\1*x", expr)

    terms = _calc_re.findall(r"[+-]?[^+-]+", expr)

    result = []

    for term in terms:
        if not term:
            continue

        # ax^n
        m = _calc_re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d+)?)?)\*?x\*\*(\d+)",
            term
        )

        if m:
            coeff_text = m.group(1)
            power = int(m.group(2))

            if coeff_text in ("", "+"):
                coeff = 1.0
            elif coeff_text == "-":
                coeff = -1.0
            else:
                coeff = float(coeff_text)

            new_power = power + 1
            new_coeff = coeff / new_power

            if new_power == 1:
                result.append(
                    f"{_fmt(new_coeff)}x"
                )
            else:
                result.append(
                    f"{_fmt(new_coeff)}x^{new_power}"
                )

            continue

        # ax
        m = _calc_re.fullmatch(
            r"([+-]?(?:\d+(?:\.\d+)?)?)\*?x",
            term
        )

        if m:
            coeff_text = m.group(1)

            if coeff_text in ("", "+"):
                coeff = 1.0
            elif coeff_text == "-":
                coeff = -1.0
            else:
                coeff = float(coeff_text)

            new_coeff = coeff / 2.0
            result.append(
                f"{_fmt(new_coeff)}x^2"
            )
            continue

        # Constant
        m = _calc_re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d+)?)",
            term
        )

        if m:
            coeff = float(term)
            result.append(
                f"{_fmt(coeff)}x"
            )
            continue

        return None

    if not result:
        return "C"

    out = result[0]

    for item in result[1:]:
        if item.startswith("-"):
            out += " - " + item[1:]
        else:
            out += " + " + item

    return out + " + C"


def _calc_numeric_function(expr):
    """
    Safe local numerical evaluator for calculus.

    This deliberately does NOT use _safe_eval(), because the
    general calculator evaluator has a stricter expression policy.
    """

    import ast
    import math
    import operator

    expr = str(expr).strip()

    if not expr:
        return None

    expr = (
        expr.replace("×", "*")
            .replace("÷", "/")
            .replace("−", "-")
            .replace("–", "-")
            .replace("^", "**")
    )

    expr = __import__("re").sub(
        r"\s*dx\s*$", "", expr, flags=__import__("re").I
    ).strip()

    # Implicit multiplication:
    # 2x -> 2*x
    # 3x^2 -> 3*x**2
    expr = __import__("re").sub(
        r"(?<=\d)\s*(?=x\b)", "*", expr, flags=__import__("re").I
    )

    expr = __import__("re").sub(
        r"(?<=\))\s*(?=x\b)", "*", expr, flags=__import__("re").I
    )

    expr = __import__("re").sub(
        r"(?<=\d)\s*(?=\()", "*", expr
    )

    expr = __import__("re").sub(
        r"(?<=x)\s*(?=\()", "*", expr, flags=__import__("re").I
    )

    functions = {
        "sqrt": math.sqrt,
        "cbrt": lambda v: math.copysign(abs(v) ** (1.0 / 3.0), v),
        "abs": abs,
        "sin": lambda v: math.sin(math.radians(v)),
        "cos": lambda v: math.cos(math.radians(v)),
        "tan": lambda v: math.tan(math.radians(v)),
        "asin": lambda v: math.degrees(math.asin(v)),
        "acos": lambda v: math.degrees(math.acos(v)),
        "atan": lambda v: math.degrees(math.atan(v)),
        "log": math.log10,
        "ln": math.log,
        "exp": math.exp,
    }

    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(node, x_value):
        if isinstance(node, ast.Expression):
            return evaluate(node.body, x_value)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("constant not allowed")

        if isinstance(node, ast.Name):
            name = node.id.lower()

            if name == "x":
                return float(x_value)

            if name == "pi":
                return math.pi

            if name == "e":
                return math.e

            raise ValueError("name not allowed")

        if isinstance(node, ast.UnaryOp):
            if type(node.op) not in (ast.USub, ast.UAdd):
                raise ValueError("unary operator not allowed")

            value = evaluate(node.operand, x_value)
            return operators[type(node.op)](value)

        if isinstance(node, ast.BinOp):
            if type(node.op) not in (
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Mod,
                ast.Pow,
            ):
                raise ValueError("operator not allowed")

            left = evaluate(node.left, x_value)
            right = evaluate(node.right, x_value)

            if isinstance(node.op, ast.Pow):
                if abs(right) > 1000:
                    raise ValueError("power too large")

            return operators[type(node.op)](left, right)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("function not allowed")

            name = node.func.id.lower()

            if name not in functions:
                raise ValueError("function not allowed")

            if len(node.args) != 1:
                raise ValueError("argument count")

            value = evaluate(node.args[0], x_value)
            return functions[name](value)

        raise ValueError("expression not allowed")

    try:
        tree = ast.parse(expr, mode="eval")
    except Exception:
        return None

    def fn(x):
        try:
            value = evaluate(tree, float(x))
            value = float(value)

            if not math.isfinite(value):
                return None

            return value

        except Exception:
            return None

    return fn


def _giant_calculus(prompt):
    q = prompt.strip().lower()

    # --------------------------------------------------------
    # Symbolic derivative
    # derivative x^2
    # derivative of 3x^2 + 2x
    # --------------------------------------------------------

    m = _calc_re.search(
        r"\bderivative(?:\s+of)?\s+(.+)$",
        q
    )

    if m:
        expr = m.group(1)
        expr = _calc_re.sub(r"\s*dx\s*$", "", expr)

        result = _calc_poly_derivative(expr)

        if result is not None:
            return f"Derivative: {result}"

    # --------------------------------------------------------
    # Symbolic integral
    # integral x^2 dx
    # integral of 3x + 2
    # --------------------------------------------------------

    m = _calc_re.search(
        r"\bintegral(?:\s+of)?\s+(.+)$",
        q
    )

    if m:
        expr = m.group(1)
        expr = _calc_re.sub(r"\s*dx\s*$", "", expr)

        result = _calc_poly_integral(expr)

        if result is not None:
            return f"Integral: {result}"

    # --------------------------------------------------------
    # Numerical derivative
    # derivative of sin( x ) at 0
    # numerical derivative x^2 at 3
    # --------------------------------------------------------

    m = _calc_re.search(
        r"(?:numerical\s+)?derivative(?:\s+of)?\s+(.+?)"
        r"\s+(?:at|when\s+x\s*=)\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
        q
    )

    if m:
        expr = m.group(1)
        x0 = float(m.group(2))

        fn = _calc_numeric_function(expr)

        if fn is not None:
            h = 1e-6
            f1 = fn(x0 + h)
            f2 = fn(x0 - h)

            if f1 is not None and f2 is not None:
                result = (f1 - f2) / (2 * h)
                return f"Numerical derivative: {_fmt(result)}"

    # --------------------------------------------------------
    # Definite integral — polynomial exact evaluation
    #
    # integral x^2 from 0 to 3
    # --------------------------------------------------------

    m = _calc_re.search(
        r"\bintegral(?:\s+of)?\s+(.+?)"
        r"\s+from\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"\s+to\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
        q
    )

    if m:
        expr = m.group(1)
        a = float(m.group(2))
        b = float(m.group(3))

        anti = _calc_poly_integral(expr)

        if anti is not None:
            fn = _calc_numeric_function(
                anti.replace("+ C", "")
            )

            if fn is not None:
                fa = fn(a)
                fb = fn(b)

                if fa is not None and fb is not None:
                    return (
                        f"Definite integral: "
                        f"{_fmt(fb - fa)}"
                    )

    # --------------------------------------------------------
    # Numerical definite integral — Simpson's rule
    #
    # numerical integral x^2 from 0 to 3
    # --------------------------------------------------------

    m = _calc_re.search(
        r"(?:numerical\s+)?integral(?:\s+of)?\s+(.+?)"
        r"\s+from\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))"
        r"\s+to\s+"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
        q
    )

    if m:
        expr = m.group(1)
        a = float(m.group(2))
        b = float(m.group(3))

        fn = _calc_numeric_function(expr)

        if fn is not None:
            n = 1000

            if n % 2:
                n += 1

            h = (b - a) / n

            total = 0.0
            valid = True

            for i in range(n + 1):
                x = a + i * h
                value = fn(x)

                if value is None:
                    valid = False
                    break

                if i == 0 or i == n:
                    weight = 1
                elif i % 2:
                    weight = 4
                else:
                    weight = 2

                total += weight * value

            if valid:
                result = total * h / 3.0
                return (
                    f"Numerical integral: {_fmt(result)}"
                )

    # --------------------------------------------------------
    # Limit using symmetric numerical evaluation
    #
    # limit x^2 as x approaches 2
    # --------------------------------------------------------

    m = _calc_re.search(
        r"\blimit(?:\s+of)?\s+(.+?)"
        r"\s+as\s+x\s+(?:approaches|approach|->)\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
        q
    )

    if m:
        expr = m.group(1)
        x0 = float(m.group(2))

        fn = _calc_numeric_function(expr)

        if fn is not None:
            h = 1e-5

            left = fn(x0 - h)
            right = fn(x0 + h)

            if left is not None and right is not None:
                result = (left + right) / 2.0
                return f"Limit: {_fmt(result)}"

    # --------------------------------------------------------
    # --------------------------------------------------------
    # Newton-Raphson root solving
    #
    # solve x^2 - 2 starting 1
    # solve x^2 - 2 = 0 starting 1
    # --------------------------------------------------------

    m = _calc_re.search(
        r"\bsolve\s+(.+?)"
        r"\s+starting\s+(?:(?:at|from)\s*)?"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))$",
        q
    )

    if m:
        expr = m.group(1).strip()
        x = float(m.group(2))

        # Accept equation-style input:
        # x^2 - 2 = 0
        # f(x) = x^2 - 2
        expr = re.sub(r"\s*=\s*0\s*$", "", expr)
        expr = re.sub(r"^\s*f\s*\(\s*x\s*\)\s*=\s*", "", expr)

        if "x" in expr:
            fn = _calc_numeric_function(expr)

            if fn is not None:
                for _ in range(100):
                    fx = fn(x)

                    if fx is None:
                        return None

                    if abs(fx) < 1e-12:
                        return f"Root: x = {_fmt(x)}"

                    h = 1e-6

                    fp = fn(x + h)
                    fm = fn(x - h)

                    if fp is None or fm is None:
                        return None

                    derivative = (fp - fm) / (2.0 * h)

                    if abs(derivative) < 1e-14:
                        return None

                    new_x = x - (fx / derivative)

                    if abs(new_x - x) < 1e-12:
                        x = new_x
                        return f"Root: x = {_fmt(x)}"

                    x = new_x

                # Final convergence check
                if fn(x) is not None and abs(fn(x)) < 1e-9:
                    return f"Root: x = {_fmt(x)}"

    return None



# Preserve current engine.
_CALCULUS_OLD_CALCULATE = calculate





def calculate(prompt):
    # Local deterministic calculus dispatch
    _calc_result = _giant_calculus(prompt)
    if _calc_result is not None:
        return _calc_result
    result = _giant_calculus(prompt)

    if result is not None:
        return result

    return _CALCULUS_OLD_CALCULATE(prompt)

