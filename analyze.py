import json
import pandas
import folium
import argparse
from datetime import datetime, timedelta
from folium import plugins
from math import radians, cos, sin, asin, sqrt, isnan

MAP_CENTER_LAT = 52.239772
MAP_CENTER_LON = 21.017347
MAP_ZOOM = 11
SPEED_ERROR_MARGIN = 1.1
pandas.set_option('future.no_silent_downcasting', True)


def haversine(lon1, lon2, lat1, lat2):
    lon1 = radians(lon1)
    lon2 = radians(lon2)
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    # Radius of earth in kilometers.
    r = 6371
    return c * r


def distance(row):
    return haversine(row['Lon_x'], row['Lon_y'], row['Lat_x'], row['Lat_y'])


def hour_diff(row):
    return (row['Time_y'] - row['Time_x']).total_seconds() / 3600


def read_file(filename):
    new_data = pandas.read_json(filename)
    new_data.index = new_data['VehicleNumber']
    new_data = new_data[['Lon', 'Lat', 'Time', 'Lines', 'Brigade']]
    new_data['Lines'] = new_data['Lines'].astype(str)
    new_data['Brigade'] = new_data['Brigade'].astype(str)
    new_data['Time'] = pandas.to_datetime(new_data['Time'])
    return new_data


def argsparser():
    parser = argparse.ArgumentParser()
    parser.add_argument('posfiles', type=str)
    parser.add_argument('amount', type=int)
    parser.add_argument('timetable', type=str)
    parser.add_argument('speedmap', type=str)
    parser.add_argument('alllate', type=str)
    args = parser.parse_args()
    return args.posfiles, args.amount, args.timetable, args.speedmap, args.alllate


def check_late_bus(row, timetable, timetable_timeind, all_arrival, bus_lates):
    this_bus = str(row['Lines_y']) + '-' + str(row['Brigade_y'])
    if this_bus in timetable and not isnan(row['speed']):
        timeformat = '%H:%M:%S'
        this_time = datetime.strptime(row['Time_x'].strftime(timeformat), timeformat)
        next_time = datetime.strptime(row['Time_y'].strftime(timeformat), timeformat)

        # Find the actual time
        timeind = timetable_timeind[this_bus]
        while timeind < len(timetable[this_bus]):
            time_in_timetable = timetable[this_bus][timeind][0]
            # Ignore all invalid timeformat like 24:mm:ss
            if int(time_in_timetable[0:2]) < 24:
                if this_time > datetime.strptime(time_in_timetable, timeformat):
                    timetable_timeind[this_bus] += 1
                    timeind += 1
                else:
                    break
            else:
                timeind += 1

        if (timeind < len(timetable[this_bus]) and
                next_time > datetime.strptime(timetable[this_bus][timeind][0], timeformat)):
            paststop = timetable[this_bus][timeind]
            stoplon = float(paststop[1])
            stoplat = float(paststop[2])

            # It's unlikely for buses to arrive on time with 00 second, so we give an extra minute.
            stoptime = datetime.strptime(paststop[0], timeformat) + timedelta(minutes=1)
            hrdiff = (stoptime - this_time).total_seconds() / 3600
            dist = haversine(stoplon, row['Lon_x'], stoplat, row['Lat_x'])

            stopname = paststop[3] + '-' + paststop[4]
            if stopname not in all_arrival:
                all_arrival[stopname] = [0, 1]
            else:
                all_arrival[stopname][1] += 1

            if hrdiff == 0:
                # 50m as margin of error
                if dist > 0.05:
                    all_arrival[stopname][0] += 1
                    if row['Lines_y'] not in bus_lates:
                        bus_lates[row['Lines_y']] = 0
                    bus_lates[row['Lines_y']] += 1

            else:
                needed_speed = dist / hrdiff
                # print(needed_speed, row['speed'])
                if needed_speed > row['speed'] * SPEED_ERROR_MARGIN:
                    all_arrival[stopname][0] += 1
                    if row['Lines_y'] not in bus_lates:
                        bus_lates[row['Lines_y']] = 0
                    bus_lates[row['Lines_y']] += 1
            # Not to check the same time twice.
            timetable_timeind[this_bus] += 1


# Add new points to map of buses exceeding limits.
def add_point(row, exceeded_points, speed):
    folium.Marker(location=[row['Lat_y'], row['Lon_y']],
                  popup=folium.Popup(
                      folium.IFrame('nr pojazdu: '
                        + str(row.name)
                        + ' nr linii: '
                        + str(row['Lines_y']
                        + ' czas: '
                        + str(row['Time_y']))
                        + ' szybkosc: '
                        + str(round(speed[row.name], 2))
                      ), min_width=150, max_width=500)
                  ).add_to(exceeded_points)


def update_new_pos(curr_pos, speed):
    for i in curr_pos.index:
        if isnan(curr_pos['Lon_y'].loc[i]):
            curr_pos.loc[i, 'Lon_y'] = curr_pos.loc[i, 'Lon_x']
            curr_pos.loc[i, 'Lat_y'] = curr_pos.loc[i, 'Lat_x']
            curr_pos.loc[i, 'Time_y'] = curr_pos.loc[i, 'Time_x']
            curr_pos.loc[i, 'Lines_y'] = curr_pos.loc[i, 'Lines_x']
            curr_pos.loc[i, 'Brigade_y'] = curr_pos.loc[i, 'Brigade_x']

    for i in curr_pos.index:
        if not isnan(speed[i]):
            curr_pos.loc[i, 'speed'] = speed[i]


def endprint(all_arrival, bus_lates, speedmapfile, alllatefile, all_exceeded_buses, curr_pos, bus_time_ind, speedmap):
    max_late = 0
    stop_name = ''
    all_buses_at_stop = 0
    for key in all_arrival:
        if all_arrival[key][0] > max_late:
            max_late = all_arrival[key][0]
            stop_name = key
            all_buses_at_stop = all_arrival[key][1]

    alllate = sum([all_arrival[key][0] for key in all_arrival])
    allarrival = sum([all_arrival[key][1] for key in all_arrival])
    speedmapfile += '.html'
    alllatefile += '.json'
    bus_lates = sorted(bus_lates.items(), key=lambda x: x[1], reverse=True)
    print('Top 3 lines with most late buses: {}, {}, {}'.format(bus_lates[0], bus_lates[1], bus_lates[2]))
    print('Most buses arrived late at stop {}, {} late on {}'.format(stop_name, max_late, all_buses_at_stop))
    print('Buses arrived late {} on {}, {}%'.format(alllate, allarrival, round(alllate / allarrival * 100, 2)))

    print('Buses exceeded speed limit of 50km/h: ' + str(all_exceeded_buses[all_exceeded_buses].count()))
    print('For futher information see ' + speedmapfile)
    print('About all late bus arrivals see ' + alllatefile)
    print('End time:', curr_pos['Time'][bus_time_ind])
    speedmap.save(speedmapfile)

    late_buses_out = {key: {'late:': all_arrival[key][0], 'all:': all_arrival[key][1]} for key in all_arrival}
    with open(alllatefile, 'w') as outfile:
        outfile.write(json.dumps(late_buses_out, indent=4))

def main():
    posfile, amount, timetablefile, speedmapfile, alllatefile = argsparser()

    timetable = {}
    with open(timetablefile + '.json', 'r') as infile:
        timetable = json.loads(infile.read())

    # Which time in timetable is the actual time
    timetable_timeind = {key: 0 for key in timetable}

    # Pairs of [late_arrivals, all arrivals] at all stops
    all_arrival = {}
    bus_lates = {}

    # Map of all points where buses exceeded speed limit
    speedmap = folium.Map(location=[MAP_CENTER_LAT, MAP_CENTER_LON], zoom_start=MAP_ZOOM)
    exceeded_points = plugins.MarkerCluster().add_to(speedmap)

    curr_pos = read_file(posfile + str(0) + '.json')
    curr_pos = pandas.concat([curr_pos, pandas.DataFrame({'speed': [0] * len(curr_pos.index)}, index=curr_pos.index)],
                             axis=1)

    # True if bus ever exceeded speed limit
    all_exceeded_buses = pandas.Series([False]*curr_pos.count(), index=curr_pos.index)
    bus_time_ind = curr_pos.index[1]
    print('Begin time:', curr_pos['Time'][bus_time_ind])

    for i in range(1, amount):
        next_pos = read_file(posfile + str(i) + '.json')
        curr_pos = curr_pos.merge(next_pos, how='outer', on='VehicleNumber')
        speed = curr_pos.apply(distance, axis=1) / curr_pos.apply(hour_diff, axis=1)

        # It's unlikely for buses to exceed 130km/h, it would probably be an error.
        exceeded_buses = (50 < speed) & (speed < 130)

        curr_pos[exceeded_buses].apply(add_point, axis=1, exceeded_points=exceeded_points, speed=speed)

        # Update list of buses exceeding speed.
        all_exceeded_buses = pandas.concat([all_exceeded_buses, exceeded_buses], axis=1)
        all_exceeded_buses[0] = all_exceeded_buses[0].fillna(False)
        all_exceeded_buses[1] = all_exceeded_buses[1].fillna(False)
        all_exceeded_buses = all_exceeded_buses[0] | all_exceeded_buses[1]

        update_new_pos(curr_pos, speed)

        # Check if buses arrive late.
        curr_pos.apply(check_late_bus, axis=1, timetable=timetable, timetable_timeind=timetable_timeind,
                       all_arrival=all_arrival, bus_lates=bus_lates)

        curr_pos = curr_pos[['Lon_y', 'Lat_y', 'Time_y', 'Lines_y', 'Brigade_y', 'speed']]
        curr_pos = curr_pos.rename(columns={'Lon_y': 'Lon',
                                            'Lat_y': 'Lat',
                                            'Time_y': 'Time',
                                            'Lines_y': 'Lines',
                                            'Brigade_y': 'Brigade'})

    endprint(all_arrival, bus_lates, speedmapfile, alllatefile, all_exceeded_buses, curr_pos, bus_time_ind, speedmap)


main()
