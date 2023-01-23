from dotenv import dotenv_values
import requests
import webbrowser
import websocket
import json
from lib.math import normalize_heading
import time
import random
import math

FRONTEND_BASE = "noflight.monad.fi"
BACKEND_BASE = "noflight.monad.fi/backend"

game_id = None

route = []

def on_message(ws: websocket.WebSocketApp, message):
    [action, payload] = json.loads(message)

    if action != "game-instance":
        print([action, payload])
        return

     # New game tick arrived!
    game_state = json.loads(payload["gameState"])
    commands = generate_commands(game_state)
    time.sleep(0.1)
    ws.send(json.dumps(["run-command", {"gameId": game_id, "payload": commands}]))


def on_error(ws: websocket.WebSocketApp, error):
    print(error)


def on_open(ws: websocket.WebSocketApp):
    print("OPENED")
    ws.send(json.dumps(["sub-game", {"id": game_id}]))


def on_close(ws, close_status_code, close_msg):
    print("CLOSED")

# Change this to your own implementation
def generate_commands(game_state):
    global route
    
    if(len(route) == 0):
        print(game_state)
        generate_route(game_state)
    
    if(len(route) == 0):
        return []
    commands = []
    for aircraft in game_state["aircrafts"]:
        # Go loopy loop
        index = 0
        for i in range(0, len(route)):
            if(route[i][-1] == aircraft['id']):
                index = i
        if(len(route[index]) <= 1):
            continue
        if(route[index][0] == 0):
            route[index].pop(0)
            continue
        new_dir = normalize_heading(aircraft['direction'] + route[index][0])
        commands.append(f"HEAD {aircraft['id']} {new_dir}")
        route[index].pop(0)

    return commands

def generate_route(game_state):
    global route

    total_limit = 100000
    route_steps_limit = 60
    direction_change_limit = 20
    found_routes_limit = 1000
    best_routes_min = 20
    best_routes_max_direction_difference = 20

    # [x_min, y_min, x_max, y_max]
    boundaries = get_boundaries(game_state["bbox"])

    # [x, y, direction, speed, collision_radius, id, target_x, target_y, target_direction, landing_radius]
    aircrafts = get_aircrafts_data(game_state)

    # [[score, [airplane1 directions], [airplane2 directions], ...], ...]
    found_routes = []
    
    most_steps = 0

    c1 = 1
    c2 = 1
    while c1 < total_limit and len(found_routes) <= found_routes_limit:
        if c2 >= 10000:
            print('Random routes: ' + str(c1) + ', Routes count: ' + str(len(found_routes)) + 
                ', Most steps: ' + str(most_steps))
            c2 = 1
        else:
            c2 += 1

        # [score, [airplane1 directions], [airplane2 directions], ...]
        current_routes = []
        for i in range(0, len(aircrafts)):
            current_routes.append([])
        
        blacklist = []
        success = False

        stop = False
        i = 0
        while i < route_steps_limit and not stop:
            for j in range(0, len(aircrafts)):
                if j in blacklist:
                    continue
                aircraft = aircrafts[j]
                if(len(current_routes[j]) > 0 and calculate_distance(current_routes[j][-1][0], current_routes[j][-1][1], aircraft[6], aircraft[7]) <= aircraft[9] and
                    compare_directions(current_routes[j][-1][2], aircraft[8], best_routes_max_direction_difference)):
                    blacklist.append(j)
                    continue
                start_x = 0
                start_y = 0
                start_direction = 0
                if(i == 0):
                    start_x = aircraft[0]
                    start_y = aircraft[1]
                    start_direction = aircraft[2]
                else:
                    start_x = current_routes[j][-1][0]
                    start_y = current_routes[j][-1][1]
                    start_direction = current_routes[j][-1][2]
                new_direction = get_rand_direction(start_direction - direction_change_limit, start_direction + direction_change_limit)
                new_x = calculate_x(start_x, new_direction, aircraft[3])
                new_y = calculate_y(start_y, new_direction, aircraft[3])
                if new_x < boundaries[0] or new_x > boundaries[2] or new_y < boundaries[1] or new_y > boundaries[3]:
                    stop = True
                    break
                if(j > 0 and check_collision(new_x, new_y, current_routes, aircrafts, j, blacklist)):
                    stop = True
                    break
                current_routes[j].append([new_x, new_y, new_direction])
            i += 1
            if(len(blacklist) == len(aircrafts)):
                success = True
                break
        c1 += 1
        if success:
            score = i + 1
            routes = [0]
            for i in range(0, len(aircrafts)):
                routes.append([])
                x = aircrafts[i][0]
                y = aircrafts[i][1]
                direction = aircrafts[i][2]
                for j in range(0, len(current_routes[i])):
                    actual_direction = calculate_direction(x, y, current_routes[i][j][0], current_routes[i][j][1])
                    direction_change = get_direction_change(direction, actual_direction)
                    routes[i + 1].append(direction_change)
                    if(direction_change != 0):
                        score += 1
                    x = current_routes[i][j][0]
                    y = current_routes[i][j][1]
                    direction = current_routes[i][j][2]
                    if(j == len(current_routes[i]) - 1):
                        direction_change = get_direction_change(direction, aircrafts[i][8])
                        if(direction_change != 0):
                            score += 1
                        routes[i + 1].append(direction_change)
                        routes[i + 1].append(aircrafts[i][5])
            routes[0] = score
            found_routes.append(routes)
            continue
        if(most_steps < i):
            most_steps = i
    
    if(len(found_routes) == 0):
        print("Most steps: " + str(most_steps))
        return []
    found_routes.sort(key=lambda x: x[0])

    route = found_routes[0][1:]
    print(route)


def get_aircrafts_data(game_state):
    aircrafts = []
    for aircraft in game_state["aircrafts"]:
        temp = [
            aircraft["position"]["x"],
            aircraft["position"]["y"],
            aircraft["direction"],
            aircraft["speed"],
            aircraft["collisionRadius"],
            aircraft["id"]]
        info = get_target_info(aircraft["destination"], aircraft["speed"], game_state["airports"])
        for i in range(0, len(info)):
            temp.append(info[i])
        aircrafts.append(temp)
    return aircrafts

def get_target_info(destination, speed, airports):
    target_info = []
    for airport in airports:
        if(airport["name"] == destination):
            target_x = airport["position"]["x"] + -math.cos(airport["direction"]) * speed
            target_y = airport["position"]["y"] + -math.sin(airport["direction"]) * speed
            target_info = [
                target_x,
                target_y,
                airport["direction"],
                airport["landingRadius"]
            ]
    return target_info

def get_boundaries(bbox):
    boundaries = []
    for i in range(0, len(bbox)):
        boundaries.append(bbox[i]["x"])
        boundaries.append(bbox[i]["y"])
    return boundaries

def get_rand_direction(min, max):
    direction = random.randint(min, max)
    if(direction < 0):
        direction += 360
    if(direction > 359):
        direction -= 360
    return direction

def check_collision(x, y, current_routes, aircrafts, aircraft_index, blacklist):
    for i in range(0, aircraft_index):
        if(i in blacklist):
            continue
        if(calculate_distance(x, y, current_routes[i][-1][0], current_routes[i][-1][1]) <= max(aircrafts[aircraft_index][4], aircrafts[i][4])):
                return True
    return False

def calculate_distance(x1, y1, x2, y2):
    return ((x1 - x2)**2 + (y1 - y2)**2)**0.5

def calculate_direction(x1, y1, x2, y2):
    return normalize_heading(math.degrees(math.atan2(y2 - y1, x2 - x1)))

def calculate_x(x, direction, distance):
    return x + math.cos(math.radians(direction)) * distance

def calculate_y(y, direction, distance):
    return y + math.sin(math.radians(direction)) * distance

def compare_directions(direction1, direction2, max_difference):
    difference = abs(direction1 - direction2)
    if difference > 180:
        difference = 359 - difference
    return difference <= max_difference

def get_direction_change(current_direction, target_direction):
    direction_change = target_direction - current_direction
    if(direction_change > 180):
        direction_change -= 360
    if(direction_change < -180):
        direction_change += 360
    return direction_change

def main():
    config = dotenv_values()
    res = requests.post(
        f"https://{BACKEND_BASE}/api/levels/{config['LEVEL_ID']}",
        headers={
            "Authorization": config["TOKEN"]
        })

    if not res.ok:
        print(f"Couldn't create game: {res.status_code} - {res.text}")
        return

    game_instance = res.json()

    global game_id
    game_id = game_instance["entityId"]

    url = f"https://{FRONTEND_BASE}/?id={game_id}"
    print(f"Game at {url}")
    webbrowser.open(url, new=2)
    time.sleep(2)

    ws = websocket.WebSocketApp(
        f"wss://{BACKEND_BASE}/{config['TOKEN']}/", on_message=on_message, on_open=on_open, on_close=on_close, on_error=on_error)
    ws.run_forever()


if __name__ == "__main__":
    main()