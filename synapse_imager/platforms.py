# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Registry-driven build entry point for Synapse device images.

The registry in ``platforms.ini`` is the single place to add a board or a new
platform. Every target becomes one entry in the release workflow matrix, so
adding a board does not require editing the workflow.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import shlex
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

IMAGER_DIR = Path(__file__).resolve().parent
REPO_ROOT = IMAGER_DIR.parent
REGISTRY_PATH = IMAGER_DIR / "platforms.ini"

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ENV_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_RUNNER = "ubuntu-24.04"
DEFAULT_TIMEOUT = 360
DEFAULT_FREE_DISK = True

PLATFORM_KEYS = {
    "name",
    "builder",
    "setup",
    "runner",
    "timeout",
    "free_disk",
    "artifact",
}
TARGET_KEYS = {
    "platform",
    "name",
    "runner",
    "timeout",
    "free_disk",
    "artifact",
}


class RegistryError(RuntimeError):
    """Raised when the platform registry is invalid."""


@dataclass(frozen=True)
class Defaults:
    """Values inherited by platforms and targets."""

    runner: str
    timeout: int
    freeDisk: bool


@dataclass(frozen=True)
class Target:
    """One buildable image or overlay."""

    id: str
    platform: str
    name: str
    env: dict[str, str]
    runner: str
    timeout: int
    freeDisk: bool
    artifact: str


@dataclass(frozen=True)
class Platform:
    """A family of targets built by the same script."""

    id: str
    name: str
    builder: str
    setup: str
    runner: str
    timeout: int
    freeDisk: bool
    artifact: str
    env: dict[str, str]
    targets: list[Target] = field(default_factory=list)


@dataclass(frozen=True)
class _TargetSpec:
    """Target values before artifact names are resolved."""

    id: str
    platform: str
    name: str
    env: dict[str, str]
    runner: str
    timeout: int
    freeDisk: bool
    artifact: str


def _readParser(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = lambda optionstr: optionstr
    try:
        with path.open(encoding="utf-8") as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error) as error:
        raise RegistryError(f"Could not read {path}: {error}") from error
    return parser


def _parseBool(value: str, context: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RegistryError(f"{context} must be true or false, got {value!r}")


def _parseInt(value: str, context: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise RegistryError(f"{context} must be an integer, got {value!r}") from error
    if parsed <= 0:
        raise RegistryError(f"{context} must be positive, got {parsed}")
    return parsed


def _required(
    section: configparser.SectionProxy, key: str, context: str
) -> str:
    value = section.get(key, "").strip()
    if not value:
        raise RegistryError(f"[{context}] is missing required key {key!r}")
    return value


def _optionalBool(
    section: configparser.SectionProxy,
    key: str,
    default: bool,
    context: str,
) -> bool:
    value = section.get(key)
    if value is None:
        return default
    return _parseBool(value, f"[{context}] {key}")


def _optionalInt(
    section: configparser.SectionProxy,
    key: str,
    default: int,
    context: str,
) -> int:
    value = section.get(key)
    if value is None:
        return default
    return _parseInt(value, f"[{context}] {key}")


def _checkKeys(
    section: configparser.SectionProxy,
    allowed: set[str],
    context: str,
) -> None:
    for key in section:
        if key.startswith("env."):
            continue
        if key not in allowed:
            raise RegistryError(f"[{context}] has unknown key {key!r}")


def _envFrom(
    section: configparser.SectionProxy, context: str
) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in section.items():
        if not key.startswith("env."):
            continue
        name = key[len("env.") :]
        if not ENV_PATTERN.match(name):
            raise RegistryError(
                f"[{context}] has invalid environment name {name!r}"
            )
        env[name] = value.strip()
    return env


def _resolvePath(relative: str, context: str) -> Path:
    path = (IMAGER_DIR / relative).resolve()
    try:
        path.relative_to(IMAGER_DIR)
    except ValueError as error:
        raise RegistryError(
            f"{context} must stay inside {IMAGER_DIR}: {relative!r}"
        ) from error
    return path


def _resolveArtifact(
    *,
    platformArtifact: str,
    platformId: str,
    targetId: str,
    targetArtifact: str,
    targetCount: int,
) -> str:
    if targetArtifact:
        return targetArtifact
    if not platformArtifact:
        return f"synapse-{targetId}"
    if targetCount == 1 or targetId == platformId:
        return platformArtifact

    suffix = targetId
    prefix = f"{platformId}-"
    if suffix.startswith(prefix):
        suffix = suffix[len(prefix) :]
    return f"{platformArtifact}-{suffix}"


def _parseDefaults(
    parser: configparser.ConfigParser,
) -> Defaults:
    if not parser.has_section("defaults"):
        return Defaults(
            runner=DEFAULT_RUNNER,
            timeout=DEFAULT_TIMEOUT,
            freeDisk=DEFAULT_FREE_DISK,
        )

    section = parser["defaults"]
    for key in section:
        if key not in {"runner", "timeout", "free_disk"}:
            raise RegistryError(f"[defaults] has unknown key {key!r}")

    return Defaults(
        runner=section.get("runner", DEFAULT_RUNNER).strip() or DEFAULT_RUNNER,
        timeout=_optionalInt(section, "timeout", DEFAULT_TIMEOUT, "defaults"),
        freeDisk=_optionalBool(
            section, "free_disk", DEFAULT_FREE_DISK, "defaults"
        ),
    )


def loadRegistry(path: Path = REGISTRY_PATH) -> list[Platform]:
    """Load and validate the platform registry."""
    parser = _readParser(path)
    defaults = _parseDefaults(parser)

    platformSections: list[str] = []
    targetSections: list[str] = []
    for sectionName in parser.sections():
        if sectionName == "defaults":
            continue
        if sectionName.startswith("platform."):
            platformSections.append(sectionName)
        elif sectionName.startswith("target."):
            targetSections.append(sectionName)
        else:
            raise RegistryError(f"Unknown section [{sectionName}]")

    if not platformSections:
        raise RegistryError("No [platform.<id>] sections found")

    platforms: list[Platform] = []
    for sectionName in platformSections:
        section = parser[sectionName]
        context = sectionName
        platformId = sectionName[len("platform.") :]
        if not ID_PATTERN.match(platformId):
            raise RegistryError(
                f"[{context}] has invalid id {platformId!r}; "
                "use lowercase letters, digits, and dashes"
            )

        _checkKeys(section, PLATFORM_KEYS, context)
        builder = _required(section, "builder", context)
        setup = section.get("setup", "").strip()
        platforms.append(
            Platform(
                id=platformId,
                name=_required(section, "name", context),
                builder=builder,
                setup=setup,
                runner=section.get("runner", defaults.runner).strip()
                or defaults.runner,
                timeout=_optionalInt(
                    section, "timeout", defaults.timeout, context
                ),
                freeDisk=_optionalBool(
                    section, "free_disk", defaults.freeDisk, context
                ),
                artifact=section.get("artifact", "").strip(),
                env=_envFrom(section, context),
            )
        )

    platformById = {platform.id: platform for platform in platforms}
    specs: list[_TargetSpec] = []
    for sectionName in targetSections:
        section = parser[sectionName]
        context = sectionName
        targetId = sectionName[len("target.") :]
        if not ID_PATTERN.match(targetId):
            raise RegistryError(
                f"[{context}] has invalid id {targetId!r}; "
                "use lowercase letters, digits, and dashes"
            )

        _checkKeys(section, TARGET_KEYS, context)
        platformId = _required(section, "platform", context)
        platform = platformById.get(platformId)
        if platform is None:
            raise RegistryError(
                f"[{context}] references unknown platform {platformId!r}"
            )

        specs.append(
            _TargetSpec(
                id=targetId,
                platform=platformId,
                name=_required(section, "name", context),
                env={**platform.env, **_envFrom(section, context)},
                runner=section.get("runner", platform.runner).strip()
                or platform.runner,
                timeout=_optionalInt(
                    section, "timeout", platform.timeout, context
                ),
                freeDisk=_optionalBool(
                    section, "free_disk", platform.freeDisk, context
                ),
                artifact=section.get("artifact", "").strip(),
            )
        )

    counts = Counter(spec.platform for spec in specs)
    for spec in specs:
        platform = platformById[spec.platform]
        platform.targets.append(
            Target(
                id=spec.id,
                platform=spec.platform,
                name=spec.name,
                env=spec.env,
                runner=spec.runner,
                timeout=spec.timeout,
                freeDisk=spec.freeDisk,
                artifact=_resolveArtifact(
                    platformArtifact=platform.artifact,
                    platformId=platform.id,
                    targetId=spec.id,
                    targetArtifact=spec.artifact,
                    targetCount=counts[platform.id],
                ),
            )
        )

    artifacts: dict[str, str] = {}
    for platform in platforms:
        if not platform.targets:
            raise RegistryError(
                f"Platform {platform.id!r} has no [target.<id>] sections"
            )

        builderPath = _resolvePath(
            platform.builder, f"[platform.{platform.id}] builder"
        )
        if not builderPath.is_file():
            raise RegistryError(
                f"[platform.{platform.id}] builder not found: {builderPath}"
            )

        if platform.setup:
            setupPath = _resolvePath(
                platform.setup, f"[platform.{platform.id}] setup"
            )
            if not setupPath.is_file():
                raise RegistryError(
                    f"[platform.{platform.id}] setup not found: {setupPath}"
                )

        for target in platform.targets:
            previous = artifacts.get(target.artifact)
            if previous is not None:
                raise RegistryError(
                    f"Targets {previous!r} and {target.id!r} share artifact "
                    f"{target.artifact!r}; set a distinct artifact"
                )
            artifacts[target.artifact] = target.id

    return platforms


def selectTargets(
    platforms: list[Platform], selection: str | None
) -> list[tuple[Platform, Target]]:
    """Resolve a comma-separated list of platform or target ids."""
    allTargets = [(platform, target) for platform in platforms for target in platform.targets]
    if not selection or selection.strip().lower() == "all":
        return allTargets

    byTarget = {target.id: (platform, target) for platform, target in allTargets}
    byPlatform = {platform.id: platform for platform in platforms}
    available = ", ".join(sorted(byTarget))

    selected: list[tuple[Platform, Target]] = []
    seen: set[str] = set()
    for token in selection.split(","):
        token = token.strip()
        if not token:
            continue
        if token.lower() == "all":
            candidates = allTargets
        elif token in byTarget:
            candidates = [byTarget[token]]
        elif token in byPlatform:
            candidates = [
                (byPlatform[token], target)
                for target in byPlatform[token].targets
            ]
        else:
            raise RegistryError(
                f"Unknown platform or target: {token!r}. Available: {available}"
            )

        for platform, target in candidates:
            if target.id in seen:
                continue
            seen.add(target.id)
            selected.append((platform, target))

    if not selected:
        raise RegistryError("No targets selected")
    return selected


def findTarget(
    platforms: list[Platform], targetId: str
) -> tuple[Platform, Target]:
    for platform in platforms:
        for target in platform.targets:
            if target.id == targetId:
                return platform, target

    available = ", ".join(
        target.id for platform in platforms for target in platform.targets
    )
    raise RegistryError(f"Unknown target: {targetId!r}. Available: {available}")


def commandList(platforms: list[Platform]) -> int:
    for platform in platforms:
        print(f"{platform.id}: {platform.name} ({platform.builder})")
        for target in platform.targets:
            print(
                f"  {target.id:<22} {target.name}  [{target.artifact}]"
            )
    return 0


def commandMatrix(platforms: list[Platform], selection: str, pretty: bool) -> int:
    matrix = [
        {
            "platform": platform.id,
            "target": target.id,
            "name": target.name,
            "runner": target.runner,
            "timeout": target.timeout,
            "free_disk": target.freeDisk,
            "setup": platform.setup,
            "artifact": target.artifact,
        }
        for platform, target in selectTargets(platforms, selection)
    ]
    if pretty:
        print(json.dumps(matrix, indent=2, sort_keys=True))
    else:
        print(json.dumps(matrix, separators=(",", ":"), sort_keys=True))
    return 0


def commandEnv(platforms: list[Platform], targetId: str, asJson: bool) -> int:
    platform, target = findTarget(platforms, targetId)
    values = {
        **target.env,
        "SYNAPSE_PLATFORM": platform.id,
        "SYNAPSE_TARGET": target.id,
    }
    if asJson:
        print(json.dumps(values, indent=2, sort_keys=True))
    else:
        for key, value in values.items():
            print(f"export {key}={shlex.quote(value)}")
    return 0


def commandBuild(
    platforms: list[Platform], targetId: str, dryRun: bool
) -> int:
    platform, target = findTarget(platforms, targetId)
    builder = _resolvePath(
        platform.builder, f"[platform.{platform.id}] builder"
    )

    env = dict(os.environ)
    for key, value in target.env.items():
        env.setdefault(key, value)
    env["SYNAPSE_PLATFORM"] = platform.id
    env["SYNAPSE_TARGET"] = target.id

    if dryRun:
        print(
            json.dumps(
                {
                    "platform": platform.id,
                    "target": target.id,
                    "builder": platform.builder,
                    "command": ["bash", platform.builder],
                    "env": {
                        **target.env,
                        "SYNAPSE_PLATFORM": platform.id,
                        "SYNAPSE_TARGET": target.id,
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(
        f"Building {target.name} ({target.id}) with {platform.builder}...",
        file=sys.stderr,
    )
    os.chdir(REPO_ROOT)
    os.execvpe("bash", ["bash", str(builder)], env)


def commandValidate(platforms: list[Platform]) -> int:
    count = sum(len(platform.targets) for platform in platforms)
    print(f"Registry OK: {len(platforms)} platforms, {count} targets")
    return 0


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="platforms.py",
        description=(
            "Build Synapse device images from the platform registry in "
            "synapse_imager/platforms.ini."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "list", help="List platforms and targets."
    )

    matrixParser = subparsers.add_parser(
        "matrix", help="Print the GitHub Actions build matrix as JSON."
    )
    matrixParser.add_argument(
        "--targets",
        default="all",
        help="Comma-separated platform or target ids (default: all).",
    )
    matrixParser.add_argument(
        "--pretty", action="store_true", help="Indent the JSON output."
    )

    buildParser = subparsers.add_parser(
        "build", help="Build one target."
    )
    buildParser.add_argument("target", help="Target id from platforms.ini.")
    buildParser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved builder and environment without building.",
    )

    envParser = subparsers.add_parser(
        "env", help="Print the environment for a target."
    )
    envParser.add_argument("target", help="Target id from platforms.ini.")
    envParser.add_argument(
        "--json", action="store_true", help="Print JSON instead of shell exports."
    )

    subparsers.add_parser("validate", help="Validate platforms.ini.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = buildParser().parse_args(argv)
    try:
        platforms = loadRegistry()
        if args.command == "list":
            return commandList(platforms)
        if args.command == "matrix":
            return commandMatrix(platforms, args.targets, args.pretty)
        if args.command == "build":
            return commandBuild(platforms, args.target, args.dry_run)
        if args.command == "env":
            return commandEnv(platforms, args.target, args.json)
        if args.command == "validate":
            return commandValidate(platforms)
    except RegistryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
