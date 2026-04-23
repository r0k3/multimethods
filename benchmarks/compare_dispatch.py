from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from timeit import timeit
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from multimethods import multimethod


@dataclass(slots=True)
class Benchmark:
    name: str
    statement: str


def _optional_import(module_name: str) -> Any | None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def build_ours() -> dict[str, Any]:
    @multimethod
    def one(x: int):
        return x

    @one.register
    def _(x: str):
        return x

    @multimethod
    def two(x: int, y: int):
        return x + y

    @two.register
    def _(x: str, y: str):
        return x + y

    one(1)
    two(1, 2)
    return {"ours_one": one, "ours_two": two}


def maybe_build_multimethod() -> dict[str, Any]:
    module = _optional_import("multimethod")
    if module is None:
        return {}

    mm = module.multimethod
    mmd = module.multidispatch

    @mm
    def mm_one(x: int):
        return x

    @mm_one.register
    def _(x: str):
        return x

    @mmd
    def mmd_one(x: int):
        return x

    @mmd_one.register
    def _(x: str):
        return x

    @mm
    def mm_two(x: int, y: int):
        return x + y

    @mm_two.register
    def _(x: str, y: str):
        return x + y

    @mmd
    def mmd_two(x: int, y: int):
        return x + y

    @mmd_two.register
    def _(x: str, y: str):
        return x + y

    return locals()


def maybe_build_multipledispatch() -> dict[str, Any]:
    module = _optional_import("multipledispatch")
    if module is None:
        return {}

    dispatch = module.dispatch

    @dispatch(int)
    def md_one(x):
        return x

    @dispatch(str)
    def md_one(x):
        return x

    @dispatch(int, int)
    def md_two(x, y):
        return x + y

    @dispatch(str, str)
    def md_two(x, y):
        return x + y

    return locals()


def maybe_build_plum() -> dict[str, Any]:
    module = _optional_import("plum")
    if module is None:
        return {}

    dispatch = module.dispatch

    @dispatch
    def pd_one(x: int):
        return x

    @dispatch
    def pd_one(x: str):
        return x

    @dispatch
    def pd_two(x: int, y: int):
        return x + y

    @dispatch
    def pd_two(x: str, y: str):
        return x + y

    return locals()


def maybe_build_ovld() -> dict[str, Any]:
    module = _optional_import("ovld")
    if module is None:
        return {}

    ovld = module.ovld

    @ovld
    def od_one(x: int):
        return x

    @ovld
    def od_one(x: str):
        return x

    @ovld
    def od_two(x: int, y: int):
        return x + y

    @ovld
    def od_two(x: str, y: str):
        return x + y

    return locals()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare dispatch speed across libraries.")
    parser.add_argument("--calls", type=int, default=500_000, help="Number of calls per benchmark")
    args = parser.parse_args()

    namespace: dict[str, Any] = {}
    namespace.update(build_ours())
    namespace.update(maybe_build_multimethod())
    namespace.update(maybe_build_multipledispatch())
    namespace.update(maybe_build_plum())
    namespace.update(maybe_build_ovld())

    benchmarks = [
        Benchmark("ours-1", "ours_one(1)"),
        Benchmark("ours-2", "ours_two(1, 2)"),
        Benchmark("multimethod-1", "mm_one(1)"),
        Benchmark("multimethod-2", "mm_two(1, 2)"),
        Benchmark("multidispatch-1", "mmd_one(1)"),
        Benchmark("multidispatch-2", "mmd_two(1, 2)"),
        Benchmark("multipledispatch-1", "md_one(1)"),
        Benchmark("multipledispatch-2", "md_two(1, 2)"),
        Benchmark("plum-1", "pd_one(1)"),
        Benchmark("plum-2", "pd_two(1, 2)"),
        Benchmark("ovld-1", "od_one(1)"),
        Benchmark("ovld-2", "od_two(1, 2)"),
    ]

    selected = []
    for benchmark in benchmarks:
        symbol = benchmark.statement.split("(", 1)[0]
        if symbol in namespace:
            selected.append(benchmark)

    for benchmark in selected:
        elapsed = timeit(benchmark.statement, number=args.calls, globals=namespace)
        rate = args.calls / elapsed
        print(f"{benchmark.name:20s} {elapsed:.4f}s  {rate:,.0f} calls/s")


if __name__ == "__main__":
    main()
