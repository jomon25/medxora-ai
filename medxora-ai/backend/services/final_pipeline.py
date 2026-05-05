from agents.backtest_analyst import analyze
from services.live_pipeline import run_live_pipeline
from services.logger import log_event
from services.timeframes import normalize_timeframe


async def run_full_pipeline(mock: bool = True, timeframe: str = "M15"):
    """
    Final demo pipeline route.
    Reuses the stronger live pipeline so websocket updates, checkpoints,
    memory, reviews, and DB persistence all stay in sync.
    """
    normalized_timeframe = normalize_timeframe(timeframe)
    log_event(
        "INFO",
        f"Final pipeline requested ({normalized_timeframe}, mock={mock})",
        source="final_pipeline",
    )

    result = await run_live_pipeline(mock=mock, timeframe=normalized_timeframe)
    if result.get("status") != "success":
        log_event(
            "ERROR",
            f"Final pipeline failed at {result.get('stage', 'unknown_stage')}: {result.get('reason', 'No reason provided')}",
            source="final_pipeline",
        )
        return result

    strategy_name = result.get("strategy_name") or result.get("strategy", {}).get("name")
    report_file = result.get("report_file")
    analysis = analyze(
        strategy_name,
        report_file,
        use_mock=mock or not report_file,
    )

    enriched = {
        **result,
        "mock": mock,
        "analysis": analysis,
        "risk": result.get("pretrade_portfolio_decision"),
    }
    log_event(
        "INFO",
        f"Final pipeline completed for {strategy_name}",
        source="final_pipeline",
    )
    return enriched
