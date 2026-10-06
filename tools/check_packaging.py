#!/usr/bin/env python3
"""Assertions for the OCB packaging layer.

Two modes:

  archives   verify the sdist and wheels produced by `python -m build`
  editable   verify `pip install -e .` used setuptools' compat mode

The sdist checks matter because `backend-path = ["setup"]` only works if
`setup/pep517_odoo.py` actually lands in the sdist; if it does not, building a
wheel from the sdist fails, which is a path the wheel-only build never touches.

The editable check matters because setuptools >= 64 defaults to a dynamic
import finder that is incompatible with Odoo's flat layout; the OCB backend
forces `editable-mode = "compat"`, which must produce a `.pth` file instead.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

PACKAGING_IN_SDIST = ["setup/pep517_odoo.py", "pyproject.toml"]
MODULE_PROBE = "odoo/addons/sale/__init__.py"


def rel_under_root(name: str) -> str:
    """Strip the leading '<pkg>-<version>/' directory of an sdist member."""
    parts = name.split("/", 1)
    return parts[1] if len(parts) > 1 else ""


def ocb_layer_present() -> bool:
    """True when the working tree carries the OCB packaging layer.

    Without it, upstream Odoo packages the root `addons/` as a top-level
    package and there is no custom backend to exercise, so the OCB-specific
    assertions do not apply. They are reported as skipped instead of failed so
    that the gate stays green on branches which have not merged the backport
    yet, and starts enforcing automatically once they have.
    """
    pyproject = Path("pyproject.toml")
    if not pyproject.is_file():
        return False
    return "pep517_odoo" in pyproject.read_text(encoding="utf-8")


def check_sdist(path: Path, failures: list[str], strict: bool) -> None:
    print(f"  sdist: {path.name}")
    with tarfile.open(path) as tar:
        members = [m.name for m in tar.getmembers() if m.isfile()]
    stripped = [rel_under_root(m) for m in members]

    top_addons = [p for p in stripped if p.startswith("addons/")]

    if strict:
        for expected in PACKAGING_IN_SDIST:
            if expected not in stripped:
                failures.append(f"{path.name}: {expected} missing from sdist")
        if MODULE_PROBE not in stripped:
            failures.append(
                f"{path.name}: {MODULE_PROBE} missing - symlink step did not work"
            )

    if top_addons and strict:
        failures.append(
            f"{path.name}: top-level addons/ present ({len(top_addons)} entries) - "
            "'prune addons' did not take effect"
        )

    print(f"    files: {len(stripped)}, top-level addons/: {len(top_addons)}")


def check_wheel(path: Path, failures: list[str], strict: bool) -> None:
    print(f"  wheel: {path.name}")
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

    top_addons = [n for n in names if n.startswith("addons/")]

    if strict:
        if top_addons:
            failures.append(
                f"{path.name}: top-level addons/ present ({len(top_addons)} entries) - "
                "addons would be packaged twice"
            )
        if MODULE_PROBE not in names:
            failures.append(f"{path.name}: {MODULE_PROBE} missing")

    print(f"    files: {len(names)}, top-level addons/: {len(top_addons)}")


def collect(directory: Path, suffix: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{suffix}"))


def archives(args: argparse.Namespace) -> int:
    failures: list[str] = []
    strict = ocb_layer_present()
    if strict:
        print("  OCB layer detected; enforcing packaging assertions")
    else:
        print("  NOTICE OCB layer not present on this branch; reporting archive "
              "contents only, OCB assertions skipped")

    sdist_files: list[Path] = []
    for directory in args.sdist or []:
        sdist_files.extend(collect(directory, ".tar.gz"))
    if not sdist_files:
        failures.append("no sdist (.tar.gz) found in the supplied directories")
    for path in sdist_files:
        check_sdist(path, failures, strict)

    wheel_files: list[Path] = []
    for directory in args.wheel or []:
        wheel_files.extend(collect(directory, ".whl"))
    if not wheel_files:
        failures.append("no wheel (.whl) found in the supplied directories")
    for path in wheel_files:
        check_wheel(path, failures, strict)

    for failure in failures:
        print(f"  FAIL {failure}")
    print("  PASS" if not failures else "  FAILED")
    return 1 if failures else 0


def editable(_args: argparse.Namespace) -> int:
    import site
    import sysconfig

    failures: list[str] = []
    purelib = Path(sysconfig.get_paths()["purelib"])
    search_dirs = [purelib, *[Path(p) for p in site.getsitepackages()]]

    pth_files: list[Path] = []
    finder_files: list[Path] = []
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        pth_files.extend(directory.glob("__editable__*.pth"))
        finder_files.extend(directory.glob("__editable___*_finder.py"))
        finder_files.extend(directory.glob("__editable___*.py"))

    print(f"  .pth files:    {[p.name for p in pth_files]}")
    print(f"  finder files:  {[p.name for p in finder_files]}")

    if not pth_files:
        if ocb_layer_present():
            failures.append("no __editable__*.pth found - editable install did not happen")
        else:
            print("  NOTICE OCB layer not present; the custom backend that forces "
                  "compat mode is not in play, skipping mode assertions")
    if finder_files:
        if ocb_layer_present():
            failures.append(
                "found __editable___*_finder.py - setuptools used the dynamic finder mode, "
                "not compat mode; Odoo's flat layout will not resolve addons"
            )
        else:
            print("  NOTICE finder mode is expected without the OCB backend, ignoring")

    for path in pth_files:
        content = path.read_text(encoding="utf-8").strip()
        print(f"  {path.name}: {content}")
        if not content:
            failures.append(f"{path.name} is empty")

    for failure in failures:
        print(f"  FAIL {failure}")
    print("  PASS" if not failures else "  FAILED")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_archives = sub.add_parser("archives", help="verify sdist and wheels")
    p_archives.add_argument("--sdist", type=Path, action="append", help="directory holding .tar.gz")
    p_archives.add_argument("--wheel", type=Path, action="append", help="directory holding .whl")
    p_archives.set_defaults(func=archives)

    p_editable = sub.add_parser("editable", help="verify editable install used compat mode")
    p_editable.set_defaults(func=editable)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
