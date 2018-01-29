#!/usr/bin/env python3


"""
expLoLer - explore LoL data
aaronjst93@gmail.com
"""


from multiprocessing import Lock
from multiprocessing.pool import Pool
from os import listdir
from time import sleep

import json
import pickle
import requests


def api_get(endpoint: str, params: str = {}):
    """Base GET request for the Riot Games API."""

    params['api_key'] = 'RGAPI-d623dbb1-7c6e-446e-8c98-c50d4bc1b1bd'

    url = 'https://na1.api.riotgames.com{}'.format(endpoint)

    response = requests.get(url, params=params)

    stdo_lock.acquire()
    print(response.url)
    stdo_lock.release()

    if response.status_code == requests.codes.ok:
        return response.json()
    else:
        stdo_lock.acquire()
        print(response.content)
        stdo_lock.release()

        if response.status_code >= 500:
            sleep(2)

            return api_get(endpoint, params)
        else:
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
        'queue': 420,  # Ranked 5v5 Solo-Queue
        'beginIndex': start_index,
        'season': 9  # 2017 Season
    }

    endpoint = '/lol/match/v3/matchlists/by-account/{}'.format(account_id)

    data = api_get(endpoint, params=params)

    match_ids = list(map(lambda x: x['gameId'], data['matches']))

    if data['endIndex'] < data['totalGames'] - 1:
        return match_ids + get_matchlist(account_id, data['endIndex'])
    else:
        stdo_lock.acquire()
        print('\nAccount {} played {} matches in the 2017 season.\n'.format(
            account_id, data['totalGames']))
        stdo_lock.release()

        return match_ids


def get_matches(*match_ids: int):
    """Get full match data for matches corresponding to ``match_ids``."""

    current_matches = map(int, listdir('spider/matches'))

    for mid in set(match_ids) - set(current_matches):
        if mid not in current_matches:
            match = None

            try:
                match = api_get('/lol/match/v3/matches/{}'.format(mid))
            except requests.exceptions.HTTPError:
                continue

            rw_lock.acquire()
            pickle.dump(match, open('spider/matches/{}'.format(mid), 'wb'))
            rw_lock.release()


def get_matches_for_account(account_id: int):
    """Get matches for given ``account_id``."""

    match_ids = None

    if account_id in map(int, listdir('spider/accounts')):
        rw_lock.acquire()
        match_ids = pickle.load(
            open('spider/accounts/{}'.format(account_id), 'rb'))
        rw_lock.release()
    else:
        try:
            match_ids = get_matchlist(account_id)
        except requests.exceptions.HTTPError:
            return

        rw_lock.acquire()
        pickle.dump(match_ids,
                    open('spider/accounts/{}'.format(account_id), 'wb'))
        rw_lock.release()

        get_matches(*match_ids)


def initialize_locks(lock1: Lock, lock2: Lock):
    """Initialize global locks for use by process pool."""

    global rw_lock, stdo_lock

    rw_lock = lock1
    stdo_lock = lock2


def spider_matches(account_ids: list, degrees: int = 1):
    """From an initial list of ``account_ids``, find relevant matches.
    Use new accounts found to additionally search for further matches
    when degrees > 1.
    """

    if degrees < 1:
        raise ValueError('``degrees`` must be >= 1')

    # new_account_ids = set()

    lock1 = Lock()
    lock2 = Lock()

    pool = Pool(initializer=initialize_locks, initargs=(lock1, lock2))

    pool.imap_unordered(get_matches_for_account, account_ids)
    pool.close()
    pool.join()

    '''  # Rework to not use local ``new_account_ids``
    if degrees > 1:
        print('\nFound {} new accounts, spidering to matches.\n'.format(
            len(new_account_ids)))

        spider_matches(list(new_account_ids), degrees - 1)
    else:
        n_accounts = len(listdir('spider/accounts'))
        n_matches = len(listdir('spider/matches'))

        print('\n\nSpidered to {} accounts and {} matches.'.format(
            n_accounts, n_matches))
    '''


if __name__ == '__main__':
    # get_seed_data()
    # seed_accounts()

    SUMMONERS = [
        39016347,  # HushRaze
        39137330,  # PowerK00K
        39010660,  # VanityDemon
        35765317,  # ILovePhoKingLOL
        33662222,  # 19970809
        202637677  # Miss Nini
    ]

    ACCOUNTS = pickle.load(open('seed/account_ids.pickle', 'rb'))
    ACCOUNTS = list(set(ACCOUNTS + SUMMONERS))

    print('{} seed accounts'.format(len(ACCOUNTS)))

    spider_matches(ACCOUNTS)

    print('done')
