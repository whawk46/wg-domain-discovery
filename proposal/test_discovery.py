#!/usr/bin/env python3
"""
x402 Domain Discovery Conformance & Schema Verification Suite
Validates RFC 8615 well-known domain discovery manifests against the authoritative JSON schema.
Verifies positive multi-rail examples and asserts schema rejection on paired negative edge fixtures.

Copyright (c) 2026 x402 Foundation contributors.
"""

import json
import os
import sys
from pathlib import Path
import jsonschema

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "domain-discovery.schema.json"
EXAMPLES_DIR = BASE_DIR / "examples"
FIXTURES_DIR = EXAMPLES_DIR / "fixtures"

def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_tests():
    print("=" * 70)
    print("x402 DOMAIN DISCOVERY SCHEMA & CONFORMANCE TEST SUITE")
    print("=" * 70)

    # 1. Load Authoritative Schema
    if not SCHEMA_FILE.exists():
        print(f"[-] ERROR: Schema file not found: {SCHEMA_FILE}")
        sys.exit(1)

    schema = load_json(SCHEMA_FILE)
    validator = jsonschema.Draft7Validator(schema)
    print(f"[+] Loaded schema: {SCHEMA_FILE.name}")

    # 2. Positive Conformance Tests
    positive_files = [
        "minimal.well-known-x402.json",
        "multirail-service.well-known-x402.json",
        "facilitator.well-known-x402.json",
        "service-with-openapi.well-known-x402.json"
    ]

    print("\n--- 1. POSITIVE CONFORMANCE TESTS (MUST PASS) ---")
    pos_passed = 0
    for filename in positive_files:
        filepath = EXAMPLES_DIR / filename
        if not filepath.exists():
            print(f"[-] Missing positive test fixture: {filename}")
            sys.exit(1)

        data = load_json(filepath)
        errors = list(validator.iter_errors(data))
        if errors:
            print(f"[-] FAIL: {filename}")
            for err in errors:
                print(f"    Error: {err.message} at path: {'/'.join(str(p) for p in err.path)}")
            sys.exit(1)
        else:
            print(f"[PASS] {filename} (valid)")
            pos_passed += 1

    # 3. Negative Edge Fixture Tests (MUST REJECT ON SPECIFIC CONSTRAINT)
    negative_fixtures = [
        ("invalid-missing-version.json", "required", [], "missing required x402Version"),
        ("invalid-bad-version.json", "enum", ["x402Version"], "unsupported x402Version"),
        ("invalid-bad-caip2.json", "pattern", ["resources", 0, "accepts", 0, "network"], "malformed CAIP-2 network identifier"),
        ("invalid-negative-amount.json", "pattern", ["resources", 0, "accepts", 0, "amount"], "negative amount string"),
        ("invalid-empty-accepts.json", "minItems", ["resources", 0, "accepts"], "empty accepts array"),
        ("invalid-misplaced-carrier.json", "additionalProperties", [], "misplaced carrier key at root"),
        ("invalid-missing-kid.json", "required", ["keys", 0], "signing key missing required kid")
    ]

    print("\n--- 2. NEGATIVE EDGE FIXTURE TESTS (MUST REJECT ON SPECIFIC CONSTRAINT) ---")
    neg_passed = 0
    for filename, expected_validator, expected_path, expected_cause in negative_fixtures:
        filepath = FIXTURES_DIR / filename
        if not filepath.exists():
            print(f"[-] Missing negative test fixture: {filename}")
            sys.exit(1)

        data = load_json(filepath)
        errors = list(validator.iter_errors(data))
        if not errors:
            print(f"[-] CRITICAL FAIL: {filename} was unexpectedly ACCEPTED by schema!")
            print(f"    Expected rejection cause: {expected_cause}")
            sys.exit(1)

        # Assert the rejection is caused by the specific validator and path, not generic fallout
        matched = False
        for err in errors:
            if err.validator == expected_validator and list(err.path) == expected_path:
                matched = True
                err_msg = err.message
                err_path = "/".join(str(p) for p in err.path) or "(root)"
                print(f"[PASS] {filename} correctly rejected by '{err.validator}' at {err_path}: '{err_msg}'")
                neg_passed += 1
                break

        if not matched:
            print(f"[-] FAIL: {filename} was rejected, but not by expected validator '{expected_validator}' at {expected_path}")
            print(f"    Actual errors:")
            for err in errors:
                print(f"      - validator='{err.validator}' at path={list(err.path)}: {err.message}")
            sys.exit(1)

    print("\n" + "=" * 70)
    print(f"TEST SUMMARY: {pos_passed} Positive Passed | {neg_passed} Negative Rejections Verified (with exact validator assertions)")
    print("ALL TESTS PASSED WITH 100% CONFORMANCE.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
