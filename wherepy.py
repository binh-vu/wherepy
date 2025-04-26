from __future__ import annotations

import os
import re
import subprocess
from enum import Enum
from math import e
from pathlib import Path
from typing import Annotated, Literal, Optional, Tuple, Union

import typer


class InterpreterType(str, Enum):
    """Enum for interpreter types."""

    cpython = "cpython"
    pypy = "pypy"
    all = "all"


def is_python_home(dir: Union[str, Path]):
    """Check if the directory is a python home."""
    return any(
        os.path.exists(os.path.join(dir, "bin", name))
        for name in ["python", "python2", "python3"]
    )


def get_python(home: Union[str, Path]) -> str:
    """Get the python executable from the specified home directory."""
    for name in ["python", "python2", "python3"]:
        path = os.path.join(home, "bin", name)
        if os.path.exists(path):
            return path
    raise ValueError("python not found in {}".format(home))


def get_python_version(home: Union[str, Path]) -> Tuple[str, InterpreterType]:
    """Get python's version and whether it is cpython or pypy."""
    output = subprocess.check_output([get_python(home), "-V"]).decode().strip()
    m = re.match(r"Python ([\d\.)]+)", output)
    assert m is not None
    version = m.group(1)
    pytype = (
        InterpreterType.pypy if output.find("PyPy") != -1 else InterpreterType.cpython
    )
    return version, pytype


app = typer.Typer(pretty_exceptions_short=True, pretty_exceptions_enable=False)


@app.command()
def find_pythons(
    search_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--search-dir",
            help="Directory to search for Python homes. This has precedence over --python-home and --python-homes",
            exists=True,
            file_okay=False,
        ),
    ],
    python_home: Annotated[
        Optional[str],
        typer.Option(
            help="Specific Python home directory to search. This has precedence over --python-homes",
        ),
    ] = None,
    python_homes: Annotated[
        Optional[str],
        typer.Option(
            help="Colon-separated list of directories to search for Python homes"
        ),
    ] = None,
    python_versions: Annotated[
        Optional[str],
        typer.Option(
            help="Comma-separated list of Python versions to filter the results",
        ),
    ] = None,
    minimum_version: Annotated[
        Optional[str],
        typer.Option(help="Minimum Python version to return"),
    ] = None,
    interpreter_type: Annotated[
        InterpreterType,
        typer.Option(
            help="Interpreter type to filter the results. Can be 'cpython', 'pypy', or 'all'",
        ),
    ] = InterpreterType.cpython,
    error_if_not_found: Annotated[
        bool,
        typer.Option(
            help="Raise an error if no Python home is found",
        ),
    ] = False,
):
    """
    Find Python interpreters based on the specified criteria.
    """
    if python_home is None and python_homes is None and search_dir is None:
        raise ValueError(
            "Either --search-dir, --python-home, or --python-homes must be provided."
        )

    homes = {}
    if search_dir is not None:
        for pyexec in search_dir.glob("**/bin/python*"):
            home = pyexec.parent.parent
            assert is_python_home(home)
            version, type = get_python_version(home)
            if interpreter_type == InterpreterType.all or type == interpreter_type:
                homes[home] = version
    elif python_home is not None:
        version, type = get_python_version(python_home)
        if interpreter_type == InterpreterType.all or type == interpreter_type:
            homes[python_home] = version
    else:
        assert python_homes is not None
        lst = python_homes.split(":")
        for path in lst:
            if is_python_home(path):
                # is the python directory
                version, type = get_python_version(path)
                if interpreter_type == InterpreterType.all or type == interpreter_type:
                    homes[path] = version
            else:
                subhomes = {}
                for subpath in os.listdir(path):
                    home = os.path.join(path, subpath)
                    if not is_python_home(home):
                        continue

                    version, pytype = get_python_version(home)
                    if (
                        interpreter_type != InterpreterType.all
                        and pytype != interpreter_type
                    ):
                        continue

                    # do not keep different patches (only keep major.minor)
                    mm_version = ".".join(version.split(".")[:2])
                    subhomes[mm_version, pytype] = (home, version)

                for home, version in subhomes.values():
                    homes[home] = version

    if python_versions is not None:
        versions = python_versions.split(",")
        filtered_homes = []
        for home, home_version in homes.items():
            for version in versions:
                if home_version.startswith(version):
                    filtered_homes.append(home)
                    break

        homes = {h: homes[h] for h in filtered_homes}

    if minimum_version is not None:
        minimum_version_parts = [int(d) for d in minimum_version.split(".")]
        filtered_homes = []
        for home, home_version in homes.items():
            pyversion = home_version.split(".")
            if all(
                int(pyversion[i]) >= minimum_version_parts[i]
                for i in range(len(minimum_version_parts))
            ):
                filtered_homes.append(home)

        homes = {h: homes[h] for h in filtered_homes}

    if len(homes) == 0 and error_if_not_found:
        print("No Python home found")
        exit(1)

    print(":".join(str(path) for path in homes))
    exit(0)


if __name__ == "__main__":
    app()
