"""Download helpers for Claw Engine datasets.

Provides thin wrappers that fetch remote datasets to a local directory.
For local/toy datasets the helpers are no-ops; for GEO and GTEx sources
the actual HTTP logic is intentionally stubbed out for now.
"""

from __future__ import annotations

import os
import shutil
import urllib.request
from pathlib import Path
from urllib.error import URLError

from .catalog import DatasetEntry, get_dataset


def download_dataset(entry: DatasetEntry, dest_dir: str) -> str:
    """Download the dataset described by *entry* into *dest_dir*.

    Parameters
    ----------
    entry : DatasetEntry
        Catalog entry for the dataset to download.
    dest_dir : str
        Directory where the downloaded file should be stored.

    Returns
    -------
    str
        Absolute path to the downloaded (or already-existing) local file.

    Raises
    ------
    NotImplementedError
        For remote sources (GEO, GTEx) whose download logic is not yet
        implemented.
    FileNotFoundError
        If a local dataset's file is missing from disk.
    OSError
        On network errors when fetching a remote resource.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Local datasets — just verify the file exists (or copy it).
    # ------------------------------------------------------------------
    if entry.source == "local":
        if entry.local_path is None:
            raise FileNotFoundError(
                f"Dataset {entry.id!r} is marked as local but has no local_path."
            )
        src = Path(entry.local_path)
        if not src.is_file():
            raise FileNotFoundError(
                f"Local dataset file not found: {src}"
            )
        target = dest / src.name
        if not target.is_file():
            shutil.copy2(src, target)
        return str(target.resolve())

    # ------------------------------------------------------------------
    # Remote sources — stub implementations.
    # ------------------------------------------------------------------
    if entry.source == "GEO":
        print(
            f"[downloader] GEO download for {entry.id!r} would fetch from "
            f"{entry.url} — not yet implemented."
        )
        raise NotImplementedError(
            f"Downloading from GEO is not yet implemented (dataset {entry.id!r})."
        )

    if entry.source == "GTEx":
        print(
            f"[downloader] GTEx download for {entry.id!r} would fetch from "
            f"{entry.url} — not yet implemented."
        )
        raise NotImplementedError(
            f"Downloading from GTEx is not yet implemented (dataset {entry.id!r})."
        )

    # ------------------------------------------------------------------
    # Generic URL fallback (future-proofing).
    # ------------------------------------------------------------------
    if entry.url is not None:
        filename = entry.url.rsplit("/", 1)[-1] or f"{entry.id}.dat"
        target = dest / filename
        if target.is_file():
            return str(target.resolve())

        print(f"[downloader] Fetching {entry.url} ...")
        try:
            urllib.request.urlretrieve(entry.url, target)
        except (URLError, OSError) as exc:
            raise OSError(
                f"Failed to download {entry.url}: {exc}"
            ) from exc
        return str(target.resolve())

    raise ValueError(
        f"Dataset {entry.id!r} has no url and is not local — cannot download."
    )


def ensure_dataset(dataset_id: str) -> str:
    """Make sure the dataset identified by *dataset_id* is available locally.

    If the dataset already exists on disk, its path is returned immediately.
    Otherwise an attempt is made to download it.

    Parameters
    ----------
    dataset_id : str
        Identifier that matches a ``DatasetEntry.id`` in the catalog.

    Returns
    -------
    str
        Absolute path to the local file.
    """
    entry = get_dataset(dataset_id)  # raises KeyError if unknown

    # Fast path: already on disk.
    if entry.local_path is not None:
        local = Path(entry.local_path)
        if local.is_file():
            return str(local.resolve())

    # Need to download — put it next to the package's toy_data directory.
    default_dest = str(Path(__file__).resolve().parent / "downloaded")
    return download_dataset(entry, dest_dir=default_dest)
