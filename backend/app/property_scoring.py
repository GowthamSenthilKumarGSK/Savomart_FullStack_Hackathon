"""
Property Evaluation Scoring Module

Deterministic scoring for individual property evaluation.
Uses point-radius spatial queries against OSM/PostGIS data.
All thresholds are product heuristics, not market benchmarks.
"""

DIMENSION_WEIGHTS = {
    "residential_catchment_proxies": 0.25,
    "commercial_context": 0.25,
    "accessibility": 0.20,
    "savomart_fit": 0.15,
    "property_attributes": 0.15,
}

GRADE_THRESHOLDS = [(80, "A"), (60, "B"), (40, "C"), (20, "D"), (0, "F")]

GROCERY_SUBCATEGORIES = (
    "supermarket", "convenience", "grocery", "greengrocer", "general",
)

FOOD_SUBCATEGORIES = (
    "restaurant", "cafe", "fast_food", "bakery", "confectionery",
    "deli", "ice_cream", "food_court",
)

MAJOR_ROAD_TYPES = ("primary", "secondary", "trunk", "motorway")


def grade_from_score(score):
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def _step_normalize(value, steps):
    """Normalize using step thresholds: [(upper_bound, score), ...] sorted ascending."""
    for bound, score in steps:
        if value <= bound:
            return score
    return steps[-1][1]


def normalize_residential_buildings_500m(count):
    if count == 0: return 10
    if count <= 5: return 30
    if count <= 15: return 55
    if count <= 30: return 75
    return 90


def normalize_apartments_500m(count):
    if count == 0: return 10
    if count <= 3: return 40
    if count <= 10: return 70
    return 90


def normalize_schools_colleges_500m(count):
    if count == 0: return 20
    if count == 1: return 50
    if count <= 3: return 75
    return 90


def normalize_shops_300m(count):
    if count == 0: return 15
    if count <= 5: return 50
    if count <= 15: return 75
    return 85


def normalize_grocery_competition_500m(count):
    """Product heuristic: 0=limited, 1-3=established retail presence, 4+=higher density."""
    if count == 0: return 40
    if count <= 3: return 80
    return 50


def normalize_food_outlets_300m(count):
    if count == 0: return 20
    if count <= 5: return 55
    if count <= 15: return 75
    return 85


def normalize_shop_diversity_300m(count):
    if count == 0: return 10
    if count <= 3: return 40
    if count <= 7: return 65
    return 85


def normalize_nearest_major_road_m(dist):
    if dist is None: return 15
    if dist <= 50: return 90
    if dist <= 150: return 75
    if dist <= 300: return 55
    if dist <= 500: return 35
    return 15


def normalize_road_length_300m(length_m):
    if length_m <= 0: return 10
    if length_m <= 500: return 35
    if length_m <= 1500: return 60
    if length_m <= 3000: return 80
    return 90


def normalize_major_roads_500m(count):
    if count == 0: return 15
    if count == 1: return 50
    if count <= 3: return 75
    return 90


def normalize_nearest_savomart_m(dist):
    if dist is None: return 70
    if dist < 500: return 20
    if dist <= 1000: return 50
    if dist <= 2000: return 80
    return 90


def normalize_savomart_count_2km(count):
    if count == 0: return 85
    if count == 1: return 60
    if count == 2: return 40
    return 20


def normalize_floor(floor):
    """Product heuristic: ground floor optimal for grocery retail."""
    if floor is None: return 50
    if floor == 0: return 100
    if floor == 1: return 60
    if floor == 2: return 35
    return 15


def normalize_carpet_area(sqft):
    """Product heuristic: 300-1500 sqft optimal for grocery retail format."""
    if sqft is None: return 50
    if sqft < 300: return 20
    if sqft <= 600: return 55
    if sqft <= 1500: return 90
    if sqft <= 3000: return 70
    return 50


def normalize_frontage(ft):
    """Product heuristic: 10-40 ft optimal for grocery retail visibility."""
    if ft is None: return 50
    if ft < 10: return 20
    if ft <= 20: return 55
    if ft <= 40: return 90
    if ft <= 60: return 75
    return 60


NEUTRAL_SCORE = 50

RECOMMENDATIONS = {
    "A": "Strong candidate — recommend scheduling a site visit to validate foot traffic and access.",
    "B": "Moderate-to-good potential — recommend site visit with attention to flagged risks.",
    "C": "Mixed signals — review flagged risks before proceeding. Site visit advisable if risks can be mitigated.",
    "D": "Below-average indicators — significant concerns noted. Review risks carefully before investing further effort.",
    "F": "Weak indicators across most dimensions. Consider alternative locations.",
}

SIGNAL_TEMPLATES = {
    "residential_buildings_500m": ("Strong residential proxy within 500m", "Low residential density within 500m"),
    "apartments_500m": ("Apartment buildings nearby suggest household density", "Few apartment buildings within 500m"),
    "schools_colleges_500m": ("Schools/colleges nearby — household catchment proxy", None),
    "shops_300m": ("Active commercial area within 300m", "Limited commercial activity within 300m"),
    "grocery_competition_500m": ("Established retail presence nearby", None),
    "food_outlets_300m": ("Food outlets nearby indicate foot traffic", "Few food outlets within 300m"),
    "shop_diversity_300m": ("Diverse retail mix within 300m", "Limited retail diversity within 300m"),
    "nearest_major_road_m": ("Close to a major road", "No major road within 500m"),
    "road_length_300m": ("Good road network density within 300m", "Limited road network within 300m"),
    "major_roads_500m": ("Multiple major roads within 500m", None),
    "nearest_savomart_m": ("No Savomart within 2km — expansion opportunity", "Existing Savomart within 500m — cannibalization risk"),
    "savomart_count_2km": ("No Savomart saturation within 2km", "Multiple Savomart stores within 2km"),
    "floor_score": ("Ground floor location", "Upper floor location"),
    "carpet_area_score": ("Carpet area suitable for grocery format", "Carpet area outside optimal range for grocery format"),
    "frontage_score": ("Good frontage for retail visibility", "Limited frontage"),
}


def compute_property_evaluation(raw_metrics, property_data):
    """
    Compute property evaluation from raw spatial metrics and property attributes.
    raw_metrics: dict from spatial queries
    property_data: dict with floor, carpet_area_sqft, frontage_ft, rent_monthly
    Returns full evaluation dict.
    """
    missing_data = []

    res_buildings = raw_metrics.get("residential_buildings_500m", 0)
    apartments = raw_metrics.get("apartments_500m", 0)
    schools = raw_metrics.get("schools_colleges_500m", 0)

    res_buildings_norm = normalize_residential_buildings_500m(res_buildings)
    apartments_norm = normalize_apartments_500m(apartments)
    schools_norm = normalize_schools_colleges_500m(schools)

    residential_score = round((res_buildings_norm + apartments_norm + schools_norm) / 3)

    shops = raw_metrics.get("shops_300m", 0)
    grocery_comp = raw_metrics.get("grocery_competition_500m", 0)
    food = raw_metrics.get("food_outlets_300m", 0)
    diversity = raw_metrics.get("shop_diversity_300m", 0)

    shops_norm = normalize_shops_300m(shops)
    grocery_norm = normalize_grocery_competition_500m(grocery_comp)
    food_norm = normalize_food_outlets_300m(food)
    diversity_norm = normalize_shop_diversity_300m(diversity)

    commercial_score = round((shops_norm + grocery_norm + food_norm + diversity_norm) / 4)

    nearest_road = raw_metrics.get("nearest_major_road_m")
    road_len = raw_metrics.get("road_length_300m", 0)
    major_roads = raw_metrics.get("major_roads_500m", 0)

    nearest_road_norm = normalize_nearest_major_road_m(nearest_road)
    road_len_norm = normalize_road_length_300m(road_len)
    major_roads_norm = normalize_major_roads_500m(major_roads)

    accessibility_score = round((nearest_road_norm + road_len_norm + major_roads_norm) / 3)

    nearest_savo = raw_metrics.get("nearest_savomart_m")
    savo_count = raw_metrics.get("savomart_count_2km", 0)

    nearest_savo_norm = normalize_nearest_savomart_m(nearest_savo)
    savo_count_norm = normalize_savomart_count_2km(savo_count)

    savomart_score = round((nearest_savo_norm + savo_count_norm) / 2)

    floor_val = property_data.get("floor")
    carpet_val = property_data.get("carpet_area_sqft")
    frontage_val = property_data.get("frontage_ft")
    rent_val = property_data.get("rent_monthly")

    if floor_val is None:
        missing_data.append("floor")
    if carpet_val is None:
        missing_data.append("carpet_area_sqft")
    if frontage_val is None:
        missing_data.append("frontage_ft")
    if rent_val is None:
        missing_data.append("rent_monthly")

    floor_norm = normalize_floor(floor_val)
    carpet_norm = normalize_carpet_area(carpet_val)
    frontage_norm = normalize_frontage(frontage_val)

    property_attr_score = round((floor_norm + carpet_norm + frontage_norm) / 3)

    rent_per_sqft = None
    if rent_val is not None and carpet_val is not None and carpet_val > 0:
        rent_per_sqft = round(rent_val / carpet_val, 2)

    overall = round(
        residential_score * DIMENSION_WEIGHTS["residential_catchment_proxies"]
        + commercial_score * DIMENSION_WEIGHTS["commercial_context"]
        + accessibility_score * DIMENSION_WEIGHTS["accessibility"]
        + savomart_score * DIMENSION_WEIGHTS["savomart_fit"]
        + property_attr_score * DIMENSION_WEIGHTS["property_attributes"]
    )
    overall = min(100, max(0, overall))
    grade = grade_from_score(overall)

    sub_scores = {
        "residential_catchment_proxies": {
            "score": residential_score,
            "grade": grade_from_score(residential_score),
            "weight": DIMENSION_WEIGHTS["residential_catchment_proxies"],
            "metrics": {
                "residential_buildings_500m": {"value": res_buildings, "normalized": res_buildings_norm, "type": "proxy"},
                "apartments_500m": {"value": apartments, "normalized": apartments_norm, "type": "proxy"},
                "schools_colleges_500m": {"value": schools, "normalized": schools_norm, "type": "proxy"},
            },
        },
        "commercial_context": {
            "score": commercial_score,
            "grade": grade_from_score(commercial_score),
            "weight": DIMENSION_WEIGHTS["commercial_context"],
            "metrics": {
                "shops_300m": {"value": shops, "normalized": shops_norm, "type": "direct"},
                "grocery_competition_500m": {"value": grocery_comp, "normalized": grocery_norm, "type": "direct"},
                "food_outlets_300m": {"value": food, "normalized": food_norm, "type": "direct"},
                "shop_diversity_300m": {"value": diversity, "normalized": diversity_norm, "type": "derived"},
            },
        },
        "accessibility": {
            "score": accessibility_score,
            "grade": grade_from_score(accessibility_score),
            "weight": DIMENSION_WEIGHTS["accessibility"],
            "metrics": {
                "nearest_major_road_m": {"value": round(nearest_road, 1) if nearest_road is not None else None, "normalized": nearest_road_norm, "type": "derived"},
                "road_length_300m": {"value": round(road_len, 1), "normalized": road_len_norm, "type": "derived"},
                "major_roads_500m": {"value": major_roads, "normalized": major_roads_norm, "type": "derived"},
            },
        },
        "savomart_fit": {
            "score": savomart_score,
            "grade": grade_from_score(savomart_score),
            "weight": DIMENSION_WEIGHTS["savomart_fit"],
            "metrics": {
                "nearest_savomart_m": {"value": round(nearest_savo, 1) if nearest_savo is not None else None, "normalized": nearest_savo_norm, "type": "direct"},
                "savomart_count_2km": {"value": savo_count, "normalized": savo_count_norm, "type": "direct"},
            },
        },
        "property_attributes": {
            "score": property_attr_score,
            "grade": grade_from_score(property_attr_score),
            "weight": DIMENSION_WEIGHTS["property_attributes"],
            "metrics": {
                "floor_score": {"value": floor_val, "normalized": floor_norm, "type": "direct", "missing": floor_val is None},
                "carpet_area_score": {"value": carpet_val, "normalized": carpet_norm, "type": "direct", "missing": carpet_val is None},
                "frontage_score": {"value": frontage_val, "normalized": frontage_norm, "type": "direct", "missing": frontage_val is None},
            },
        },
    }

    positive_signals = []
    risks = []

    all_metrics = {
        "residential_buildings_500m": res_buildings_norm,
        "apartments_500m": apartments_norm,
        "schools_colleges_500m": schools_norm,
        "shops_300m": shops_norm,
        "grocery_competition_500m": grocery_norm,
        "food_outlets_300m": food_norm,
        "shop_diversity_300m": diversity_norm,
        "nearest_major_road_m": nearest_road_norm,
        "road_length_300m": road_len_norm,
        "major_roads_500m": major_roads_norm,
        "nearest_savomart_m": nearest_savo_norm,
        "savomart_count_2km": savo_count_norm,
        "floor_score": floor_norm,
        "carpet_area_score": carpet_norm,
        "frontage_score": frontage_norm,
    }

    for metric_key, norm_val in all_metrics.items():
        templates = SIGNAL_TEMPLATES.get(metric_key)
        if not templates:
            continue
        pos_text, neg_text = templates
        if norm_val >= 70 and pos_text:
            positive_signals.append(pos_text)
        elif norm_val <= 30 and neg_text:
            risks.append(neg_text)

    if grocery_comp >= 4:
        risks.append("Higher competitive density within 500m (product heuristic: 4+ grocery competitors)")

    for field in missing_data:
        label = field.replace("_", " ").replace("sqft", "(sq ft)").replace("ft", "(ft)")
        risks.append(f"{label.title()} not provided — neutral default used")

    recommendation = RECOMMENDATIONS.get(grade, RECOMMENDATIONS["C"])
    if risks and grade in ("B", "C"):
        recommendation = recommendation.replace("flagged risks", risks[0].split(" — ")[0].lower() if risks else "flagged risks")

    raw_data = {
        "radii_m": {"small": 300, "medium": 500, "large": 2000},
        "positive_signals": positive_signals,
        "risks": risks,
        "missing_data": missing_data,
        "field_derived": {"rent_per_sqft": rent_per_sqft},
        "recommendation": recommendation,
        "grade": grade,
        "scoring_notes": {
            "carpet_area_range": "Product heuristic: 300-1500 sqft optimal for grocery retail format",
            "frontage_range": "Product heuristic: 10-40 ft optimal for grocery retail visibility",
            "floor_preference": "Product heuristic: ground floor optimal for grocery retail",
            "competition_thresholds": "Product heuristic: 0=limited nearby competition, 1-3=established retail presence, 4+=higher competitive density",
        },
    }

    return {
        "overall_score": overall,
        "grade": grade,
        "sub_scores": sub_scores,
        "raw_data": raw_data,
    }
