"""Command line entry point: run the parity suite and write its reports.

Exit status follows TSTVAL00 where it can: 12 for a case that blew up, as
9999-ERROR-HANDLER does, 1 when the two sides differ, 0 otherwise. Blocked cases
do not fail the run unless ``--fail-on-blocked`` is given, so the suite can sit
in CI while the services it needs are still being ported.
"""

import argparse
import sys
from pathlib import Path

from parity.adapters import PortedSystem
from parity.cases import CaseType, cases_by_type, run_suite
from parity.report import diff_text, legacy_report, write_reports
from parity.suite import CASES


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="parity", description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="directory to write test-validation-report.txt, parity-diff.json and parity-diff.txt",
    )
    parser.add_argument(
        "--type",
        dest="case_type",
        choices=[item.value for item in CaseType],
        default=None,
        help="run only cases of one TEST-TYPE",
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="treat a case whose ported service is missing as a failure",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    system = PortedSystem()
    cases = list(CASES)
    if arguments.case_type is not None:
        cases = cases_by_type(cases, CaseType(arguments.case_type))

    result = run_suite(cases, system)

    sys.stdout.write(legacy_report(result))
    sys.stdout.write("\n" + diff_text(result) + "\n")
    if arguments.out is not None:
        written = write_reports(result, arguments.out)
        for label, path in written.items():
            sys.stdout.write(f"{label}: {path}\n")

    if result.errored:
        return 12
    if result.failed or (arguments.fail_on_blocked and result.blocked):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
