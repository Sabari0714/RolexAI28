import unittest

from modules.math_engine import calculate, safe_expression


class MathEngineTests(unittest.TestCase):

    def test_addition(self):
        self.assertEqual(calculate("25 + 16"), "Answer: 41")

    def test_precedence(self):
        self.assertEqual(calculate("10 + 5 * 2"), "Answer: 20")

    def test_brackets(self):
        self.assertEqual(calculate("(10 + 5) * 2"), "Answer: 30")

    def test_percentage(self):
        self.assertEqual(
            calculate("20% of 500"),
            "Percentage: 100",
        )

    def test_power(self):
        self.assertEqual(
            calculate("2 ^ 10"),
            "Answer: 1024",
        )

    def test_sqrt(self):
        self.assertEqual(
            calculate("sqrt(144)"),
            "Answer: 12",
        )

    def test_sin(self):
        self.assertEqual(
            calculate("sin(30)"),
            "Answer: 0.5",
        )

    def test_ohms_law(self):
        self.assertEqual(
            calculate("12V 2A resistance"),
            "Resistance: 6 Ω",
        )

    def test_power(self):
        self.assertEqual(
            calculate("12V 2A power"),
            "Power: 24 W",
        )

    def test_voltage(self):
        self.assertEqual(
            calculate("2A 6ohm voltage"),
            "Voltage: 12 V",
        )

    def test_rpm_to_rps(self):
        self.assertEqual(
            calculate("1500 rpm to rps"),
            "RPS: 25 r/s",
        )

    def test_length_conversion(self):
        self.assertEqual(
            calculate("1 km to m"),
            "Conversion: 1000 m",
        )

    def test_temperature(self):
        self.assertEqual(
            calculate("100 C to F"),
            "Temperature: 212 °F",
        )

    def test_circle_area(self):
        self.assertTrue(
            calculate("circle area 10").startswith("Circle area:")
        )

    def test_malicious_expression_blocked(self):
        self.assertIsNone(
            calculate("__import__('os').system('id')")
        )

    def test_division_by_zero(self):
        self.assertIsNone(
            calculate("10 / 0")
        )

    def test_non_math_rejected(self):
        self.assertIsNone(
            calculate("hello rolex")
        )

    def test_ast_blocks_attribute_access(self):
        with self.assertRaises(Exception):
            safe_expression("__import__('os')")


if __name__ == "__main__":
    unittest.main()
