#!/usr/bin/env python3


"""
expLoLer - explore LoL data
aaronjst93@gmail.com
"""


from os import listdir
from time import sleep

import json
import pickle
import requests


def api_get(endpoint: str, params: str = {}):
    """Base GET request for the LoL API."""

    sleep(1.2)  # Handles 100 requests / 2 minutes rate limit

    params['api_key'] = '<api_key>' # censored

    url = 'https://na1.api.riotgames.com{}'.format(endpoint)

    response = requests.get(url, params=params)

    print(response.url)

    if response.status_code == requests.codes.ok:
        return response.json()
    else:
        print(response.content)

        response.raise_for_status()


def get_seed_data():
    """Get bulk seed data."""

    for i in range(1, 11):
        url = ('https://s3-us-west-1.amazonaws.com/riot-developer-portal/seed-'
               'data/matches{}.json').format(i)

        response = requests.get(url)

        if response.status_code == requests.codes.ok:
            json.dump(response.json(),
                      open('seed/matches{}.json'.format(i), 'w'))
        else:
            response.raise_for_status()


def seed_accounts():
    """Extract account_ids from seed match data."""

    account_ids = []

    for i in range(1, 11):
        matches = json.load(
            open('seed/matches{}.json'.format(i), 'r'))['matches']

        for match in matches:
            for participant in match['participantIdentities']:
                account_ids.append(participant['player']['accountId'])

    account_ids = list(set(account_ids))

    print('Extracted {} unique accounts from seed match data.'.format(
        len(account_ids)))

    pickle.dump(account_ids, open('seed/account_ids.pickle', 'wb'))


def get_account_ids_from_name(*summoner_names: str):
    """Get account_ids for provided summoner names."""

    account_ids = []

    for name in summoner_names:
        data = api_get('/lol/summoner/v3/summoners/by-name/{}'.format(name))
        account_ids.append(data['accountId'])

    return list(set(account_ids))


def get_account_ids_from_match(*matches: dict):
    """From an initial list of matches, find all account ids."""

    account_ids = []

    for match in matches:
        for participant in match['participantIdentities']:
            account_ids.append(participant['player']['accountId'])

    return list(set(account_ids))


def get_matchlist(account_id: str, start_index: int = 0):
    """Get a match list using provided ``account_id`` and ``start_index``.
    Recurse if total matches > ending index.
    """

    params = {
        'queue': 420,
        'beginIndex': start_index,
        'season': 9
    }

    endpoint = '/lol/match/v3/matchlists/by-account/{}'.format(account_id)

    data = api_get(endpoint, params=params)

    match_ids = list(map(lambda x: x['gameId'], data['matches']))

    if data['endIndex'] < data['totalGames'] - 1:
        return match_ids + get_matchlist(account_id, data['endIndex'])
    else:
        print('\nAccount {} played {} matches in the 2017 season.\n'.format(
            account_id, data['totalGames']))

        return match_ids


def get_matches(*match_ids: int):
    """Get full match data for matches corresponding to ``match_ids``."""

    current_matches = map(int, listdir('spider/matches'))
    new_matches = []

    for mid in set(match_ids) - set(current_matches):
        if mid not in current_matches:
            match = api_get('/lol/match/v3/matches/{}'.format(mid))

            pickle.dump(match, open('spider/matches/{}'.format(mid), 'wb'))

            new_matches.append(match)

    return new_matches


def spider_matches(account_ids: list, degrees: int = 1):
    """From an initial list of ``account_ids``, find relevant matches.
    Use new accounts found to additionally search for further matches
    when degrees > 1.
    """

    if degrees < 1:
        raise ValueError('``degrees`` must be >= 1')

    new_account_ids = set()

    for aid in account_ids:
        try:
            match_ids = get_matchlist(aid)

            pickle.dump(match_ids, open('spider/accounts/{}'.format(aid), 'wb'))

            new_matches = get_matches(*match_ids)

            if degrees > 1:
                new_aids = get_account_ids_from_match(*new_matches)

                new_account_ids |= set(new_aids) - set(account_ids)
        except requests.exceptions.HTTPError:
            continue

    if len(new_account_ids) > 0 and degrees > 1:
        print('\nFound {} new accounts, spidering to matches.\n'.format(
            len(new_account_ids)))

        spider_matches(list(new_account_ids), degrees - 1)
    else:
        n_accounts = len(listdir('spider/accounts'))
        n_matches = len(listdir('spider/matches'))

        print('\n\nSpidered to {} accounts and {} matches.'.format(
            n_accounts, n_matches))


if __name__ == '__main__':
    # get_seed_data()
    # seed_accounts()

    SUMMONERS = (
        'HushRaze',
        'PowerK00K',
        'VanityDemon',
        'ILovePhoKingLOL',
        '19970809',
        'Miss Nini'
    )

    ACCOUNTS = pickle.load(open('seed/account_ids.pickle', 'rb'))
    ACCOUNTS = list(set(ACCOUNTS + get_account_ids_from_name(*SUMMONERS)))

    spider_matches(ACCOUNTS, degrees=5)
