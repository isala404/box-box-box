#!/usr/bin/env python3
"""F1 Race Simulator - Box Box Box Challenge"""
import json
import sys

# Parameters (84/100 on local test set)
OFF = {'SOFT': -1.0, 'MEDIUM': 0.0, 'HARD': 0.8}
RATE = {'SOFT': 1.2406729384227766, 'MEDIUM': 0.6290198039097495, 'HARD': 0.32170928712764346}
GRACE = {'SOFT': 10, 'MEDIUM': 20, 'HARD': 30}
TEMP_POWER = 0.825
TEMP_FACTOR = {
    18: 0.932373217526,
    19: 1.005464726294,
    20: 1.079951690342,
    22: 1.040826607336,
    23: 1.173566075483,
    26: 1.308552561689,
    27: 1.331121185847,
    28: 1.3114899386681973,
    29: 1.31701868377,
    30: 1.377388168288,
    31: 1.452050999821,
    32: 1.444220894213,
    33: 1.4971691685449697,
    34: 1.504979252794,
    36: 1.6059232078752694,
    37: 1.782270872844,
    38: 3.205179469746,
    39: 1.7129301197683011,
    40: 1.7482392028429241,
    41: 1.853832649017,
    42: 1.818349518218618,
}

def simulate_race(race_input):
    rc = race_input['race_config']
    base = rc['base_lap_time']
    total_laps = rc['total_laps']
    pit_time = rc['pit_lane_time']
    temp = rc['track_temp']
    temp_factor = TEMP_FACTOR.get(temp, (temp / 20.0) ** TEMP_POWER)

    results = []
    for _, strategy in race_input['strategies'].items():
        driver_id = strategy['driver_id']
        total_time = 0.0
        tire_age = 0
        compound = strategy['starting_tire']
        pit_laps = {ps['lap']: ps['to_tire'] for ps in strategy['pit_stops']}

        for lap in range(1, total_laps + 1):
            tire_age += 1
            deg = RATE[compound] * max(0, tire_age - GRACE[compound]) * temp_factor
            total_time += base + OFF[compound] + deg

            if lap in pit_laps:
                total_time += pit_time
                compound = pit_laps[lap]
                tire_age = 0

        results.append((total_time, driver_id))

    results.sort()
    return [driver_id for _, driver_id in results]

def main():
    race_input = json.load(sys.stdin)
    finishing = simulate_race(race_input)
    output = {
        'race_id': race_input['race_id'],
        'finishing_positions': finishing
    }
    json.dump(output, sys.stdout)

if __name__ == '__main__':
    main()
