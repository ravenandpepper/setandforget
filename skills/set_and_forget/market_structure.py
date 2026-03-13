import json
from pathlib import Path

import feature_snapshot


BASE_DIR = Path(__file__).resolve().parent
MARKET_STRUCTURE_INPUT_SCHEMA_FILE = BASE_DIR / "market_structure_input_schema.json"
FEATURE_SNAPSHOT_SCHEMA_FILE = BASE_DIR / "feature_snapshot_schema.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_market_structure_input(payload: dict, schema: dict):
    errors = []
    errors.extend(_validate_sections(payload, schema.get("sections", []), []))
    errors.extend(validate_candle_sections(payload, schema.get("candle_item_schema", {})))
    errors.extend(validate_objective_context_consistency(payload))
    return errors


def _validate_sections(payload: dict, sections: list, path: list):
    errors = []
    for section in sections:
        section_name = section["name"]
        if section_name not in payload:
            if section.get("required", True):
                errors.append(f"Missing required section: {'.'.join(path + [section_name])}")
            continue

        section_payload = payload[section_name]
        if not isinstance(section_payload, dict):
            errors.append(f"Section {'.'.join(path + [section_name])} must be an object.")
            continue

        for field in section.get("fields", []):
            errors.extend(_validate_field(section_payload, field, path + [section_name]))

        if "sections" in section:
            errors.extend(_validate_sections(section_payload, section["sections"], path + [section_name]))

    return errors


def _validate_field(section_payload: dict, field: dict, path: list):
    errors = []
    name = field["name"]
    dotted = ".".join(path + [name])
    if field.get("required") and name not in section_payload:
        errors.append(f"Missing required field: {dotted}")
        return errors

    if name not in section_payload:
        return errors

    value = section_payload[name]
    expected_type = field["type"]
    if expected_type == "string" and not isinstance(value, str):
        errors.append(f"Field {dotted} must be of type string.")
        return errors
    if expected_type == "boolean" and not isinstance(value, bool):
        errors.append(f"Field {dotted} must be of type boolean.")
        return errors
    if expected_type == "integer" and not (isinstance(value, int) and not isinstance(value, bool)):
        errors.append(f"Field {dotted} must be of type integer.")
        return errors
    if expected_type == "number" and not (isinstance(value, (int, float)) and not isinstance(value, bool)):
        errors.append(f"Field {dotted} must be of type number.")
        return errors
    if expected_type == "array" and not isinstance(value, list):
        errors.append(f"Field {dotted} must be of type array.")
        return errors

    allowed_values = field.get("allowed_values")
    if allowed_values and value not in allowed_values:
        errors.append(f"Field {dotted} has invalid value {value!r}.")

    field_range = field.get("range")
    if field_range and isinstance(value, (int, float)) and not isinstance(value, bool):
        lower, upper = field_range
        if value < lower or value > upper:
            errors.append(f"Field {dotted} must be between {lower} and {upper}.")

    return errors


def validate_candle_sections(payload: dict, candle_schema: dict):
    errors = []
    candles_root = payload.get("candles", {})
    required_fields = candle_schema.get("required_fields", [])
    types = candle_schema.get("types", {})

    for timeframe in ["weekly", "daily", "h4"]:
        timeframe_payload = candles_root.get(timeframe, {})
        candles = timeframe_payload.get("candles")
        dotted = f"candles.{timeframe}.candles"

        if not isinstance(candles, list):
            errors.append(f"Field {dotted} must be an array of candle objects.")
            continue

        if len(candles) < 7:
            errors.append(f"Field {dotted} must contain at least 7 candles.")
            continue

        for index, candle in enumerate(candles):
            if not isinstance(candle, dict):
                errors.append(f"Field {dotted}[{index}] must be an object.")
                continue

            for required_field in required_fields:
                if required_field not in candle:
                    errors.append(f"Missing required field: {dotted}[{index}].{required_field}")
                    continue

                value = candle[required_field]
                expected_type = types.get(required_field)
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Field {dotted}[{index}].{required_field} must be of type string.")
                if expected_type == "number" and not (isinstance(value, (int, float)) and not isinstance(value, bool)):
                    errors.append(f"Field {dotted}[{index}].{required_field} must be of type number.")

            if all(key in candle for key in ["open", "high", "low", "close"]):
                if candle["high"] < max(candle["open"], candle["close"]):
                    errors.append(f"Field {dotted}[{index}].high must be >= open and close.")
                if candle["low"] > min(candle["open"], candle["close"]):
                    errors.append(f"Field {dotted}[{index}].low must be <= open and close.")

    return errors


def validate_objective_context_consistency(payload: dict):
    context = payload.get("objective_context", {})
    aoi = context.get("aoi_features", {})
    if not aoi:
        return []
    confluence_count = sum(
        1
        for key in ["has_sr", "has_order_block", "has_structural_level"]
        if aoi.get(key) is True
    )
    if "confluence_count" in aoi and aoi["confluence_count"] != confluence_count:
        return ["objective_context.aoi_features.confluence_count must match the AOI confluence booleans."]
    return []


def find_pivot_highs(candles: list):
    pivots = []
    for index in range(1, len(candles) - 1):
        if candles[index]["high"] > candles[index - 1]["high"] and candles[index]["high"] > candles[index + 1]["high"]:
            pivots.append({"index": index, "price": candles[index]["high"]})
    return pivots


def find_pivot_lows(candles: list):
    pivots = []
    for index in range(1, len(candles) - 1):
        if candles[index]["low"] < candles[index - 1]["low"] and candles[index]["low"] < candles[index + 1]["low"]:
            pivots.append({"index": index, "price": candles[index]["low"]})
    return pivots


def fallback_trend_from_closes(candles: list):
    closes = [candle["close"] for candle in candles[-4:]]
    if len(closes) < 4:
        return "unknown"
    if closes[-1] > closes[0] and closes[-1] > closes[-2]:
        return "bullish"
    if closes[-1] < closes[0] and closes[-1] < closes[-2]:
        return "bearish"
    return "neutral"


def analyze_timeframe_structure(candles: list):
    pivot_highs = find_pivot_highs(candles)
    pivot_lows = find_pivot_lows(candles)

    if len(pivot_highs) >= 2 and len(pivot_lows) >= 2:
        latest_high = pivot_highs[-1]["price"]
        previous_high = pivot_highs[-2]["price"]
        latest_low = pivot_lows[-1]["price"]
        previous_low = pivot_lows[-2]["price"]

        if latest_high > previous_high and latest_low > previous_low:
            return {
                "trend": "bullish",
                "structure_state": "bullish_hh_hl",
                "last_swing_high": latest_high,
                "last_swing_low": latest_low,
            }

        if latest_high < previous_high and latest_low < previous_low:
            return {
                "trend": "bearish",
                "structure_state": "bearish_ll_lh",
                "last_swing_high": latest_high,
                "last_swing_low": latest_low,
            }

        return {
            "trend": "neutral",
            "structure_state": "range",
            "last_swing_high": latest_high,
            "last_swing_low": latest_low,
        }

    fallback_trend = fallback_trend_from_closes(candles)
    if fallback_trend == "bullish":
        structure_state = "bullish_hh_hl"
    elif fallback_trend == "bearish":
        structure_state = "bearish_ll_lh"
    elif fallback_trend == "neutral":
        structure_state = "range"
    else:
        structure_state = "unclear"

    return {
        "trend": fallback_trend,
        "structure_state": structure_state,
        "last_swing_high": None,
        "last_swing_low": None,
    }


def infer_higher_trend(weekly: dict, daily: dict):
    if weekly["trend"] == daily["trend"] and weekly["trend"] in {"bullish", "bearish"}:
        return weekly["trend"]
    return "unknown"


def infer_h4_features(candles: list, higher_trend: str):
    if len(candles) < 7 or higher_trend not in {"bullish", "bearish"}:
        return {
            "pullback_direction": "unclear",
            "pullback_structure": "unclear",
            "reversal_state": "unclear",
            "break_of_structure": False,
            "first_entry_structure": "unclear",
            "last_confirmed_high": None,
            "last_confirmed_low": None,
        }

    pullback_window = candles[:-3]
    reversal_window = candles[-3:]
    pullback_state = analyze_timeframe_structure(pullback_window)

    if pullback_state["trend"] == "bullish":
        pullback_structure = "hh_hl"
    elif pullback_state["trend"] == "bearish":
        pullback_structure = "ll_lh"
    elif pullback_state["trend"] == "neutral":
        pullback_structure = "mixed"
    else:
        pullback_structure = "unclear"

    if higher_trend == "bullish":
        bos_reference = max(candle["high"] for candle in pullback_window[-3:])
        break_of_structure = reversal_window[-1]["close"] > bos_reference
        first_entry_ready = (
            break_of_structure
            and reversal_window[1]["low"] > reversal_window[0]["low"]
            and reversal_window[2]["low"] >= reversal_window[1]["low"]
        )
        return {
            "pullback_direction": pullback_state["trend"] if pullback_state["trend"] in {"bearish", "bullish", "none"} else "unclear",
            "pullback_structure": pullback_structure,
            "reversal_state": "confirmed_bullish" if break_of_structure else "not_confirmed",
            "break_of_structure": break_of_structure,
            "first_entry_structure": "first_hl" if first_entry_ready else "not_present",
            "last_confirmed_high": bos_reference if break_of_structure else None,
            "last_confirmed_low": min(candle["low"] for candle in reversal_window),
        }

    bos_reference = min(candle["low"] for candle in pullback_window[-3:])
    break_of_structure = reversal_window[-1]["close"] < bos_reference
    first_entry_ready = (
        break_of_structure
        and reversal_window[1]["high"] < reversal_window[0]["high"]
        and reversal_window[2]["high"] <= reversal_window[1]["high"]
    )
    return {
        "pullback_direction": pullback_state["trend"] if pullback_state["trend"] in {"bearish", "bullish", "none"} else "unclear",
        "pullback_structure": pullback_structure,
        "reversal_state": "confirmed_bearish" if break_of_structure else "not_confirmed",
        "break_of_structure": break_of_structure,
        "first_entry_structure": "first_lh" if first_entry_ready else "not_present",
        "last_confirmed_high": max(candle["high"] for candle in reversal_window),
        "last_confirmed_low": bos_reference if break_of_structure else None,
    }


def detect_aoi_features(
    weekly_state: dict,
    daily_state: dict,
    h4_state: dict,
    candles_root: dict,
    risk_features: dict,
    provided_aoi: dict | None,
):
    if provided_aoi:
        return normalize_aoi_features(provided_aoi)

    h4_candles = candles_root["h4"]["candles"]
    higher_trend = infer_higher_trend(weekly_state, daily_state)
    reference_price = risk_features.get("entry_price", h4_candles[-1]["close"])
    swing_high, swing_low = determine_aoi_impulse_bounds(weekly_state, daily_state, h4_state, candles_root)
    fib_zone = compute_fib_zone(higher_trend, swing_high, swing_low)
    zone_status = infer_zone_status(reference_price, fib_zone)
    has_structural_level = h4_state["first_entry_structure"] in {"first_hl", "first_lh"}
    has_sr = is_near_structural_reference(reference_price, weekly_state, daily_state, h4_state, swing_high, swing_low)
    has_order_block = h4_state["break_of_structure"] and zone_status == "inside_50_61_8"

    aoi = {
        "zone_status": zone_status,
        "has_sr": has_sr,
        "has_order_block": has_order_block,
        "has_structural_level": has_structural_level,
    }
    aoi["confluence_count"] = sum(
        1
        for key in ["has_sr", "has_order_block", "has_structural_level"]
        if aoi[key] is True
    )
    return aoi


def determine_aoi_impulse_bounds(weekly_state: dict, daily_state: dict, h4_state: dict, candles_root: dict):
    if h4_state.get("last_confirmed_high") is not None and h4_state.get("last_confirmed_low") is not None:
        return h4_state["last_confirmed_high"], h4_state["last_confirmed_low"]

    if daily_state.get("last_swing_high") is not None and daily_state.get("last_swing_low") is not None:
        return daily_state["last_swing_high"], daily_state["last_swing_low"]

    lookback = candles_root["h4"]["candles"][-7:]
    return max(candle["high"] for candle in lookback), min(candle["low"] for candle in lookback)


def is_near_structural_reference(
    price: float,
    weekly_state: dict,
    daily_state: dict,
    h4_state: dict,
    swing_high: float,
    swing_low: float,
):
    references = [
        weekly_state.get("last_swing_high"),
        weekly_state.get("last_swing_low"),
        daily_state.get("last_swing_high"),
        daily_state.get("last_swing_low"),
        h4_state.get("last_confirmed_high"),
        h4_state.get("last_confirmed_low"),
    ]
    references = [value for value in references if value is not None]
    if not references:
        return False

    tolerance = max((swing_high - swing_low) * 0.1, 0.0005)
    return any(abs(price - reference) <= tolerance for reference in references)


def normalize_aoi_features(aoi: dict):
    normalized = {
        "zone_status": aoi.get("zone_status", "unknown"),
        "has_sr": aoi.get("has_sr", False),
        "has_order_block": aoi.get("has_order_block", False),
        "has_structural_level": aoi.get("has_structural_level", False),
    }
    normalized["confluence_count"] = aoi.get(
        "confluence_count",
        sum(
            1
            for key in ["has_sr", "has_order_block", "has_structural_level"]
            if normalized[key] is True
        ),
    )
    return normalized


def compute_fib_zone(higher_trend: str, swing_high: float, swing_low: float):
    range_size = swing_high - swing_low
    if range_size <= 0:
        return None

    if higher_trend == "bullish":
        zone_high = swing_high - (range_size * 0.5)
        zone_low = swing_high - (range_size * 0.618)
        return min(zone_low, zone_high), max(zone_low, zone_high)

    if higher_trend == "bearish":
        zone_low = swing_low + (range_size * 0.5)
        zone_high = swing_low + (range_size * 0.618)
        return min(zone_low, zone_high), max(zone_low, zone_high)

    return None


def infer_zone_status(price: float, fib_zone: tuple[float, float] | None):
    if not fib_zone:
        return "unknown"
    zone_low, zone_high = fib_zone
    if zone_low <= price <= zone_high:
        return "inside_50_61_8"
    return "outside_zone"


def detect_confirmation_features(
    h4_candles: list,
    provided_confirmation: dict | None,
    h4_state: dict | None = None,
    higher_trend: str = "unknown",
):
    if provided_confirmation:
        return {
            "present": provided_confirmation.get("present", False),
            "type": provided_confirmation.get("type", "unknown"),
        }

    if len(h4_candles) < 2:
        return {"present": False, "type": "unknown"}

    previous = h4_candles[-2]
    current = h4_candles[-1]

    if is_bullish_engulfing(previous, current):
        return {"present": True, "type": "bullish_engulfing"}
    if is_bearish_engulfing(previous, current):
        return {"present": True, "type": "bearish_engulfing"}
    if is_bos_retest(h4_candles, h4_state or {}, higher_trend):
        return {"present": True, "type": "bos_retest"}
    if is_hammer(current):
        return {"present": True, "type": "hammer"}
    if is_shooting_star(current):
        return {"present": True, "type": "shooting_star"}
    return {"present": False, "type": "none"}


def is_bullish_engulfing(previous: dict, current: dict):
    return (
        previous["close"] < previous["open"]
        and current["close"] > current["open"]
        and current["open"] <= previous["close"]
        and current["close"] >= previous["open"]
    )


def is_bearish_engulfing(previous: dict, current: dict):
    return (
        previous["close"] > previous["open"]
        and current["close"] < current["open"]
        and current["open"] >= previous["close"]
        and current["close"] <= previous["open"]
    )


def is_hammer(candle: dict):
    body = abs(candle["close"] - candle["open"])
    full_range = candle["high"] - candle["low"]
    if full_range <= 0 or body == 0:
        return False
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    body_position = (max(candle["open"], candle["close"]) - candle["low"]) / full_range
    return (
        lower_wick >= body * 2
        and upper_wick <= body * 0.75
        and body <= full_range * 0.35
        and body_position >= 0.55
        and candle["close"] >= candle["open"]
    )


def is_shooting_star(candle: dict):
    body = abs(candle["close"] - candle["open"])
    full_range = candle["high"] - candle["low"]
    if full_range <= 0 or body == 0:
        return False
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]
    body_position = (candle["high"] - min(candle["open"], candle["close"])) / full_range
    return (
        upper_wick >= body * 2
        and lower_wick <= body
        and body <= full_range * 0.35
        and body_position >= 0.55
        and candle["close"] <= candle["open"]
    )


def is_bos_retest(h4_candles: list, h4_state: dict, higher_trend: str):
    if len(h4_candles) < 2:
        return False
    if not h4_state or not h4_state.get("break_of_structure"):
        return False

    previous = h4_candles[-2]
    current = h4_candles[-1]
    recent_range = max(candle["high"] for candle in h4_candles[-4:]) - min(candle["low"] for candle in h4_candles[-4:])
    tolerance = max(recent_range * 0.08, 0.0005)

    if higher_trend == "bullish" and h4_state.get("last_confirmed_high") is not None:
        level = h4_state["last_confirmed_high"]
        touched_level = current["low"] <= level + tolerance
        reclaimed_level = current["close"] >= level
        bullish_close = current["close"] > current["open"] and current["close"] >= previous["close"]
        return touched_level and reclaimed_level and bullish_close

    if higher_trend == "bearish" and h4_state.get("last_confirmed_low") is not None:
        level = h4_state["last_confirmed_low"]
        touched_level = current["high"] >= level - tolerance
        reclaimed_level = current["close"] <= level
        bearish_close = current["close"] < current["open"] and current["close"] <= previous["close"]
        return touched_level and reclaimed_level and bearish_close

    return False


def build_feature_snapshot_from_market_input(payload: dict):
    meta = payload["meta"]
    candles_root = payload["candles"]
    objective_context = payload["objective_context"]

    weekly_state = analyze_timeframe_structure(candles_root["weekly"]["candles"])
    daily_state = analyze_timeframe_structure(candles_root["daily"]["candles"])
    higher_trend = infer_higher_trend(weekly_state, daily_state)
    h4_state = infer_h4_features(candles_root["h4"]["candles"], higher_trend)
    provided_aoi = objective_context.get("aoi_features")
    provided_confirmation = objective_context.get("confirmation_features")
    risk_features = objective_context["risk_features"]
    aoi_features = detect_aoi_features(weekly_state, daily_state, h4_state, candles_root, risk_features, provided_aoi)
    confirmation_features = detect_confirmation_features(
        candles_root["h4"]["candles"],
        provided_confirmation,
        h4_state=h4_state,
        higher_trend=higher_trend,
    )

    feature_payload = {
        "meta": {
            "feature_snapshot_version": "1.0",
            "strategy_id": "set_and_forget",
            "objective_only": True,
            "pair": meta["pair"],
            "execution_timeframe": meta["execution_timeframe"],
            "execution_mode": meta["execution_mode"],
            "source_kind": meta["source_kind"],
            "generated_at": meta.get("generated_at"),
            "fxalex_confluence_enabled": meta.get("fxalex_confluence_enabled", False),
            "news_context_enabled": meta.get("news_context_enabled", False),
        },
        "timeframe_features": {
            "weekly": weekly_state,
            "daily": daily_state,
            "h4": h4_state,
        },
        "aoi_features": aoi_features,
        "confirmation_features": confirmation_features,
        "risk_features": risk_features,
        "operational_flags": objective_context["operational_flags"],
    }
    return feature_payload


def validate_built_feature_snapshot(feature_payload: dict, schema: dict | None = None):
    schema = schema or feature_snapshot.load_json(FEATURE_SNAPSHOT_SCHEMA_FILE)
    return feature_snapshot.validate_feature_snapshot(feature_payload, schema)
