from db import get_bus, get_passengers_for_bus, save_route
from solver import solve_single_bus_route


def compute_and_save_route(bus_id: int):

    bus = get_bus(bus_id)
    if not bus:
        raise ValueError(f"Bus id={bus_id} not found")

    passengers_rows = get_passengers_for_bus(bus_id)
    if not passengers_rows:
        raise ValueError(f"No passengers found for bus id={bus_id}")

    depot = (bus["depot_lat"], bus["depot_lng"])
    destination = (bus["dest_lat"], bus["dest_lng"])
    passengers = [(p["lat"], p["lng"]) for p in passengers_rows]
    capacity = bus["capacity"]

    print(f"Bus: {bus['name']} (capacity={capacity})")
    print(f"Passengers: {len(passengers)}")
    print("Solving route...")

    result = solve_single_bus_route(
        depot=depot,
        destination=destination,
        passengers=passengers,
        bus_capacity=capacity,
    )

    route_id = save_route(bus_id, result)

    print("\n=== Route computed & saved ===")
    print(f"Route id          : {route_id}")
    print(f"Total distance    : {result['total_distance_km']} km")
    if result.get("duration_min") is not None:
        print(f"Estimated time    : {result['duration_min']} min")
    print(f"Used real roads   : {result['used_real_roads']}")
    print(f"Naive distance    : {result['naive_distance_km']} km")

    saving = (result["naive_distance_km"] - result["total_distance_km"]) / result["naive_distance_km"] * 100
    print(f"Savings           : {round(saving, 1)}%")

    return result

