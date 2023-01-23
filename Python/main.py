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

coordinates = []
directions = []

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

route = []

# Change this to your own implementation
def generate_commands(game_state):
    global route
    global coordinates
    global directions

    if(len(coordinates) != 0):
        real = [game_state["aircrafts"][0]["position"]["x"], game_state["aircrafts"][0]["position"]["y"]]
        calculated = [coordinates[0][0], coordinates[0][1]]
        coordinates = coordinates[1:]
        directions = directions[1:]

    if(len(route) == 0):
        generate_route(game_state)
    direction = 0
    if(len(route) > 0):
        direction = route[0]
        route = route[1:]
    commands = []
    for aircraft in game_state["aircrafts"]:
        # Go loopy loop
        if(len(route) == 0 and direction == 0 or direction == 0):
            break
        new_dir = normalize_heading(aircraft['direction'] + direction)
        commands.append(f"HEAD {aircraft['id']} {new_dir}")

    return commands

# best_routes [[distance, steps, x1, y1, ...], [], []]

def generate_route(game_state):
    global route
    global coordinates
    global directions

    box_x_min = -180
    box_x_max = 180
    box_y_min = -180
    box_y_max = 180


    best_routes = []
    destination_x = game_state["airports"][0]["position"]["x"]
    destination_y = game_state["airports"][0]["position"]["y"]
    destination_direction = game_state["airports"][0]["direction"]
    landing_radius = game_state["airports"][0]["landingRadius"]
    #collision_radius = game_state["aircrafts"][0]["collisionRadius"]
    speed = game_state["aircrafts"][0]["speed"]
    start_x = game_state["aircrafts"][0]["position"]["x"]
    start_y = game_state["aircrafts"][0]["position"]["y"]
    start_direction = game_state["aircrafts"][0]["direction"]
    target_x = destination_x + -math.cos(destination_direction) * speed
    target_y = destination_y + -math.sin(destination_direction) * speed

    total_limit = 450000
    route_steps_limit = 40
    direction_change_limit = 20
    best_routes_limit = 20000
    best_routes_min = 20
    best_routes_max_distance = landing_radius
    best_routes_max_direction_difference = 20    

    c2 = 1
    found = False
    c1 = 1
    while c1 < total_limit and len(best_routes) <= best_routes_limit:
        if c2 >= 10000:
            print('Outer: ' + str(c1) + ', Routes ' + str(len(best_routes)))
            c2 = 1
        else:
            c2 += 1
        current_route = [0, 0]    
        x = start_x
        y = start_y
        direction = start_direction
        finish = False
        
        while len(current_route) < route_steps_limit and not finish:
            new_direction = get_rand_direction(direction - direction_change_limit, direction + direction_change_limit)
            new_x = calculate_x(x, new_direction, speed)
            new_y = calculate_y(y, new_direction, speed)
            if new_x < box_x_min or new_x > box_x_max or new_y < box_y_min or new_y > box_y_max:
                break
            current_route.append([new_x, new_y])
            if(calculate_distance(new_x, new_y, target_x, target_y) <= best_routes_max_distance and compare_directions(new_direction, destination_direction, best_routes_max_direction_difference)):
                current_route[0] = calculate_total_distance(current_route)
                current_route[1] = len(current_route) - 2
                best_routes.append(current_route)
                #if(calculate_distance(new_x, new_y, target_x, target_y) <= landing_radius):
                    #found = True
                finish = True
                break
            x = new_x
            y = new_y
            direction = new_direction
        if(found):
            break
        c1 += 1
    
    if(not found):
        best_routes.sort(key=lambda x: x[0], reverse=True)
        if(len(best_routes) == 0):
            return

    x = start_x
    y = start_y
    best_route = best_routes[-1]

    coordinates = best_route[2:]
    current_direction = start_direction
    for i in range(2, len(best_route)):
        new_direction = calculate_direction(x, y, best_route[i][0], best_route[i][1])
        directions.append(new_direction)
        route_direction = new_direction - current_direction
        if(route_direction > 180):
            route_direction -= 360
        if(route_direction < -180):
            route_direction += 360
        route.append(route_direction)
        x = best_route[i][0]
        y = best_route[i][1]
        current_direction = new_direction

    route_direction = destination_direction - current_direction
    if(route_direction > 180):
        route_direction -= 360
    if(route_direction < -180):
        route_direction += 360

    route.append(route_direction)
    directions.append(destination_direction)


def get_rand_direction(min, max):
    direction = random.randint(min, max)
    if(direction < 0):
        direction += 360
    if(direction > 359):
        direction -= 360
    return direction

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

def calculate_total_distance(route):
    total_distance = 0
    for i in range(3, len(route)):
        total_distance += calculate_distance(route[i][0], route[i][1], route[i - 1][0], route[i - 1][1])
    return total_distance

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