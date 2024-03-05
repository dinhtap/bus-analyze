import requests
import json
import time
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=str)
    parser.add_argument('amount', type=int)
    args = parser.parse_args()
    file = args.filename
    amount = args.amount

    url = 'https://api.um.warszawa.pl/api/action/busestrams_get/'
    query = {
        'resource_id': '%20f2e5503e%02927d-4ad3-9500-4ab9e55deb59',
        'apikey': '5c994126-6936-4ed2-9bc4-516294b8571f',
        'type': 1
    }

    # Getting positon of buses each 70 seconds, 'amount' times, saves to filename + i + .json.
    for i in range(amount):
        filename = file + str(i) + '.json'
        response_dict = {'result': "Błędna metoda lub parametry wywołania"}
        while response_dict['result'] == "Błędna metoda lub parametry wywołania":
            time.sleep(1)
            response = requests.get(url, query)
            response_dict = response.json()
        with open(filename, 'w') as outfile:
            outfile.write(json.dumps(response_dict['result'], indent=4))

        time.sleep(70)


main()
