"""Check translation, operand validation and the command-line interface."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.assembler import translate


ROOT = Path(__file__).resolve().parents[1]
SPEC_PROGRAM = ROOT / "tests" / "spec_program.json"
EXPECTED_FIELDS = [
    {"A": 0, "B": 12, "C": 851},
    {"A": 25, "B": 9, "C": 937},
    {"A": 32, "B": 8, "C": 0},
    {"A": 23, "B": 251, "C": 3, "D": 15, "E": 15},
]
EXPECTED_OUTPUT = (
    "(A=0, B=12, C=851)\n"
    "(A=25, B=9, C=937)\n"
    "(A=32, B=8, C=0)\n"
    "(A=23, B=251, C=3, D=15, E=15)\n"
)


def run_cli(*arguments: str | Path) -> subprocess.CompletedProcess[str]:
    """Run the CLI in an independent process."""
    return subprocess.run(
        [
            sys.executable, "-B", str(ROOT / "src" / "assembler.py"),
            *(str(argument) for argument in arguments),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TranslationTests(unittest.TestCase):
    """Check field values and input validation."""

    def test_specification_fields(self) -> None:
        """Match all four examples from the variant specification."""
        program = json.loads(SPEC_PROGRAM.read_text(encoding="utf-8"))
        self.assertEqual(translate(program), EXPECTED_FIELDS)

    def test_operand_limits(self) -> None:
        """Accept the minimum and inclusive maximum values of the fields."""
        program = [
            {"op": "load_const", "dst": 0, "value": 0},
            {"op": "load_const", "dst": 15, "value": 16_777_215},
            {"op": "read_mem", "dst": 15, "address": 524_287},
            {"op": "write_mem", "src": 15, "addr_reg": 15},
            {"op": "mul", "offset": 8191, "lhs": 15, "base": 15, "dst": 0},
        ]
        self.assertEqual(translate(program), [
            {"A": 0, "B": 0, "C": 0},
            {"A": 0, "B": 15, "C": 16_777_215},
            {"A": 25, "B": 15, "C": 524_287},
            {"A": 32, "B": 15, "C": 15},
            {"A": 23, "B": 8191, "C": 15, "D": 15, "E": 0},
        ])

    def test_rejects_invalid_shape(self) -> None:
        """Reject invalid containers, operations and operand keys."""
        cases = [
            ({}, "expected a JSON array"),
            ([None], "instruction 1: expected a JSON object"),
            ([{"op": "halt"}], "unknown operation 'halt'"),
            ([{"op": "read_mem", "dst": 9}], "missing fields: address"),
            ([{"op": "load_const", "dst": 0, "value": 0, "x": 0}],
             "unexpected fields: x"),
        ]
        for program, message in cases:
            with self.subTest(program=program):
                with self.assertRaisesRegex(ValueError, message):
                    translate(program)

    def test_rejects_invalid_operands(self) -> None:
        """Reject out-of-range operands and numbers of the wrong JSON type."""
        cases = [
            ({"op": "load_const", "dst": -1, "value": 0}, "0..15"),
            ({"op": "load_const", "dst": 0, "value": 16_777_216},
             "0..16777215"),
            ({"op": "read_mem", "dst": 0, "address": 524_288}, "0..524287"),
            ({"op": "write_mem", "src": 0, "addr_reg": 16}, "0..15"),
            ({"op": "mul", "offset": 8192, "lhs": 0, "base": 0, "dst": 0},
             "0..8191"),
            ({"op": "load_const", "dst": True, "value": 0}, "an integer"),
            ({"op": "load_const", "dst": 0, "value": 1.0}, "an integer"),
        ]
        valid = {"op": "load_const", "dst": 0, "value": 0}
        for instruction, message in cases:
            with self.subTest(instruction=instruction):
                with self.assertRaises(ValueError) as error:
                    translate([valid, instruction])
                self.assertIn("instruction 2: ", str(error.exception))
                self.assertIn(message, str(error.exception))


class CliTests(unittest.TestCase):
    """Check observable behavior of the stage 1 command-line interface."""

    def test_test_mode_prints_specification_examples(self) -> None:
        """Print the expected fields and leave the result path unused."""
        with TemporaryDirectory() as directory:
            target = Path(directory) / "program.bin"
            result = run_cli(SPEC_PROGRAM, target, "--test")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, EXPECTED_OUTPUT)
            self.assertEqual(result.stderr, "")
            self.assertFalse(target.exists())

    def test_normal_mode_is_silent(self) -> None:
        """Translate silently without overwriting an existing result file."""
        with TemporaryDirectory() as directory:
            target = Path(directory) / "program.bin"
            original = b"existing file"
            target.write_bytes(original)
            result = run_cli(SPEC_PROGRAM, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            self.assertEqual(target.read_bytes(), original)

    def test_rejects_malformed_json(self) -> None:
        """Report malformed JSON or duplicate keys on standard error."""
        cases = [
            ("[", "line 1 column 2"),
            ('[{"op": "load_const", "dst": 0, "dst": 1, "value": 0}]',
             "duplicate JSON key 'dst'"),
        ]
        with TemporaryDirectory() as directory:
            source = Path(directory) / "invalid program.json"
            target = Path(directory) / "program.bin"
            for document, message in cases:
                with self.subTest(document=document):
                    source.write_text(document, encoding="utf-8")
                    result = run_cli(source, target, "--test")
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(message, result.stderr)
                    self.assertFalse(target.exists())

    def test_output_path_is_required(self) -> None:
        """Require both positional paths before translating the program."""
        result = run_cli(SPEC_PROGRAM, "--test")
        self.assertEqual(result.returncode, 2)
        self.assertIn("output", result.stderr)
