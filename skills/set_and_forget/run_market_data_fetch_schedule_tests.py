import json
from pathlib import Path

import market_data_fetch_schedule


BASE_DIR = Path(__file__).resolve().parent
FIXTURES_FILE = BASE_DIR / "market_data_fetch_schedule_test_fixtures.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def run_valid_case(case: dict):
    plan = market_data_fetch_schedule.build_fetch_schedule(**case["input"])
    expected = case["expected"]
    budget = plan["request_budget"]
    schedule = plan["schedule"]

    if "normalized_pairs" in expected:
        flattened_pairs = []
        for bucket in schedule["buckets"]:
            flattened_pairs.extend(bucket["pairs"])
        assert flattened_pairs == expected["normalized_pairs"], f"{case['id']}: normalized pair order mismatch"

    assert budget["pairs_per_minute"] == expected["pairs_per_minute"], f"{case['id']}: pairs_per_minute mismatch"
    assert budget["effective_requests_per_minute"] == expected["effective_requests_per_minute"], (
        f"{case['id']}: effective request budget mismatch"
    )
    assert budget["unused_requests_per_minute"] == expected["unused_requests_per_minute"], (
        f"{case['id']}: unused request budget mismatch"
    )
    assert len(schedule["buckets"]) == expected["bucket_count"], f"{case['id']}: bucket count mismatch"

    if "first_bucket_pairs" in expected:
        assert schedule["buckets"][0]["pairs"] == expected["first_bucket_pairs"], (
            f"{case['id']}: first bucket pair order mismatch"
        )
    if "last_bucket_time" in expected:
        assert schedule["buckets"][-1]["scheduled_for"] == expected["last_bucket_time"], (
            f"{case['id']}: last bucket time mismatch"
        )

    return {
        "id": case["id"],
        "bucket_count": len(schedule["buckets"]),
        "pairs_per_minute": budget["pairs_per_minute"],
    }


def run_error_case(case: dict):
    try:
        market_data_fetch_schedule.build_fetch_schedule(**case["input"])
    except ValueError as error:
        assert case["expected_error"] in str(error), f"{case['id']}: unexpected error {error}"
        return {
            "id": case["id"],
            "error": str(error),
        }

    raise AssertionError(f"{case['id']}: expected a ValueError")


def main():
    fixtures = load_json(FIXTURES_FILE)
    results = []
    for case in fixtures["cases"]:
        if "expected_error" in case:
            results.append(run_error_case(case))
            continue
        results.append(run_valid_case(case))

    print(f"PASS {len(results)}/{len(results)} market data fetch schedule scenarios")
    for result in results:
        if "error" in result:
            print(f"- {result['id']}: error_ok=True")
            continue
        print(
            f"- {result['id']}: bucket_count={result['bucket_count']} "
            f"pairs_per_minute={result['pairs_per_minute']}"
        )


if __name__ == "__main__":
    main()
