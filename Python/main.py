from dotenv import dotenv_values
import requests
import webbrowser
import websocket
import json
from lib.math import normalize_heading
import time
import random
import math
import threading as th

FRONTEND_BASE = "noflight.monad.fi"
BACKEND_BASE = "noflight.monad.fi/backend"

game_id = None

route = [-1]

still_time = True

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
    
    if(route[0] == -1):
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
    global still_time

    s = th.Timer(25.0, no_time_left)  
    s.start()

    total_limit = 1000000
    route_steps_limit = 100
    direction_change_limit = 20
    found_routes_limit = 10000
    best_routes_max_direction_difference = 20

    # [x_min, y_min, x_max, y_max]
    boundaries = get_boundaries(game_state["bbox"])

    # [x, y, direction, speed, collision_radius, id, target_x, target_y, target_direction, landing_radius]
    aircrafts_all = get_aircrafts_data(game_state)
    aircrafts = []
    more_aircrafts = True

    # [[score, [airplane1 directions], [airplane2 directions], ...], ...]
    found_routes = []

    saved_routes = []
    saved_blacklist = []
    last_resort_success = False
    counter = 0

    last_resort = True

    c1 = 1
    c2 = 1
    while c1 < total_limit and len(found_routes) <= found_routes_limit and still_time:
        if c2 >= 10000:
            print('Random routes: ' + str(c1) + ', Routes count: ' + str(len(found_routes)))
            if len(found_routes) > 0:
                found_routes.sort(key=lambda x: x[0])
                print("best score: " + str(found_routes[0][0]))
            c2 = 1
        else:
            c2 += 1

        # [score, [airplane1 directions], [airplane2 directions], ...]
        current_routes = saved_routes.copy()
        
        blacklist = saved_blacklist.copy()
        success = False

        if last_resort:
            if(len(aircrafts) < len(aircrafts_all) and more_aircrafts):
                aircrafts = aircrafts_all[:(len(blacklist) + 1)].copy()
                current_routes.append([])
                more_aircrafts = False
            else:
                for i in range(len(blacklist), len(aircrafts)):
                    current_routes.append([])        
        else:
            for i in range(0, len(aircrafts)):
                current_routes.append([])

        stop = False
        i = 0
        while i < route_steps_limit and not stop:
            for j in range(0, len(aircrafts)):
                if j in blacklist:
                    continue
                aircraft = aircrafts[j]
                if(len(current_routes[j]) > 0 and calculate_distance(current_routes[j][-1][0], current_routes[j][-1][1], aircraft[6], aircraft[7]) < aircraft[9] and 
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
                if new_x <= boundaries[0] or new_x >= boundaries[2] or new_y <= boundaries[1] or new_y >= boundaries[3]:
                    stop = True
                    break
                if(j > 0 and check_collision(new_x, new_y, current_routes, aircrafts, j, i)):
                    stop = True
                    break
                current_routes[j].append([new_x, new_y, new_direction])
            i += 1
            if(len(blacklist) == len(aircrafts)):
                if(len(blacklist) == len(aircrafts_all)):
                    last_resort_success = True
                success = True
                break
        c1 += 1
        if last_resort:
            counter += 1
            if counter >= 10000 and not last_resort_success:
                counter = 0
                aircrafts = []
                saved_routes = []
                saved_blacklist = []
                more_aircrafts = True
        
        if last_resort and success:
            direction = aircrafts[-1][8]
            x = current_routes[-1][-1][0]
            y = current_routes[-1][-1][1]
            new_x = calculate_x(x, direction, aircrafts[-1][3])
            new_y = calculate_y(y, direction, aircrafts[-1][3])
            current_routes[-1].append([new_x, new_y, direction])            
            if not last_resort_success:
                saved_routes = current_routes.copy()
                saved_blacklist = blacklist.copy()
                more_aircrafts = True
                continue
        if success:
            sizes = []
            for i in range(0, len(aircrafts)):
                sizes.append(len(current_routes[i]))
            score = max(sizes)
            routes = [0]
            for i in range(0, len(aircrafts)):
                temp_route = []
                direction = aircrafts[i][2]
                for j in range(0, len(current_routes[i])):
                    direction_change = get_direction_change(direction, current_routes[i][j][2])
                    temp_route.append(direction_change)
                    if(direction_change != 0):
                        score += 1
                    direction = current_routes[i][j][2]
                    if(j == len(current_routes[i]) - 1):
                        temp_route.append(aircrafts[i][5])
                routes.append(temp_route)
            routes[0] = score
            found_routes.append(routes)
            found_routes.sort(key=lambda x: x[0])
            saved_blacklist = []
            saved_routes = []
            aircrafts = []
            more_aircrafts = True
            last_resort_success = False
            counter = 0
            continue
        if(not last_resort and c1 > 20000 and len(found_routes) == 0):
            last_resort = True
            aircrafts = []
    s.cancel()

    if(len(found_routes) == 0):
        route = []
        return
    found_routes.sort(key=lambda x: x[0])
    scores = []
    for i in range(0, len(found_routes)):
        scores.append(found_routes[i][0])
    print(scores)

    route = found_routes[0][1:]


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
            target_x = airport["position"]["x"] + -math.cos(math.radians(airport["direction"])) * speed
            target_y = airport["position"]["y"] + -math.sin(math.radians(airport["direction"])) * speed
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

def check_collision(x, y, current_routes, aircrafts, aircraft_index, step):
    for i in range(0, aircraft_index):
        if(len(current_routes[i]) - 1 < step):
            continue
        if(calculate_distance(x, y, current_routes[i][step][0], current_routes[i][step][1]) <= max(aircrafts[aircraft_index][4], aircrafts[i][4])):
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

def no_time_left():
    global still_time
    still_time = False

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