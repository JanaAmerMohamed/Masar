import psycopg2
from psycopg2.extras import RealDictCursor, Json
from contextlib import contextmanager
import json
import sys
from pathlib import Path


def resource_path(*relative_path):

    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    return base_path.joinpath(*relative_path)


CONFIG_PATH = resource_path("db_config.json")


def load_db_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    raise FileNotFoundError(
        f"Database configuration file not found: {CONFIG_PATH}"
    )


DB_CONFIG = load_db_config()


@contextmanager
def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
# ------------------------------------------------------------------
# Buses
# ------------------------------------------------------------------

def create_bus(name, capacity, depot_lat, depot_lng, dest_lat, dest_lng,
                depot_address=None, dest_address=None, bus_type=None):
  
    sql = """
        INSERT INTO buses (name, capacity, depot_lat, depot_lng, dest_lat, dest_lng,
                            depot_address, dest_address, bus_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (name, capacity, depot_lat, depot_lng, dest_lat, dest_lng,
                               depot_address, dest_address, bus_type))
            bus_id = cur.fetchone()[0]
            return bus_id


def get_bus(bus_id):

    sql = "SELECT * FROM buses WHERE id = %s;"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (bus_id,))
            return cur.fetchone()


def list_buses():

    sql = "SELECT * FROM buses ORDER BY id;"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()


def delete_bus(bus_id):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM routes WHERE bus_id = %s;", (bus_id,))
            cur.execute("DELETE FROM passengers WHERE bus_id = %s;", (bus_id,))
            cur.execute("DELETE FROM buses WHERE id = %s RETURNING id;", (bus_id,))
            deleted = cur.fetchone()
            return deleted[0] if deleted else None


# ------------------------------------------------------------------
# Passengers
# ------------------------------------------------------------------

def add_passenger(bus_id, name, address, lat, lng, passenger_type=None):

    sql = """
        INSERT INTO passengers (bus_id, name, address, lat, lng, passenger_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (bus_id, name, address, lat, lng, passenger_type))
            return cur.fetchone()[0]


def get_passengers_for_bus(bus_id):

    sql = "SELECT * FROM passengers WHERE bus_id = %s ORDER BY id;"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (bus_id,))
            return cur.fetchall()


def delete_passenger(bus_id, passenger_id):
  
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM passengers WHERE id = %s AND bus_id = %s RETURNING id;",
                (passenger_id, bus_id),
            )
            deleted = cur.fetchone()
            if not deleted:
                return None
            cur.execute("DELETE FROM routes WHERE bus_id = %s;", (bus_id,))
            return deleted[0]


# ------------------------------------------------------------------
# Routes (save results of solver)
# ------------------------------------------------------------------

def save_route(bus_id, result):

    sql = """
        INSERT INTO routes (
            bus_id,
            ordered_stops,
            total_distance_km,
            duration_min,
            used_real_roads,
            geometry,
            legs,
            stops_detail,
            num_passengers
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                bus_id,
                Json(result.get("ordered_coordinates")),
                result.get("total_distance_km"),
                result.get("duration_min"),
                result.get("used_real_roads"),
                Json(result.get("route_geometry")),

                Json(result.get("legs")),

                Json(result.get("stops_detail")),
                result.get("num_passengers"),
            ))
            return cur.fetchone()[0]


def get_latest_route(bus_id):

    sql = """
        SELECT * FROM routes
        WHERE bus_id = %s
        ORDER BY created_at DESC
        LIMIT 1;
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (bus_id,))
            return cur.fetchone()


# ------------------------------------------------------------------
# Edit mode 
# ------------------------------------------------------------------

def save_edits(bus_id, depot=None, destination=None, passengers=None):

    with get_connection() as conn:
        with conn.cursor() as cur:
            if depot or destination:
                sets, params = [], []
                if depot:
                    sets += ["depot_lat = %s", "depot_lng = %s"]
                    params += [depot["lat"], depot["lng"]]
                    if depot.get("address"):
                        sets.append("depot_address = %s")
                        params.append(depot["address"])
                if destination:
                    sets += ["dest_lat = %s", "dest_lng = %s"]
                    params += [destination["lat"], destination["lng"]]
                    if destination.get("address"):
                        sets.append("dest_address = %s")
                        params.append(destination["address"])
                params.append(bus_id)
                cur.execute(f"UPDATE buses SET {', '.join(sets)} WHERE id = %s;", params)

            for p in (passengers or []):
                if p.get("address"):
                    cur.execute(
                        "UPDATE passengers SET lat = %s, lng = %s, address = %s "
                        "WHERE id = %s AND bus_id = %s;",
                        (p["lat"], p["lng"], p["address"], p["id"], bus_id),
                    )
                else:
                    cur.execute(
                        "UPDATE passengers SET lat = %s, lng = %s "
                        "WHERE id = %s AND bus_id = %s;",
                        (p["lat"], p["lng"], p["id"], bus_id),
                    )
    return True