"""Dataset catalog for the Claw Engine.

Maintains a registry of known datasets (local toy data, GEO, GTEx, etc.)
and helpers to look them up by id.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Resolve the directory that *this* file lives in so local_path values
# can be expressed relative to the package root and still work regardless
# of the caller's cwd.
_PACKAGE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class DatasetEntry:
    """Describes a single dataset known to the engine."""

    id: str
    name: str
    source: str
    description: str
    url: str | None = None
    local_path: str | None = None
    task_types: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

CATALOG: list[DatasetEntry] = [
    DatasetEntry(
        id="toy_expression",
        name="Toy Synthetic Expression",
        source="local",
        description=(
            "A small synthetic gene-expression matrix (40 samples, 5 genes) "
            "with a planted differential signal in gene_A between control and "
            "treatment groups.  Suitable for smoke-testing DE analysis pipelines."
        ),
        local_path=str(_PACKAGE_DIR / "toy_data" / "toy_expression.csv"),
        task_types=["differential_expression", "visualization", "smoke_test"],
    ),
    DatasetEntry(
        id="GSE12345",
        name="GEO Series GSE12345",
        source="GEO",
        description=(
            "Stub entry for a Gene Expression Omnibus dataset.  Real download "
            "logic is not yet implemented."
        ),
        url="https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE12345",
        task_types=["differential_expression", "pathway_analysis"],
    ),
    DatasetEntry(
        id="gtex_v8_sample",
        name="GTEx v8 Sample Dataset",
        source="GTEx",
        description=(
            "Stub entry for a GTEx Portal dataset (v8).  Real download logic "
            "is not yet implemented."
        ),
        url="https://gtexportal.org/api/v2/dataset",
        task_types=["tissue_expression", "eqtl"],
    ),
]

# Build an index for O(1) lookup by id.
_INDEX: dict[str, DatasetEntry] = {entry.id: entry for entry in CATALOG}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_dataset(dataset_id: str) -> DatasetEntry:
    """Return the catalog entry for *dataset_id*.

    Raises
    ------
    KeyError
        If no dataset with the given id exists in the catalog.
    """
    try:
        return _INDEX[dataset_id]
    except KeyError:
        available = ", ".join(sorted(_INDEX))
        raise KeyError(
            f"Unknown dataset id {dataset_id!r}. "
            f"Available datasets: {available}"
        ) from None


def list_available(local_only: bool = False) -> list[DatasetEntry]:
    """Return catalog entries, optionally filtering to local-only datasets.

    Parameters
    ----------
    local_only : bool, default False
        When *True*, only entries whose ``local_path`` points to an existing
        file on disk are returned.
    """
    if not local_only:
        return list(CATALOG)

    return [
        entry
        for entry in CATALOG
        if entry.local_path is not None and os.path.isfile(entry.local_path)
    ]
