"""Validate the V0.1.0 RAG JSON Schemas and fixed examples.

This is a static contract verifier. It does not start Java, Python RAG,
RocketMQ, PostgreSQL, MinIO, Gateway, Nacos, or Sentinel.
"""

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError, validators


ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"
MANIFEST = ROOT / "SHA256SUMS.txt"
SCHEMAS = {
    "intake": ROOT / "document-intake-v2.schema.json",
    "acceptance": ROOT / "document-ingestion-acceptance-v1.schema.json",
    "result": ROOT / "document-ingestion-result-v1.schema.json",
}


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time", raises=(TypeError, ValueError))
def is_strict_rfc3339(value):
    if not isinstance(value, str):
        return True
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
    if re.fullmatch(pattern, value) is None:
        return False
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return True


def validate_utf8_max_bytes(validator, limit, instance, schema):
    if isinstance(instance, str) and len(instance.encode("utf-8")) > limit:
        yield ValidationError("UTF-8 byte length exceeds {0}".format(limit))


def validate_fractional_second_digits(validator, limit, instance, schema):
    if not isinstance(instance, str):
        return
    match = re.fullmatch(r".*?(?:\.(\d+))?(?:Z|[+-]\d{2}:\d{2})", instance)
    if match and match.group(1) and len(match.group(1)) > limit:
        yield ValidationError("fractional second digits exceed {0}".format(limit))


def validate_canonical_order(validator, rule, instance, schema):
    if rule != "ascending UTF-8 byte order" or not isinstance(instance, list):
        return
    expected = sorted(
        instance,
        key=lambda item: item.encode("utf-8") if isinstance(item, str) else b"",
    )
    if instance != expected:
        yield ValidationError("array is not in ascending UTF-8 byte order")


StrictDraft202012Validator = validators.extend(
    Draft202012Validator,
    {
        "x-utf8-max-bytes": validate_utf8_max_bytes,
        "x-max-fractional-second-digits": validate_fractional_second_digits,
        "x-canonical-order": validate_canonical_order,
    },
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def schema_name_for_example(path):
    name = path.name
    if name.startswith("document-intake."):
        return "intake"
    if name.startswith("document-ingestion-acceptance."):
        return "acceptance"
    if name.startswith("document-ingestion-result."):
        return "result"
    raise AssertionError("Unmapped example: {0}".format(name))


def contract_files():
    return sorted(list(SCHEMAS.values()) + list(EXAMPLES.glob("*.json")))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest():
    lines = []
    for path in contract_files():
        relative = path.relative_to(ROOT).as_posix()
        lines.append("{0}  {1}".format(sha256(path), relative))
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_manifest():
    expected = {path.relative_to(ROOT).as_posix(): path for path in contract_files()}
    actual = {}
    for number, raw_line in enumerate(MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", raw_line)
        if match is None:
            raise AssertionError("Malformed SHA256SUMS line {0}".format(number))
        actual[match.group(2)] = match.group(1)
    if set(actual) != set(expected):
        raise AssertionError("SHA256SUMS file set differs from schemas/examples")
    for relative, path in expected.items():
        if sha256(path) != actual[relative]:
            raise AssertionError("SHA-256 mismatch: {0}".format(relative))


def verify_cross_field_rules(schema_name, path, instance):
    if schema_name != "intake":
        return
    expected_file_ref = "local-file-ref:v1:{0}".format(instance["document_id"])
    if instance["file_ref"] != expected_file_ref:
        raise AssertionError(
            "Intake file_ref must contain the same reference_id as document_id: {0}".format(
                path.name
            )
        )


def run():
    validator_by_name = {}
    for name, path in SCHEMAS.items():
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)
        validator_by_name[name] = StrictDraft202012Validator(
            schema,
            format_checker=FORMAT_CHECKER,
        )

    valid_paths = sorted(EXAMPLES.glob("*.valid.json"))
    invalid_paths = sorted(EXAMPLES.glob("*.invalid.json"))

    for path in valid_paths:
        schema_name = schema_name_for_example(path)
        instance = load_json(path)
        validator_by_name[schema_name].validate(instance)
        verify_cross_field_rules(schema_name, path, instance)

    for path in invalid_paths:
        schema_name = schema_name_for_example(path)
        instance = load_json(path)
        errors = list(validator_by_name[schema_name].iter_errors(instance))
        if not errors:
            raise AssertionError("Invalid example was accepted: {0}".format(path.name))

    verify_manifest()
    print("SCHEMAS_OK={0}".format(len(SCHEMAS)))
    print("VALID_EXAMPLES_OK={0}".format(len(valid_paths)))
    print("INVALID_EXAMPLES_REJECTED={0}".format(len(invalid_paths)))
    print("SHA256_MANIFEST=PASS")
    print("STATIC_CONTRACT_VALIDATION=PASS")
    print("RUNTIME_CONNECTIVITY=NOT_RUN")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="Regenerate SHA256SUMS.txt before validation.",
    )
    args = parser.parse_args()
    if args.write_manifest:
        write_manifest()
    run()


if __name__ == "__main__":
    main()
