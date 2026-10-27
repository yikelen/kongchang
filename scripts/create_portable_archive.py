"""Create a ZIP with correctly marked UTF-8 names from a staged folder."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def create_archive(source: Path, destination: Path) -> None:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError(f"找不到便携包目录：{source}")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(source.rglob("*")):
            if file.is_file():
                archive.write(file, Path(source.name) / file.relative_to(source))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    create_archive(args.source, args.destination)


if __name__ == "__main__":
    main()
