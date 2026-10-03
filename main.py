# standard library
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import List, Optional

# third-party
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# local
import db
from solver import solve_single_bus_route

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

app = FastAPI(
    title="Masar API",
    description="Bus route optimization API - Masar (مسار)",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class BusCreate(BaseModel):
    name: str
    capacity: int
    depot_lat: float
    depot_lng: float

    dest_lat: float
    dest_lng: float
    depot_address: Optional[str] = None
    dest_address: Optional[str] = None
    bus_type: Optional[str] = None   # "hiace" or "coaster"


class BusOut(BusCreate):
    id: int



class PassengerCreate(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
    passenger_type: Optional[str] = None   # "employee" / "student" / "faculty"


class PassengerOut(PassengerCreate):
    id: int
    bus_id: int


class RouteOut(BaseModel):
    id: int
    bus_id: int
    ordered_stops: Optional[list] = None
    total_distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    used_real_roads: Optional[bool] = None
    geometry: Optional[list] = None  # list of [lat, lng] points tracing the streets (not GeoJSON)
    legs: Optional[list] = None  # [{"distance_km": .., "duration_min": ..}, ...] per stop-to-stop segment
    stops_detail: Optional[list] = None  # ordered [{name, address, type, leg_from_previous_min, ...}, ...]
    num_passengers: Optional[int] = None


class EndpointEdit(BaseModel):
    lat: float
    lng: float
    address: Optional[str] = None


class PassengerEdit(BaseModel):
    id: int
    lat: float
    lng: float
    address: Optional[str] = None


class SaveEditsPayload(BaseModel):
    depot: Optional[EndpointEdit] = None
    destination: Optional[EndpointEdit] = None
    passengers: List[PassengerEdit] = []


# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


def resource_path(*relative_path):
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    return base_path.joinpath(*relative_path)

@app.get("/")
def dashboard():
    return FileResponse(resource_path("masar-app.html"))



@app.get("/resolve-maps-link")
def resolve_maps_link(url: str):
    if "google.com" not in url and "goo.gl" not in url:
        raise HTTPException(status_code=400, detail="الرابط ده مش رابط Google Maps")
    headers = {

        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    try:
        resp = requests.head(url, allow_redirects=True, timeout=6, headers=headers)
        final_url = resp.url

        if final_url == url:
            resp = requests.get(url, allow_redirects=True, timeout=6, headers=headers)
            final_url = resp.url
        return {"resolved_url": final_url}
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"تعذر فك الرابط: {e}")


# ------------------------------------------------------------------
# Buses
# ------------------------------------------------------------------

@app.post("/buses", response_model=BusOut)
def create_bus(bus: BusCreate):
    bus_id = db.create_bus(
        bus.name, bus.capacity,
        bus.depot_lat, bus.depot_lng,
        bus.dest_lat, bus.dest_lng,
        bus.depot_address, bus.dest_address,
        bus.bus_type,
    )
    return {**bus.dict(), "id": bus_id}


@app.get("/buses", response_model=List[BusOut])
def list_buses():
    return db.list_buses()


@app.get("/buses/{bus_id}", response_model=BusOut)
def get_bus(bus_id: int):
    bus = db.get_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return bus


@app.delete("/buses/{bus_id}")
def delete_bus(bus_id: int):
    deleted_id = db.delete_bus(bus_id)
    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Bus not found")
    return {"message": "Bus deleted successfully", "id": deleted_id}


# ------------------------------------------------------------------
# Passengers
# ------------------------------------------------------------------


@app.post("/buses/{bus_id}/passengers", response_model=PassengerOut)
def add_passenger(bus_id: int, passenger: PassengerCreate):
    bus = db.get_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    pid = db.add_passenger(
        bus_id, passenger.name, passenger.address,
        passenger.lat, passenger.lng, passenger.passenger_type,
    )
    return {**passenger.dict(), "id": pid, "bus_id": bus_id}


@app.get("/buses/{bus_id}/passengers", response_model=List[PassengerOut])
def list_passengers(bus_id: int):
    bus = db.get_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return db.get_passengers_for_bus(bus_id)


@app.delete("/buses/{bus_id}/passengers/{passenger_id}")
def delete_passenger(bus_id: int, passenger_id: int):
    bus = db.get_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    deleted_id = db.delete_passenger(bus_id, passenger_id)
    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Passenger not found for this bus")
    return {"message": "Passenger deleted successfully", "id": deleted_id}


# ------------------------------------------------------------------
# Route computation
# ------------------------------------------------------------------

def _build_stops_detail(bus, passengers_rows, result):

    stop_order = result["stop_order"]
    legs = result.get("legs") or []
    destination_index = len(stop_order) - 1  # last position in the ORDER, not a node id

    stops_detail = []
    for position, node in enumerate(stop_order):
        if node == 0:
            stop_type, name, address = "depot", "نقطة الانطلاق", bus.get("name")
        elif position == destination_index:
            stop_type, name, address = "destination", "الوجهة النهائية", None
        else:
            passenger = passengers_rows[node - 1]
            stop_type, name, address = "passenger", passenger["name"], passenger["address"]

        leg = legs[position - 1] if position > 0 and position - 1 < len(legs) else None

        stops_detail.append({
            "order": position,
            "type": stop_type,
            "name": name,
            "address": address,
            "passenger_id": passengers_rows[node - 1]["id"] if stop_type == "passenger" else None,
            "lat": result["ordered_coordinates"][position][0],
            "lng": result["ordered_coordinates"][position][1],
            "leg_from_previous_km": leg["distance_km"] if leg else None,
            "leg_from_previous_min": leg["duration_min"] if leg else None,
        })

    return stops_detail


@app.post("/buses/{bus_id}/compute-route")
def compute_route(bus_id: int):
    bus = db.get_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    passengers_rows = db.get_passengers_for_bus(bus_id)
    if not passengers_rows:
        raise HTTPException(status_code=400, detail="No passengers for this bus")

    depot = (bus["depot_lat"], bus["depot_lng"])
    destination = (bus["dest_lat"], bus["dest_lng"])
    passengers = [(p["lat"], p["lng"]) for p in passengers_rows]

    result = solve_single_bus_route(
        depot=depot,
        destination=destination,
        passengers=passengers,
        bus_capacity=bus["capacity"],
    )

    result["stops_detail"] = _build_stops_detail(bus, passengers_rows, result)

    route_id = db.save_route(bus_id, result)
    result["route_id"] = route_id
    return result


@app.get("/buses/{bus_id}/route", response_model=RouteOut)
def get_route(bus_id: int):
    route = db.get_latest_route(bus_id)
    if not route:
        raise HTTPException(status_code=404, detail="No route computed yet for this bus")
    return route




@app.post("/buses/{bus_id}/save-edits")
def save_edits(bus_id: int, payload: SaveEditsPayload):
    bus = db.get_bus(bus_id)
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    db.save_edits(
        bus_id,
        depot=payload.depot.dict() if payload.depot else None,
        destination=payload.destination.dict() if payload.destination else None,
        passengers=[p.dict() for p in payload.passengers],
    )
    return {"message": "تم حفظ التعديلات"}



def open_browser():
    time.sleep(1.5)  
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)