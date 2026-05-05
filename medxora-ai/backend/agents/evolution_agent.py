from services.evolution_engine import evolve_population, score_result
from services.report_parser import parse_mock_result


def run_evolution(base_strategy: dict, generations: int = 3, pop_size: int = 5) -> dict:
    best_strategy = base_strategy
    best_score = score_result(parse_mock_result(base_strategy["name"]))
    history = []

    for gen in range(1, generations + 1):
        children = evolve_population(best_strategy, size=pop_size)
        gen_results = []

        for child in children:
            metrics = parse_mock_result(child["name"])
            score = score_result(metrics)
            gen_results.append((child, score, metrics))

        gen_results.sort(key=lambda x: x[1], reverse=True)
        top_child, top_score, top_metrics = gen_results[0]

        history.append({
            "generation": gen,
            "best_name": top_child["name"],
            "best_score": top_score,
            "metrics": top_metrics,
        })

        if top_score > best_score:
            best_score = top_score
            best_strategy = top_child

    return {
        "original": base_strategy["name"],
        "evolved": best_strategy,
        "best_score": best_score,
        "generations": history,
        "improved": best_strategy["name"] != base_strategy["name"],
    }
