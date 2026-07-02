from datasets.tempobench.spec import TEMPO_BENCH
from obrist.collections import benchmark_job_collection
from obrist.dsl import BenchmarkCollection


def get_collection() -> BenchmarkCollection:
    """Return the packaged Tempo benchmark collection."""

    return benchmark_job_collection(TEMPO_BENCH)
