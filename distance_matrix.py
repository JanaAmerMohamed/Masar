import requests

OSRM_BASE_URL = "https://router.project-osrm.org"
UNREACHABLE_PENALTY_M = 10**8  # large number so OR-Tools avoids unreachable pairs
UNREACHABLE_PENALTY_S = 10**7  # same idea, but for duration-based routing (seconds)


def get_osrm_distance_matrix(locations, profile="driving", timeout=10):

    # OSRM wants "lng,lat" order (opposite of how we store lat,lng everywhere else)
    coords = ";".join(f"{lng},{lat}" for lat, lng in locations)
    url = f"{OSRM_BASE_URL}/table/v1/{profile}/{coords}"
    params = {"annotations": "distance,duration"}

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table request failed: {data.get('code')}")

    raw_distances = data["distances"]
    raw_durations = data["durations"]
    n = len(locations)

    distance_matrix_m = [
        [int(raw_distances[i][j]) if raw_distances[i][j] is not None else UNREACHABLE_PENALTY_M for j in range(n)]
        for i in range(n)
    ]

    duration_matrix_s = [
        [int(raw_durations[i][j]) if raw_durations[i][j] is not None else UNREACHABLE_PENALTY_S for j in range(n)]
        for i in range(n)
    ]

    return distance_matrix_m, duration_matrix_s


def get_osrm_route_geometry(ordered_locations, profile="driving", timeout=10):

    coords = ";".join(f"{lng},{lat}" for lat, lng in ordered_locations)
    url = f"{OSRM_BASE_URL}/route/v1/{profile}/{coords}"
    params = {"overview": "full", "geometries": "geojson"}

    response = requests.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM route request failed: {data.get('code')}")

    route = data["routes"][0]
    geometry = [(lat, lng) for lng, lat in route["geometry"]["coordinates"]]

    legs = [
        {"distance_km": round(leg["distance"] / 1000, 2), "duration_min": round(leg["duration"] / 60, 1)}
        for leg in route["legs"]
    ]

    return {
        "geometry": geometry,
        "distance_km": round(route["distance"] / 1000, 2),
        "duration_min": round(route["duration"] / 60, 1),
        "legs": legs,
    }

