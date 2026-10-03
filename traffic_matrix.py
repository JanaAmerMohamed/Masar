import os
import requests
import truststore
from dotenv import load_dotenv
truststore.inject_into_ssl()
load_dotenv()
# ============================================================
# TomTom API configuration
# ============================================================

TOMTOM_MATRIX_URL = "https://api.tomtom.com/routing/matrix/2"

TOMTOM_ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute"

TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY")

UNREACHABLE_PENALTY_S = 10**7

MAX_MATRIX_ITEMS = 2500


# ============================================================
# Configuration
# ============================================================

def is_configured():
    """Return True when a TomTom API key is available."""
    return bool(TOMTOM_API_KEY)


# ============================================================
# 1. TomTom LIVE TRAFFIC DURATION MATRIX
# ============================================================

def get_tomtom_duration_matrix(locations, profile="car", timeout=15):
    """
    Get a live-traffic travel-time matrix from TomTom.

    locations:
        [(lat, lng), (lat, lng), ...]

    Returns:
        NxN matrix containing travel time in seconds.

    This matrix is used by OR-Tools to optimize the passenger order.
    """

    if not TOMTOM_API_KEY:
        raise RuntimeError(
            "TOMTOM_API_KEY is not set - skipping TomTom"
        )

    n = len(locations)

    if n * n > MAX_MATRIX_ITEMS:
        raise RuntimeError(
            f"{n}x{n} matrix ({n * n} items) exceeds TomTom's "
            f"{MAX_MATRIX_ITEMS}-item limit."
        )

    points = [
        {
            "point": {
                "latitude": lat,
                "longitude": lng
            }
        }
        for lat, lng in locations
    ]

    body = {
        "origins": points,
        "destinations": points,
        "options": {
            "traffic": "live",
            "departAt": "now",
            "routeType": "fastest",
            "travelMode": profile,
        },
    }

    response = requests.post(
        TOMTOM_MATRIX_URL,
        params={"key": TOMTOM_API_KEY},
        json=body,
        timeout=timeout,

    )

    response.raise_for_status()

    data = response.json()

    duration_matrix_s = [
        [UNREACHABLE_PENALTY_S] * n
        for _ in range(n)
    ]

    for cell in data.get("data", []):

        i = cell.get("originIndex")
        j = cell.get("destinationIndex")

        summary = cell.get("routeSummary")

        if (
            summary
            and "travelTimeInSeconds" in summary
            and i is not None
            and j is not None
        ):
            duration_matrix_s[i][j] = int(
                summary["travelTimeInSeconds"]
            )

    return duration_matrix_s


# ============================================================
# 2. TomTom ACTUAL ROAD GEOMETRY
# ============================================================

def get_tomtom_route_geometry(
    locations,
    profile="car",
    timeout=20,
):
    """
    Get the actual TomTom road geometry for an already ordered route.

    IMPORTANT:
    locations must already be in the final visiting order:

        depot
        -> passenger 1
        -> passenger 2
        -> ...
        -> destination

    Returns:

        {
            "geometry": [[lat, lng], ...],
            "distance_km": float,
            "duration_min": float,
            "legs": [...]
        }

    This geometry is the route that TomTom itself calculated,
    including its traffic-aware routing.
    """

    if not TOMTOM_API_KEY:
        raise RuntimeError(
            "TOMTOM_API_KEY is not set"
        )

    if len(locations) < 2:
        raise ValueError(
            "At least two locations are required"
        )


    locations_string = ":".join(
        f"{lat},{lng}"
        for lat, lng in locations
    )

    url = (
        f"{TOMTOM_ROUTE_URL}/"
        f"{locations_string}/json"
    )

    params = {
        "key": TOMTOM_API_KEY,

        # Use current traffic conditions
        "traffic": "true",

        # Start calculation now
        "departAt": "now",

        # Fastest route
        "routeType": "fastest",

        # Vehicle type
        "travelMode": profile,

        # We already have the stop order from OR-Tools
        "computeBestOrder": "false",

        # Ask TomTom to return detailed route points
        "routeRepresentation": "polyline",
    }

    response = requests.get(
        url,
        params=params,
        timeout=timeout,
    )

    response.raise_for_status()

    data = response.json()

    routes = data.get("routes", [])

    if not routes:
        raise RuntimeError(
            "TomTom returned no routes"
        )

    route = routes[0]

    # ========================================================
    # Geometry
    # ========================================================

    geometry = []

    for leg in route.get("legs", []):

        for point in leg.get("points", []):

            lat = point.get("latitude")
            lng = point.get("longitude")

            if lat is not None and lng is not None:
                geometry.append([
                    lat,
                    lng
                ])

    if not geometry:
        raise RuntimeError(
            "TomTom returned a route but no geometry points"
        )

    # ========================================================
    # Overall route summary
    # ========================================================

    summary = route.get("summary", {})

    total_distance_m = summary.get(
        "lengthInMeters",
        0
    )

    total_duration_s = summary.get(
        "travelTimeInSeconds",
        0
    )

    # ========================================================
    # Leg information
    # ========================================================

    legs = []

    for leg in route.get("legs", []):

        leg_summary = leg.get(
            "summary",
            {}
        )

        leg_distance_m = leg_summary.get(
            "lengthInMeters",
            0
        )

        leg_duration_s = leg_summary.get(
            "travelTimeInSeconds",
            0
        )

        legs.append({
            "distance_km": round(
                leg_distance_m / 1000,
                2
            ),
            "duration_min": round(
                leg_duration_s / 60,
                1
            ),
        })

    return {
        "geometry": geometry,

        "distance_km": round(
            total_distance_m / 1000,
            2
        ),

        "duration_min": round(
            total_duration_s / 60,
            1
        ),

        "legs": legs,
    }