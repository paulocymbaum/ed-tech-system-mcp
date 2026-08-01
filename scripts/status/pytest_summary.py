#!/usr/bin/env python3
"""Print pytest summary env exports from a JUnit XML file."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "pytest-results.xml")
    if not path.is_file():
        print("export PYTEST_PASSED=0")
        print("export PYTEST_FAILED=0")
        print("export PYTEST_SKIPPED=0")
        return 0

    root = ET.parse(path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        print("export PYTEST_PASSED=0")
        print("export PYTEST_FAILED=0")
        print("export PYTEST_SKIPPED=0")
        return 0

    total = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    passed = max(total - failures - errors - skipped, 0)

    print(f"export PYTEST_PASSED={passed}")
    print(f"export PYTEST_FAILED={failures + errors}")
    print(f"export PYTEST_SKIPPED={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
