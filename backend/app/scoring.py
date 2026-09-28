"""
Area Fitness Scoring Module

Deterministic scoring for grocery retail expansion site evaluation.
Uses only OSM + PostGIS data. No LLM, no fabricated data.

Dimensions and weights are product-design assumptions, not statistically
calibrated. Change the constants below to rebalance.
"""

import numpy as np
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Product-design assumption: dimension weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "market_opportunity": 0.30,
    "commercial_vitality": 0.25,
    "accessibility": 0.20,
    "residential_signal": 0.15,
    "amenity_infrastructure": 0.10,
}

# Winsorize bounds (percentile)
WINSORIZE_LOW = 5
WINSORIZE_HIGH = 95

# Grade thresholds
GRADES = [(80, "A"), (60, "B"), (40, "C"), (20, "D"), (0, "F")]

# POI subcategories considered grocery competitors
GROCERY_SUBCATEGORIES = (
    "supermarket", "convenience", "grocery", "greengrocer",
    "general", "department_store",
)

# Major road types for accessibility signal
MAJOR_ROAD_TYPES = ("primary", "secondary", "trunk", "motorway")

# Healthcare amenity subcategories
HEALTHCARE_SUBCATEGORIES = ("hospital", "clinic", "pharmacy")

# Food/commercial amenity subcategories
FOOD_SUBCATEGORIES = ("restaurant", "cafe", "fast_food")


def grade_from_score(score: int) -> str:
    for threshold, grade in GRADES:
        if score >= threshold:
            return grade
    return "F"


def winsorized_percentile(values: np.ndarray, target: float) -> float:
    """Compute percentile score (0-100) for target within winsorized distribution."""
    if len(values) == 0:
        return 50.0
    low = np.percentile(values, WINSORIZE_LOW)
    high = np.percentile(values, WINSORIZE_HIGH)
    if high <= low:
        return 50.0
    clipped = np.clip(values, low, high)
    target_clipped = np.clip(target, low, high)
    rank = np.sum(clipped < target_clipped) + 0.5 * np.sum(clipped == target_clipped)
    return float(rank / len(clipped) * 100)


def score_market_opportunity(
    grocery_density_pctl: float,
    savomart_distance_pctl: float,
    has_savomart: bool,
) -> float:
    """
    Competitive whitespace is not simply 'fewer = better'.
    - Too few competitors (< P10): area may lack demand → partial score
    - Sweet spot (P10–P60): underserved but viable → highest score
    - Saturated (> P60): diminishing returns → score declines to floor of 20
    """
    gp = grocery_density_pctl
    if gp < 10:
        whitespace = gp * 4.0
    elif gp <= 60:
        whitespace = 40.0 + (gp - 10) * 1.2
    else:
        whitespace = max(20.0, 100.0 - (gp - 60) * 2.0)

    presence_bonus = 20.0 if not has_savomart else 0.0
    raw = (whitespace + savomart_distance_pctl) / 2.0 + presence_bonus
    return min(100.0, max(0.0, raw))


def score_dimension_avg(percentiles: list[float]) -> float:
    if not percentiles:
        return 50.0
    return sum(percentiles) / len(percentiles)


@dataclass
class MetricValue:
    value: float | int
    metric_type: str  # "direct", "derived", "proxy"


def compute_fitness(
    target_pincode: str,
    all_raw: dict[str, dict[str, float]],
) -> dict:
    """
    Compute fitness score for target_pincode given raw metrics for ALL pincodes.
    all_raw: {pincode: {metric_name: value, ...}, ...}
    Returns the full report dict for the target pincode.
    """
    target = all_raw[target_pincode]
    codes = sorted(all_raw.keys())
    N = len(codes)

    def pctl(metric: str) -> float:
        vals = np.array([all_raw[c].get(metric, 0) for c in codes], dtype=float)
        return winsorized_percentile(vals, target.get(metric, 0))

    # --- Percentiles ---
    grocery_density_pctl = pctl("grocery_density_per_km2")
    savomart_dist_pctl = pctl("nearest_savomart_m")
    has_savomart = target.get("savomart_in_pincode", 0) > 0

    market_opp = score_market_opportunity(grocery_density_pctl, savomart_dist_pctl, has_savomart)

    commercial = score_dimension_avg([
        pctl("poi_density_per_km2"),
        pctl("shop_count"),
        pctl("food_count"),
        pctl("shop_diversity"),
        pctl("commercial_building_count"),
    ])

    accessibility = score_dimension_avg([
        pctl("road_network_km"),
        pctl("road_density_km_per_km2"),
        pctl("major_road_count"),
    ])

    residential = score_dimension_avg([
        pctl("residential_building_count"),
        pctl("apartment_density_per_km2"),
        pctl("school_college_count"),
    ])

    amenity = score_dimension_avg([
        pctl("bank_atm_count"),
        pctl("healthcare_count"),
        pctl("fuel_count"),
        pctl("amenity_diversity"),
    ])

    overall = round(
        market_opp * WEIGHTS["market_opportunity"]
        + commercial * WEIGHTS["commercial_vitality"]
        + accessibility * WEIGHTS["accessibility"]
        + residential * WEIGHTS["residential_signal"]
        + amenity * WEIGHTS["amenity_infrastructure"]
    )
    overall = min(100, max(0, overall))

    def m(name, mtype):
        return {"value": target.get(name, 0), "type": mtype}

    sub_scores = {
        "market_opportunity": {
            "score": round(market_opp),
            "weight": WEIGHTS["market_opportunity"],
            "metrics": {
                "grocery_competitor_count": m("grocery_competitor_count", "direct"),
                "grocery_density_per_km2": m("grocery_density_per_km2", "derived"),
                "nearest_savomart_m": m("nearest_savomart_m", "direct"),
                "savomart_in_pincode": m("savomart_in_pincode", "direct"),
            },
        },
        "commercial_vitality": {
            "score": round(commercial),
            "weight": WEIGHTS["commercial_vitality"],
            "metrics": {
                "poi_density_per_km2": m("poi_density_per_km2", "derived"),
                "shop_count": m("shop_count", "direct"),
                "food_count": m("food_count", "direct"),
                "shop_diversity": m("shop_diversity", "direct"),
                "commercial_building_count": m("commercial_building_count", "direct"),
            },
        },
        "accessibility": {
            "score": round(accessibility),
            "weight": WEIGHTS["accessibility"],
            "metrics": {
                "road_network_km": m("road_network_km", "direct"),
                "road_density_km_per_km2": m("road_density_km_per_km2", "derived"),
                "major_road_count": m("major_road_count", "direct"),
            },
        },
        "residential_signal": {
            "score": round(residential),
            "weight": WEIGHTS["residential_signal"],
            "metrics": {
                "residential_building_count": m("residential_building_count", "proxy"),
                "apartment_density_per_km2": m("apartment_density_per_km2", "proxy"),
                "school_college_count": m("school_college_count", "proxy"),
            },
        },
        "amenity_infrastructure": {
            "score": round(amenity),
            "weight": WEIGHTS["amenity_infrastructure"],
            "metrics": {
                "bank_atm_count": m("bank_atm_count", "direct"),
                "healthcare_count": m("healthcare_count", "direct"),
                "fuel_count": m("fuel_count", "direct"),
                "amenity_diversity": m("amenity_diversity", "direct"),
            },
        },
    }

    return {
        "overall_score": overall,
        "grade": grade_from_score(overall),
        "sub_scores": sub_scores,
        "raw_data": {k: v for k, v in target.items()},
        "weights": WEIGHTS,
    }
