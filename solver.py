import math
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from distance_matrix import get_osrm_distance_matrix, get_osrm_route_geometry
from traffic_matrix import (
    get_tomtom_duration_matrix,
    get_tomtom_route_geometry,
    is_configured as tomtom_is_configured,
)

def haversine_km(a, b):
    """Straight-line distance in km between two (lat, lng) points."""
    R = 6371.0
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def build_haversine_matrix(locations):
    """locations: list of (lat, lng) tuples. Returns an NxN matrix in meters (OR-Tools wants integers)."""
    n = len(locations)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = int(haversine_km(locations[i], locations[j]) * 1000)
    return matrix


AVG_CITY_SPEED_KMH = 35  # used only for the haversine fallback duration estimate


def build_matrices(locations, use_tomtom=True):
    
    try:
        distance_matrix_m, osrm_duration_matrix_s = get_osrm_distance_matrix(locations)
        used_real_roads = True
        duration_matrix_s = osrm_duration_matrix_s
        duration_source = "osrm"
    except Exception as e:
        print(f"[warning] OSRM unavailable ({e}) - falling back to straight-line distances")
        distance_matrix_m = build_haversine_matrix(locations)
        speed_m_per_s = AVG_CITY_SPEED_KMH * 1000 / 3600
        duration_matrix_s = [
            [int(d / speed_m_per_s) if d else 0 for d in row]
            for row in distance_matrix_m
        ]
        used_real_roads = False
        duration_source = "haversine_estimate"

    if use_tomtom and tomtom_is_configured():
        try:
            duration_matrix_s = get_tomtom_duration_matrix(locations)
            duration_source = "tomtom_live_traffic"
        except Exception as e:
            print(f"[warning] TomTom unavailable ({e}) - using {duration_source} duration instead")

    return distance_matrix_m, duration_matrix_s, used_real_roads, duration_source


def solve_single_bus_route(depot, destination, passengers, bus_capacity, use_tomtom=True):

    if len(passengers) > bus_capacity:
        raise ValueError(
            f"{len(passengers)} passengers exceed bus capacity of {bus_capacity}. "
            "Split across multiple buses (handled in the multi-vehicle stage)."
        )

    # Node 0 = depot (start), last node = destination (end), middle nodes = passengers
    locations = [depot] + passengers + [destination]
    num_locations = len(locations)
    depot_index = 0
    destination_index = num_locations - 1

    distance_matrix, duration_matrix, used_real_roads, duration_source = build_matrices(locations, use_tomtom=use_tomtom)


    naive_distance_m = sum(distance_matrix[i][i + 1] for i in range(num_locations - 1))
    naive_duration_s = sum(duration_matrix[i][i + 1] for i in range(num_locations - 1))

    # OR-Tools setup: 1 vehicle, explicit start and end nodes (not a round trip)
    manager = pywrapcp.RoutingIndexManager(num_locations, 1, [depot_index], [destination_index])
    routing = pywrapcp.RoutingModel(manager)

    def duration_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return duration_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(duration_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(5)

    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        raise RuntimeError("No solution found - check that all points are reachable.")


    index = routing.Start(0)
    ordered_node_indices = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        ordered_node_indices.append(node)
        index = solution.Value(routing.NextVar(index))
    ordered_node_indices.append(manager.IndexToNode(index))  # destination

    total_distance_m = sum(
        distance_matrix[ordered_node_indices[i]][ordered_node_indices[i + 1]]
        for i in range(len(ordered_node_indices) - 1)
    )
    total_duration_s = sum(
        duration_matrix[ordered_node_indices[i]][ordered_node_indices[i + 1]]
        for i in range(len(ordered_node_indices) - 1)
    )

    ordered_coords = [locations[i] for i in ordered_node_indices]

    result = {
        "stop_order": ordered_node_indices,
        "ordered_coordinates": ordered_coords,
        "total_distance_km": round(total_distance_m / 1000, 2),
        "naive_distance_km": round(naive_distance_m / 1000, 2),
        "naive_duration_min": round(naive_duration_s / 60, 1),
        "num_passengers": len(passengers),
        "used_real_roads": used_real_roads,
        "duration_source": duration_source,  # "tomtom_live_traffic" | "osrm" | "haversine_estimate"
        "route_geometry": None,   # filled in below if OSRM route call succeeds
        "duration_min": round(total_duration_s / 60, 1),
    }


    try:
        if duration_source == "tomtom_live_traffic":
        # TomTom was used to optimize the route under live traffic,
        # so use TomTom itself to obtain the actual road geometry.
            route = get_tomtom_route_geometry(ordered_coords)

            result["route_geometry"] = route["geometry"]
            result["legs"] = route["legs"]
            result["total_distance_km"] = route["distance_km"]
            result["duration_min"] = route["duration_min"]

        else:
        # No TomTom: keep the existing OSRM geometry pipeline.
            route = get_osrm_route_geometry(ordered_coords)

            result["route_geometry"] = route["geometry"]
            result["legs"] = route["legs"]
            result["total_distance_km"] = route["distance_km"]
            result["duration_min"] = route["duration_min"]

    except Exception as e:
        print(
            f"[warning] Could not fetch street-level route geometry "
            f"({e}) - returning stop order only, no turn-by-turn path"
    )

    return result

