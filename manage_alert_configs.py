#!/usr/bin/env python3
"""
Utility for managing JSON-based alert configurations.

Commands:
  list                  - Show discoverable profiles.
  clone <src> <dest>    - Copy a profile into the user dir.
  validate [profile]    - Validate one or all profiles against the schema.
  export-hardcoded PATH - Export the default hard-coded preset to a path.
  set-active PROFILE    - Mark a profile as the active selection.
  show-active           - Print the currently active profile name.
"""

import argparse
import shutil
from pathlib import Path
from typing import List, Optional

from alert_config_manager import AlertConfigManager


def cmd_list(_args: argparse.Namespace) -> int:
    manager = AlertConfigManager()
    entries = manager.list_profiles()
    if not entries:
        print("No alert profiles found.")
        return 1

    for entry in entries:
        print(f"{entry['name']}\t{entry['source']}\t{entry['path']}")
    return 0


def cmd_clone(args: argparse.Namespace) -> int:
    manager = AlertConfigManager()
    try:
        path = manager.create_config_copy(args.source, args.target)
        print(f"Copied '{args.source}' to '{path}'")
        return 0
    except FileNotFoundError as exc:
        print(exc)
        return 2
    except FileExistsError as exc:
        print(exc)
        return 3


def cmd_validate(args: argparse.Namespace) -> int:
    manager = AlertConfigManager()
    names: List[str]
    if args.profile:
        names = [args.profile]
    else:
        names = [entry["name"] for entry in manager.list_profiles()]

    failures = []
    for name in names:
        try:
            manager.validate_profile(name)
            print(f"Validated {name}")
        except Exception as exc:
            print(f"Validation failed for {name}: {exc}")
            failures.append(name)
    return 1 if failures else 0


def cmd_export(args: argparse.Namespace) -> int:
    manager = AlertConfigManager()
    default_path = manager.get_profile_path("default")
    if not default_path:
        print("Default preset not found.")
        return 1
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(default_path, output_path)
    print(f"Exported hardcoded preset to {output_path}")
    return 0


def cmd_set_active(args: argparse.Namespace) -> int:
    manager = AlertConfigManager()
    try:
        manager.set_active_profile(args.profile)
        print(f"Active profile set to {args.profile}")
        return 0
    except FileNotFoundError as exc:
        print(exc)
        return 1


def cmd_show_active(_args: argparse.Namespace) -> int:
    manager = AlertConfigManager()
    print(manager.get_active_profile_name())
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage JSON alert configurations for trading stats."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List all alert profiles.")

    clone_parser = subparsers.add_parser(
        "clone", help="Clone a profile into the user directory."
    )
    clone_parser.add_argument("source", help="Existing profile name.")
    clone_parser.add_argument("target", help="New profile name (saved under user/).")

    validate_parser = subparsers.add_parser(
        "validate", help="Validate configs against the schema."
    )
    validate_parser.add_argument(
        "--profile",
        "-p",
        help="Specific profile name to validate; defaults to all discovered profiles.",
    )

    export_parser = subparsers.add_parser(
        "export-hardcoded", help="Export the default hard-coded preset."
    )
    export_parser.add_argument(
        "output",
        help="Path to write the exported JSON.",
    )

    set_active_parser = subparsers.add_parser(
        "set-active", help="Mark a profile as active."
    )
    set_active_parser.add_argument(
        "profile", help="Profile name that should be active."
    )

    subparsers.add_parser("show-active", help="Print the active profile.")

    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "clone":
        return cmd_clone(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "export-hardcoded":
        return cmd_export(args)
    if args.command == "set-active":
        return cmd_set_active(args)
    if args.command == "show-active":
        return cmd_show_active(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
