#!/usr/bin/env python3
"""F1 Race Simulator - Box Box Box Challenge"""
import json
import sys

# Parameters (67/100 - best so far)
OFF = {'SOFT': -1.0, 'MEDIUM': 0.0, 'HARD': 0.8}
RATE = {'SOFT': 1.2406729384227766, 'MEDIUM': 0.6290198039097495, 'HARD': 0.32170928712764346}
GRACE = {'SOFT': 10, 'MEDIUM': 20, 'HARD': 30}
TEMP_POWER = 0.8059025951046688

def simulate_race(race_input):
    rc = race_input['race_config']
    base = rc['base_lap_time']
    total_laps = rc['total_laps']
    pit_time = rc['pit_lane_time']
    temp = rc['track_temp']
    temp_factor = (temp / 20.0) ** TEMP_POWER

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
