from pydantic import BaseModel


class BenchmarkOutcome(BaseModel):
    benchmark_ticker: str
    stock_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float


DEFAULT_BENCHMARKS = {
    "software": "QQQ",
    "big_tech": "QQQ",
    "semiconductor": "SMH",
    "semiconductors": "SMH",
    "general": "SPY",
}


def calculate_excess_return(stock_return: float, benchmark_return: float) -> float:
    return stock_return - benchmark_return


def calculate_benchmark_outcome(
    benchmark_ticker: str,
    stock_return_pct: float,
    benchmark_return_pct: float,
) -> BenchmarkOutcome:
    return BenchmarkOutcome(
        benchmark_ticker=benchmark_ticker,
        stock_return_pct=stock_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        excess_return_pct=calculate_excess_return(stock_return_pct, benchmark_return_pct),
    )


def default_benchmark_for_tags(tags: list[str]) -> str:
    normalized = {tag.lower() for tag in tags}
    for key, ticker in DEFAULT_BENCHMARKS.items():
        if key in normalized:
            return ticker
    return DEFAULT_BENCHMARKS["general"]

