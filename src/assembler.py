"""Translate the variant 1 JSON assembly language to instruction fields."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path


REGISTER_BITS = 4
MIN_OPERAND = 0

INSTRUCTIONS = {
    "load_const": (0, (
        ("B", "dst", REGISTER_BITS),
        ("C", "value", 24),
    )),
    "read_mem": (25, (
        ("B", "dst", REGISTER_BITS),
        ("C", "address", 19),
    )),
    "write_mem": (32, (
        ("B", "src", REGISTER_BITS),
        ("C", "addr_reg", REGISTER_BITS),
    )),
    "mul": (23, (
        ("B", "offset", 13),
        ("C", "lhs", REGISTER_BITS),
        ("D", "base", REGISTER_BITS),
        ("E", "dst", REGISTER_BITS),
    )),
}


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object and reject repeated keys."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def validate_keys(instruction: dict[str, object], required: set[str]) -> None:
    """Require the exact set of keys defined for the operation."""
    missing = required - instruction.keys()
    extra = instruction.keys() - required
    if missing:
        raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"unexpected fields: {', '.join(sorted(extra))}")


def read_operand(value: object, name: str, bits: int) -> int:
    """Require a JSON integer that fits in the given unsigned field."""
    maximum = (1 << bits) - 1
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name!r} must be an integer")
    if not MIN_OPERAND <= value <= maximum:
        raise ValueError(f"{name!r} must be in {MIN_OPERAND}..{maximum}")
    return value


def translate_instruction(instruction: object) -> dict[str, int]:
    """Build a dictionary of machine fields in specification order."""
    if not isinstance(instruction, dict):
        raise ValueError("expected a JSON object")

    operation = instruction.get("op")
    if not isinstance(operation, str) or operation not in INSTRUCTIONS:
        raise ValueError(f"unknown operation {operation!r}")

    opcode, fields = INSTRUCTIONS[operation]
    required_keys = {"op"}
    required_keys.update(name for _, name, _ in fields)
    validate_keys(instruction, required_keys)

    result = {"A": opcode}
    for letter, name, bits in fields:
        result[letter] = read_operand(instruction[name], name, bits)
    return result


def translate(program: object) -> list[dict[str, int]]:
    """Translate a JSON array in order and report the index of bad commands."""
    if not isinstance(program, list):
        raise ValueError("expected a JSON array of instructions")

    instructions = []
    for number, instruction in enumerate(program, start=1):
        try:
            instructions.append(translate_instruction(instruction))
        except ValueError as error:
            raise ValueError(f"instruction {number}: {error}") from error
    return instructions


def format_fields(instruction: dict[str, int]) -> str:
    """Format fields as in the examples from the specification."""
    values = ", ".join(f"{key}={value}" for key, value in instruction.items())
    return f"({values})"


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and print the intermediate form in test mode."""
    parser = argparse.ArgumentParser(
        prog="assembler",
        description="UVM assembler, variant 1, stage 1",
    )
    parser.add_argument("source", type=Path, help="source JSON program")
    parser.add_argument(
        "output", type=Path, help="binary output path reserved for stage 2",
    )
    parser.add_argument(
        "--test", action="store_true", help="print the instruction fields",
    )
    args = parser.parse_args(argv)

    try:
        source = args.source.read_text(encoding="utf-8-sig")
        document = json.loads(source, object_pairs_hook=unique_object)
        program = translate(document)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")

    if args.test:
        for instruction in program:
            print(format_fields(instruction))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
