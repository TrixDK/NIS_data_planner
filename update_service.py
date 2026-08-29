from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass


GITHUB_API_VERSION = "2022-11-28"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    title: str
    release_url: str
    installer_url: str
    installer_name: str
    is_newer: bool


def normalize_repository(value: str) -> str:
    repository = value.strip().removesuffix(".git")
    prefixes = ("https://github.com/", "http://github.com/", "git@github.com:")
    for prefix in prefixes:
        if repository.startswith(prefix):
            repository = repository[len(prefix):]
            break
    repository = repository.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("GitHub-adressen skal være skrevet som ejer/repository.")
    return repository


def version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    if not numbers:
        raise ValueError(f"Ugyldigt versionsnummer: {value}")
    return tuple(int(number) for number in numbers[:4])


def release_from_payload(payload: dict, current_version: str) -> ReleaseInfo:
    tag = str(payload.get("tag_name", "")).strip()
    latest_version = tag.lstrip("vV")
    if not latest_version:
        raise ValueError("Den seneste GitHub-release mangler et versionsnummer.")

    assets = payload.get("assets", []) or []
    installers = [
        asset for asset in assets
        if str(asset.get("name", "")).lower().endswith(".exe")
        and "setup" in str(asset.get("name", "")).lower()
    ]
    installer = installers[0] if installers else {}
    return ReleaseInfo(
        version=latest_version,
        title=str(payload.get("name") or tag),
        release_url=str(payload.get("html_url", "")),
        installer_url=str(installer.get("browser_download_url", "")),
        installer_name=str(installer.get("name", "")),
        is_newer=version_tuple(latest_version) > version_tuple(current_version),
    )


def get_latest_release(repository: str, current_version: str, timeout: int = 12) -> ReleaseInfo:
    repository = normalize_repository(repository)
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "NIS-Data-Center-Planner-Updater",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return release_from_payload(payload, current_version)
