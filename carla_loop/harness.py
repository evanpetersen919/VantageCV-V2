"""Drive one episode in CARLA with a standard agent and report how it went.

The agent is CARLA's ``BasicAgent`` (route following, traffic lights, obstacle braking). What it
*sees* of other vehicles goes through one function, ``vision``: by default it returns the true
vehicles of the simulator (a ceiling: perfect perception). A detector in the loop replaces that
function and nothing else, so two runs differ only in what the agent believes is in front of it.

Needs a running CARLA 0.9.16 server and the ``carla`` and ``shapely`` Python packages. The
``agents`` package ships inside the CARLA download (``PythonAPI/carla``), not in the pip wheel.
"""

import math
import os
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, Tuple

CARLA_ROOT = Path(os.environ.get("CARLA_ROOT", r"F:\CARLA_0.9.16"))
sys.path.insert(0, str(CARLA_ROOT / "PythonAPI" / "carla"))

# pylint: disable=wrong-import-position,import-error
import carla  # noqa: E402
from agents.navigation.basic_agent import BasicAgent  # noqa: E402

Vision = Callable[[Any, Any], Sequence[Any]]  # (world, ego) -> vehicles the agent will consider

STEP_SECONDS = 0.05
COLLISION_DEBOUNCE_S = 1.0
STUCK_SECONDS = 40.0
HARD_BRAKE = 0.5  # BasicAgent's emergency stop brakes at its max_brake (0.5)


@dataclass(frozen=True)
class Episode:
    """One scripted episode: where the ego starts and goes, and how busy the road is."""

    seed: int
    town: str = "Town10HD_Opt"
    traffic: int = 40
    target_kmh: float = 30.0
    max_seconds: float = 180.0
    min_route_m: float = 150.0
    max_route_m: float = 450.0


def pick_route(
    spawn_points: Sequence[Any], seed: int, min_m: float, max_m: float
) -> Tuple[int, int]:
    """(start index, goal index) of two spawn points a straight-line ``min_m``-``max_m`` apart."""
    rng = random.Random(seed)
    for _ in range(1000):
        start, goal = rng.sample(range(len(spawn_points)), 2)
        distance = spawn_points[start].location.distance(spawn_points[goal].location)
        if min_m <= distance <= max_m:
            return start, goal
    raise RuntimeError("no spawn pair within the requested distance")


def true_vehicles(world: Any, ego: Any) -> List[Any]:
    """Perfect perception: every other vehicle in the world."""
    return [v for v in world.get_actors().filter("*vehicle*") if v.id != ego.id]


class VisionAgent(BasicAgent):  # type: ignore[misc]
    """``BasicAgent`` whose view of other vehicles comes from ``vision`` (ground truth by default)."""

    def __init__(self, vehicle: Any, vision: Vision = true_vehicles, **kwargs: Any) -> None:
        super().__init__(vehicle, **kwargs)
        self._vision = vision

    def run_step(self) -> Any:  # pylint: disable=arguments-differ
        """One control: the planner's, braked if a seen vehicle or a red light is ahead."""
        velocity = self._vehicle.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        vehicles = list(self._vision(self._world, self._vehicle))
        vehicle_reach = self._base_vehicle_threshold + self._speed_ratio * speed
        light_reach = self._base_tlight_threshold + self._speed_ratio * speed
        hazard = self._vehicle_obstacle_detected(vehicles, vehicle_reach)[0]
        hazard = self._affected_by_traffic_light(self._lights_list, light_reach)[0] or hazard
        control = self._local_planner.run_step()
        return self.add_emergency_stop(control) if hazard else control


def debounce(events: Sequence[Tuple[float, str]]) -> List[Dict[str, Any]]:
    """Collapse contact events of one crash (a collision fires every tick it lasts)."""
    kept: List[Dict[str, Any]] = []
    last: Dict[str, float] = {}
    for time, other in events:
        if other not in last or time - last[other] > COLLISION_DEBOUNCE_S:
            kept.append({"t": round(time, 1), "with": other})
        last[other] = time
    return kept


def summarise(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate episode rows: how many reached the goal, and collisions per kilometre."""
    km = sum(r["distance_m"] for r in rows) / 1000.0
    crashes = sum(len(r["collisions"]) for r in rows)
    return {
        "episodes": len(rows),
        "reached": sum(r["outcome"] == "reached" for r in rows),
        "stuck": sum(r["outcome"] == "stuck" for r in rows),
        "mean_completion": round(sum(r["route_completion"] for r in rows) / max(len(rows), 1), 3),
        "collisions": crashes,
        "collisions_per_km": round(crashes / km, 2) if km else None,
        "lane_invasions": sum(r["lane_invasions"] for r in rows),
        "hard_brake_events": sum(r.get("hard_brake_events", 0) for r in rows),
        "hard_brake_events_per_km": round(sum(r.get("hard_brake_events", 0) for r in rows) / km, 1) if km else None,
        "km": round(km, 2),
    }


def restart_server(wait_s: float = 240.0) -> None:
    """Kill CARLA and start it again, then wait until its port answers (a hung server cannot be reset)."""
    import socket  # pylint: disable=import-outside-toplevel
    import subprocess  # pylint: disable=import-outside-toplevel
    import time  # pylint: disable=import-outside-toplevel

    subprocess.run(["taskkill", "/F", "/IM", "CarlaUE4-Win64-Shipping.exe"], check=False, capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "CarlaUE4.exe"], check=False, capture_output=True)
    time.sleep(5.0)
    subprocess.Popen(  # pylint: disable=consider-using-with
        [str(CARLA_ROOT / "CarlaUE4.exe"), "-quality-level=Low"], cwd=str(CARLA_ROOT)
    )
    deadline = time.time() + wait_s
    while time.time() < deadline:
        with socket.socket() as probe:
            probe.settimeout(3.0)
            if probe.connect_ex(("localhost", 2000)) == 0:
                time.sleep(25.0)  # the port opens before the world is ready
                return
        time.sleep(5.0)
    raise RuntimeError("CARLA did not come back")


def connect(host: str = "localhost", port: int = 2000) -> Any:
    """A client for the running server, checked against this package's version."""
    client = carla.Client(host, port)
    client.set_timeout(60.0)
    if client.get_server_version() != client.get_client_version():
        raise RuntimeError("CARLA server and client versions differ")
    return client


def _spawn_traffic(world: Any, manager: Any, episode: Episode, skip: Sequence[int]) -> List[Any]:
    """Up to ``episode.traffic`` autopilot cars at seeded spawn points other than ``skip``."""
    rng = random.Random(episode.seed + 1)
    spawn_points = world.get_map().get_spawn_points()
    free = [i for i in range(len(spawn_points)) if i not in skip]
    rng.shuffle(free)
    cars = [
        b
        for b in world.get_blueprint_library().filter("vehicle.*")
        if int(b.get_attribute("number_of_wheels")) == 4
    ]
    spawned: List[Any] = []
    for index in free:
        if len(spawned) >= episode.traffic:
            break
        npc = world.try_spawn_actor(rng.choice(cars), spawn_points[index])
        if npc is not None:
            npc.set_autopilot(True, manager.get_port())
            spawned.append(npc)
    return spawned


def _follow(world: Any, ego: Any) -> None:
    """Put the spectator camera behind the ego so the server window shows the drive."""
    transform = ego.get_transform()
    behind = transform.get_forward_vector() * -8.0
    world.get_spectator().set_transform(
        carla.Transform(
            transform.location + behind + carla.Location(z=4.0),
            carla.Rotation(pitch=-15.0, yaw=transform.rotation.yaw),
        )
    )


def run_episode(  # pylint: disable=too-many-locals
    client: Any, episode: Episode, vision: Vision = true_vehicles, rig: Any = None
) -> Dict[str, Any]:
    """Run ``episode`` and return its metrics. Restores the server's settings afterwards."""
    world = client.get_world()
    if not world.get_map().name.endswith(episode.town):  # reloading a loaded map can hang the server
        world = client.load_world(episode.town)
    original = world.get_settings()
    manager = client.get_trafficmanager()
    actors: List[Any] = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = STEP_SECONDS
        world.apply_settings(settings)
        manager.set_synchronous_mode(True)
        manager.set_random_device_seed(episode.seed)

        spawn_points = world.get_map().get_spawn_points()
        start, goal = pick_route(spawn_points, episode.seed, episode.min_route_m, episode.max_route_m)
        blueprints = world.get_blueprint_library()
        ego = world.spawn_actor(blueprints.find("vehicle.tesla.model3"), spawn_points[start])
        actors.append(ego)
        traffic = _spawn_traffic(world, manager, episode, (start, goal))
        actors += traffic

        collisions: List[Tuple[float, str]] = []
        lane_invasions: List[float] = []
        clock = {"t": 0.0}
        sensor_collision = world.spawn_actor(
            blueprints.find("sensor.other.collision"), carla.Transform(), attach_to=ego
        )
        sensor_lane = world.spawn_actor(
            blueprints.find("sensor.other.lane_invasion"), carla.Transform(), attach_to=ego
        )
        sensor_collision.listen(lambda e: collisions.append((clock["t"], e.other_actor.type_id)))
        sensor_lane.listen(lambda e: lane_invasions.append(clock["t"]))
        actors += [sensor_collision, sensor_lane]
        if rig is not None:
            actors += rig.attach(world, ego)

        world.tick()  # in synchronous mode a spawned actor's transform is only valid after a tick
        agent = VisionAgent(ego, vision, target_speed=episode.target_kmh)
        agent.set_destination(spawn_points[goal].location)
        total = max(len(agent.get_local_planner().get_plan()), 1)

        outcome, stopped_for, distance_m, ticks = "timeout", 0.0, 0.0, 0
        braking, brake_events, brake_ticks = False, 0, 0
        last = ego.get_location()
        while clock["t"] < episode.max_seconds:
            frame = world.tick()
            clock["t"] += STEP_SECONDS
            ticks += 1
            if rig is not None:
                rig.step(world, ego, frame)
            control = agent.run_step()
            ego.apply_control(control)
            hard = control.brake >= HARD_BRAKE  # the agent's emergency stop applies its max_brake
            brake_events += int(hard and not braking)
            brake_ticks += int(hard)
            braking = hard
            here = ego.get_location()
            distance_m += here.distance(last)
            last = here
            v = ego.get_velocity()
            moving = math.sqrt(v.x**2 + v.y**2 + v.z**2) > 0.1
            stopped_for = 0.0 if moving else stopped_for + STEP_SECONDS
            _follow(world, ego)
            if agent.done():
                outcome = "reached"
                break
            if stopped_for > STUCK_SECONDS:
                outcome = "stuck"
                break

        remaining = len(agent.get_local_planner().get_plan())
        return {
            **asdict(episode),
            "outcome": outcome,
            "route_completion": 1.0 if outcome == "reached" else round(1.0 - remaining / total, 3),
            "seconds": round(clock["t"], 1),
            "distance_m": round(distance_m, 1),
            "mean_speed_kmh": round(3.6 * distance_m / max(clock["t"], 1e-6), 1),
            "collisions": debounce(collisions),
            "lane_invasions": len(lane_invasions),
            "hard_brake_events": brake_events,
            "hard_brake_seconds": round(brake_ticks * STEP_SECONDS, 1),
            "npcs": len(traffic),
            **({"rig": rig.report()} if rig is not None else {}),
        }
    finally:
        sensors = [a for a in actors if hasattr(a, "stop")]
        for sensor in sensors:  # sensors go first, one by one (a batch with a tick hung the server)
            sensor.stop()
            sensor.destroy()
        manager.set_synchronous_mode(False)
        world.apply_settings(original)
        client.apply_batch([carla.command.DestroyActor(a) for a in reversed(actors) if a not in sensors])
