import argparse

import pandas
import json
import requests
from time import sleep

apikey = '5c994126-6936-4ed2-9bc4-516294b8571f'
allstopsurl = 'https://api.um.warszawa.pl/api/action/dbstore_get/'
timetableurl = 'https://api.um.warszawa.pl/api/action/dbtimetable_get/'


def get_all_stops():
    query = {
        'id': 'ab75c33d-3a26-4342-b36a-6e5fef0a3ac3',
        'apikey': apikey
    }

    all_stops_req_dict = {'result': "Błędna metoda lub parametry wywołania"}
    while all_stops_req_dict['result'] == "Błędna metoda lub parametry wywołania":
        all_stops_req = requests.get(allstopsurl, query)
        all_stops_req_dict = all_stops_req.json()

    return all_stops_req_dict['result']


def get_all_lines(stopid, stopnr):
    lines_res_id = '88cd555f-6f31-43ca-9de4-66c479ad5942'
    all_lines_req = requests.get(timetableurl, {'id': lines_res_id,
                                       'busstopId': stopid,
                                       'busstopNr': stopnr,
                                       'apikey': apikey
                                       })
    return all_lines_req.json()['result']


def get_line_timetable(stopid, stopnr, busline):
    time_res_id = 'e923fa0e-d96c-43f9-ae6e-60518c9f3238'
    line_timetable = requests.get(timetableurl, {'id': time_res_id,
                                        'busstopId': stopid,
                                        'busstopNr': stopnr,
                                        'line': busline,
                                        'apikey': apikey
                                        })

    return line_timetable.json()['result']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=str)
    args = parser.parse_args()
    file = args.filename

    all_stops = get_all_stops()

    stopid_list = [stop['values'][0]['value'] for stop in all_stops]
    stopnr_list = [stop['values'][1]['value'] for stop in all_stops]
    lon_list = [stop['values'][5]['value'] for stop in all_stops]
    lat_list = [stop['values'][4]['value'] for stop in all_stops]
    name_list = [stop['values'][2]['value'] for stop in all_stops]

    whole_timetable = {}
    # iterations = len(stopnr_list)
    for i in range(2):
        print('{}-{}'.format(stopid_list[i], stopnr_list[i]))
        all_lines = get_all_lines(stopid_list[i], stopnr_list[i])
        for line in all_lines:
            bus_line = line['values'][0]['value']
            line_timetable = get_line_timetable(stopid_list[i], stopnr_list[i], bus_line)
            for bus in line_timetable:
                # bus_id = line-brigade (string concat)
                bus_id = str(bus_line) + '-' + str(bus['values'][2]['value'])
                newv = (bus['values'][5]['value'], lon_list[i], lat_list[i], name_list[i] + str(stopnr_list[i]))
                if bus_id not in whole_timetable:
                    whole_timetable.update({bus_id: [newv]})
                else:
                    whole_timetable[bus_id].append(newv)

    for bus in whole_timetable:
        whole_timetable[bus].sort(key=lambda x: x[0])

    with open(file + '.json', 'w') as outfile:
        outfile.write(json.dumps(whole_timetable, indent=4))
        outfile.close()


main()