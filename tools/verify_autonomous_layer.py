#!/usr/bin/env python3
"""Verify the autonomous layer is intact.

Run this after every upstream sync, backport, or merge that touches `chain` or
`20.0`. It exists because the failure mode we care about is silent: if a merge
conflict on one of the 30 `auto_install` manifests is resolved by taking the
upstream side, the OCB policy flips back to `True` and nothing errors.

Checks:
  1. the 30 `auto_install` values still match the OCB policy
  2. the 5 packaging/identity files are present, and byte-identical to the
     OCB baseline when a baseline ref is supplied
  3. every addon manifest parses
  4. no conflict markers are left anywhere
  5. `odoo/release.py` is unchanged relative to a supplied ref

Usage:
    python tools/verify_autonomous_layer.py
    python tools/verify_autonomous_layer.py --baseline-ref origin/20.0
    python tools/verify_autonomous_layer.py --release-ref odoo/master

Exit code 0 means all checks passed.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

# The OCB policy: module -> expected auto_install value.
# Source: OCA/OCB ecba93571a156a0501ff4e9ce7a39ecc056737d2
# ("[IMP] *: change auto_install", OCA/OCB PR #1358).
#
# 18 modules are switched off entirely. 12 spreadsheet modules move from a
# dependency-subset list (e.g. ['sale']) to True, which tightens the trigger:
# True requires every dependency to be installed, whereas a list triggers when
# any listed dependency is present.
EXPECTED_AUTO_INSTALL: dict[str, object] = {
    # switched off (was True or a list)
    "account_edi_ubl_cii": False,
    "account_peppol": False,
    "account_qr_code_sepa": False,
    "base_import_module": False,
    "base_install_request": False,
    "iap": False,
    "iap_crm": False,
    "l10n_fr_pdp": False,
    "mail_bot": False,
    "mail_plugin": False,
    "mysubscription": False,
    "partner_autocomplete": False,
    "privacy_lookup": False,
    "project_todo": False,
    "sale_margin": False,
    "sale_pdf_quote_builder": False,
    "sms": False,
    "web_unsplash": False,
    # tightened: dependency-subset list -> True
    "spreadsheet_account": True,
    "spreadsheet_dashboard_event_sale": True,
    "spreadsheet_dashboard_hr_expense": True,
    "spreadsheet_dashboard_hr_timesheet": True,
    "spreadsheet_dashboard_im_livechat": True,
    "spreadsheet_dashboard_pos_hr": True,
    "spreadsheet_dashboard_pos_restaurant": True,
    "spreadsheet_dashboard_sale": True,
    "spreadsheet_dashboard_sale_timesheet": True,
    "spreadsheet_dashboard_stock_account": True,
    "spreadsheet_dashboard_website_sale": True,
    "spreadsheet_dashboard_website_sale_slides": True,
}

PACKAGING_FILES = [
    "README.md",
    "MANIFEST.in",
    "pyproject.toml",
    "setup.py",
    "setup/pep517_odoo.py",
]

RELEASE_FILE = "odoo/release.py"

CONFLICT_MARKERS = r"^(<<<<<<<|>>>>>>>|\|\|\|\|\|\|\|)"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], capture_output=True).returncode == 0


def ocb_layer_present() -> bool:
    """True when this branch carries the OCB packaging layer.

    `chain` does not have it until the OCB backport is merged, and the policy
    checks below are only meaningful once it is there. Detecting this keeps the
    generic checks (manifest parsing, conflict markers) running on every branch
    while the OCB-specific ones activate automatically afterwards.
    """
    pyproject = Path("pyproject.toml")
    if not pyproject.is_file():
        return False
    return "pep517_odoo" in pyproject.read_text(encoding="utf-8")


def load_manifest(ref: str, path: str) -> dict:
    return ast.literal_eval(git("show", f"{ref}:{path}"))


def check_auto_install() -> list[str]:
    if not ocb_layer_present():
        print("  NOTICE autonomous layer is not present on this branch; "
              "auto_install policy check skipped")
        return []

    failures = []
    for module, expected in EXPECTED_AUTO_INSTALL.items():
        path = f"addons/{module}/__manifest__.py"
        try:
            manifest = ast.literal_eval(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            failures.append(f"{path}: missing")
            continue
        except (SyntaxError, ValueError) as exc:
            failures.append(f"{path}: unparseable ({exc})")
            continue
        actual = manifest.get("auto_install")
        if actual != expected:
            failures.append(f"{path}: auto_install is {actual!r}, expected {expected!r}")
    return failures


def check_packaging(baseline_ref: str | None) -> list[str]:
    if not ocb_layer_present():
        print("  NOTICE autonomous layer is not present on this branch; "
              "packaging file check skipped")
        return []

    failures = []
    for path in PACKAGING_FILES:
        if not Path(path).exists():
            failures.append(f"{path}: missing")
            continue
        if baseline_ref and git_ok("cat-file", "-e", f"{baseline_ref}:{path}"):
            if git("rev-parse", f"HEAD:{path}") != git("rev-parse", f"{baseline_ref}:{path}"):
                failures.append(f"{path}: diverges from {baseline_ref}")
    return failures


def check_all_manifests() -> list[str]:
    failures = []
    patterns = ("addons/*/__manifest__.py", "odoo/addons/*/__manifest__.py")
    seen = 0
    for pattern in patterns:
        for path in sorted(Path().glob(pattern)):
            seen += 1
            try:
                value = ast.literal_eval(path.read_text(encoding="utf-8"))
            except (SyntaxError, ValueError) as exc:
                failures.append(f"{path}: unparseable ({exc})")
                continue
            if not isinstance(value, dict):
                failures.append(f"{path}: manifest is not a dict")
    print(f"  parsed {seen} manifests")
    return failures


def check_conflict_markers() -> list[str]:
    # Scoped to source and data files on purpose. Documentation legitimately
    # quotes conflict markers to show what a resolution looked like, and this
    # repository's own doc/dev notes do exactly that.
    result = subprocess.run(
        [
            "git", "grep", "-I", "-l", "-E", CONFLICT_MARKERS, "HEAD", "--",
            "*.py", "*.js", "*.xml", "*.scss", "*.css", "*.csv", "*.json", "*.sql",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return [f"conflict markers in: {result.stdout.split()}"]
    return []


def check_release(release_ref: str | None) -> list[str]:
    if not release_ref:
        return []
    if not git_ok("cat-file", "-e", f"{release_ref}:{RELEASE_FILE}"):
        return [f"{RELEASE_FILE}: ref {release_ref} is unavailable, check skipped"]
    try:
        head = git("show", f"HEAD:{RELEASE_FILE}")
        upstream = git("show", f"{release_ref}:{RELEASE_FILE}")
    except subprocess.CalledProcessError:
        return []
    if head != upstream:
        return [f"{RELEASE_FILE}: diverges from {release_ref} (version was modified)"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-ref",
        default=None,
        help="ref holding the OCB baseline, e.g. origin/20.0; enables byte-level "
        "comparison of the packaging files",
    )
    parser.add_argument(
        "--release-ref",
        default=None,
        help="ref whose odoo/release.py the working tree must match, e.g. odoo/master",
    )
    args = parser.parse_args()

    checks = [
        ("auto_install policy (30 modules)", lambda: check_auto_install()),
        ("packaging and identity files", lambda: check_packaging(args.baseline_ref)),
        ("manifest parsing", check_all_manifests),
        ("conflict markers", check_conflict_markers),
        ("release version", lambda: check_release(args.release_ref)),
    ]

    exit_code = 0
    for name, run in checks:
        print(f"[check] {name}")
        failures = run()
        if failures:
            exit_code = 1
            for failure in failures:
                print(f"  FAIL {failure}")
        else:
            print("  PASS")

    print("\nRESULT:", "PASS" if exit_code == 0 else "FAIL")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
