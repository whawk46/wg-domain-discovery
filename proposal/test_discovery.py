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
import urllib.parse
from pathlib import Path
import jsonschema

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "domain-discovery.schema.json"
EXAMPLES_DIR = BASE_DIR / "examples"
FIXTURES_DIR = EXAMPLES_DIR / "fixtures"
MIGRATION_DIR = EXAMPLES_DIR / "migration"

# Root keys the v2 schema admits. Kept explicit so that a schema revision which
# adds a root key is a deliberate edit here, instead of silently relaxing the
# §8.3 relocation assertion below.
V2_ROOT_KEYS = {
    "x402Version", "kind", "facilitator", "keys", "extensions", "resources", "openapi"
}

def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_migration_check(validator):
    """section 8.2/8.3: the incumbent -> v2 rendition must be a deterministic map.

    Returns the number of resource entries checked; exits 1 on any violation.

    The pair is a real incumbent host (76 resources, 24 legacy root keys), not a
    synthetic minimal. The three properties asserted are the three the section 8
    revision promises a migrating host can rely on:

      1. the incumbent fails the schema -- it is not a positive example;
      2. its v2 rendition passes;
      3. the transition is mechanical: `path` is the incumbent `url`'s path,
         `method` carries into `methods`, `description` is preserved, and every
         incumbent root key the schema does not admit lands in `extensions`
         with its value unchanged.
    """
    incumbent_file = MIGRATION_DIR / "incumbent-legacy.json"
    v2_file = MIGRATION_DIR / "incumbent-v2.well-known-x402.json"
    for path in (incumbent_file, v2_file):
        if not path.exists():
            print(f"[-] Missing migration fixture: {path}")
            sys.exit(1)

    incumbent = load_json(incumbent_file)
    v2 = load_json(v2_file)

    # (1) The incumbent is invalid -- that is the whole reason a migration exists.
    inc_errors = list(validator.iter_errors(incumbent))
    if not inc_errors:
        print("[-] FAIL: incumbent-legacy.json was ACCEPTED by the v2 schema; "
              "it no longer demonstrates a migration.")
        sys.exit(1)

    # (2) The v2 rendition is a positive example.
    v2_errors = list(validator.iter_errors(v2))
    if v2_errors:
        print("[-] FAIL: incumbent-v2.well-known-x402.json is not schema-valid:")
        for err in v2_errors[:10]:
            print(f"      - {err.validator} at {'/'.join(str(p) for p in err.path)}: {err.message}")
        sys.exit(1)

    # (3, section 8.3) Root relocation is total and value-preserving.
    relocated = 0
    for key, value in incumbent.items():
        if key == "resources":
            continue
        if key in V2_ROOT_KEYS:
            if v2.get(key) != value:
                print(f"[-] FAIL: root key '{key}' changed during migration")
                sys.exit(1)
        elif v2.get("extensions", {}).get(key) != value:
            print(f"[-] FAIL: legacy root key '{key}' did not land in extensions unchanged")
            sys.exit(1)
        else:
            relocated += 1

    # (3, section 8.2) Every resource entry maps mechanically, in order.
    inc_res = incumbent.get("resources", [])
    v2_res = v2.get("resources", [])
    if len(inc_res) != len(v2_res):
        print(f"[-] FAIL: resource count changed {len(inc_res)} -> {len(v2_res)}")
        sys.exit(1)
    for i, (before, after) in enumerate(zip(inc_res, v2_res)):
        want_path = urllib.parse.urlsplit(before.get("url", "")).path
        if after.get("path") != want_path:
            print(f"[-] FAIL: entry {i}: path {after.get('path')!r} != url path {want_path!r}")
            sys.exit(1)
        if after.get("methods") != [before.get("method")]:
            print(f"[-] FAIL: entry {i}: methods {after.get('methods')!r} does not carry "
                  f"method {before.get('method')!r}")
            sys.exit(1)
        if before.get("description") and after.get("description") != before.get("description"):
            print(f"[-] FAIL: entry {i}: description not preserved")
            sys.exit(1)
        if not after.get("accepts"):
            print(f"[-] FAIL: entry {i}: v2 entry has no accepts")
            sys.exit(1)

    print(f"[PASS] migration: incumbent ({len(inc_errors)} schema error(s)) -> v2 valid; "
          f"{len(v2_res)} entr(ies) map deterministically (section 8.2), "
          f"{relocated} legacy root key(s) relocated to extensions (section 8.3)")
    return len(v2_res)

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
        "service-with-openapi.well-known-x402.json",
        "bare-openapi.well-known-x402.json",
        "hybrid-facilitator.well-known-x402.json",
        "forward-extensions.well-known-x402.json"
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
        ("invalid-caip2-reference-overflow.json", "pattern", ["resources", 0, "accepts", 0, "network"], "CAIP-2 network reference exceeding 32 characters"),
        ("invalid-negative-amount.json", "pattern", ["resources", 0, "accepts", 0, "amount"], "negative amount string"),
        ("invalid-empty-accepts.json", "minItems", ["resources", 0, "accepts"], "empty accepts array"),
        ("invalid-misplaced-carrier.json", "not", [], "misplaced carrier key at root"),
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

    # 3b. Resource Class Discrimination & Client Root-Key Tolerance Checks (§4.2, §4.3, §8.2, §8.3)
    print("\n--- 2b. RESOURCE CLASS DISCRIMINATION & ROOT TOLERANCE CHECKS ---")
    pointer_and_root_manifest = {
        "x402Version": 2,
        "name": "Example Pointer Service",
        "description": "Benign unknown descriptive root keys tolerated by client validation",
        "resources": [
            {"url": "https://example.com/x402/proxy/x402-gas", "method": "GET", "description": "Gas prices across 5 chains."},
            "https://example.com/x402/proxy/x402-find"
        ]
    }
    ptr_errors = list(validator.iter_errors(pointer_and_root_manifest))
    if ptr_errors:
        print(f"[-] FAIL: pointerResource + benign root keys rejected: {ptr_errors[0].message}")
        sys.exit(1)
    print("[PASS] pointerResource ({url, method, description} + URI string) & benign unknown root keys accepted")

    ambiguous_mixed_entry = {
        "x402Version": 2,
        "resources": [
            {
                "path": "/api/v1/mixed",
                "url": "https://example.com/api/v1/mixed",
                "accepts": [{"scheme": "exact", "network": "eip155:8453", "amount": "100"}]
            }
        ]
    }
    mix_errors = list(validator.iter_errors(ambiguous_mixed_entry))
    if not any(e.validator == "additionalProperties" and list(e.path) == ["resources", 0] for e in mix_errors):
        print("[-] FAIL: overlapping {path, url, accepts} entry was not rejected by resources[0] additionalProperties")
        sys.exit(1)
    print("[PASS] ambiguous overlapping {path, url, accepts} entry deterministically rejected by 'additionalProperties' at resources/0")

    # 4. Migration Fixture: legacy incumbent -> x402Version 2 rendition
    print("\n--- 3. MIGRATION FIXTURE (incumbent -> x402Version 2) ---")
    mig_entries = run_migration_check(validator)

    print("\n" + "=" * 70)
    print(f"TEST SUMMARY: {pos_passed} Positive Passed | {neg_passed} Negative Rejections Verified "
          f"(with exact validator assertions) | {mig_entries} Migration Entr(ies) Verified")
    print("ALL TESTS PASSED WITH 100% CONFORMANCE.")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
