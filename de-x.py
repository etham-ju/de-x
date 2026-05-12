##
# de-x.py -- delete all your tweets w/o API access
# Copyright 2023 Thorsten Schroeder
#
# Published under 2-Clause BSD License (https://opensource.org/license/bsd-2-clause/)
#
# Please see README.md for more information
##

import sys
import json
import time
import random
import requests

def _tweet_extract(d):
    t = d['tweet']
    # Skip retweets — they need DeleteRetweet with source_tweet_id
    if t['full_text'].startswith('RT @'):
        return None
    return {'tweet_id': t['id_str']}


def _retweet_extract(d):
    t = d['tweet']
    if not t['full_text'].startswith('RT @'):
        return None
    # The archive doesn't carry the source tweet id directly; it's only
    # available via extended_entities.media[*].source_status_id for RTs
    # that have media. RTs without media are skipped.
    for m in t.get('extended_entities', {}).get('media', []):
        src = m.get('source_status_id_str') or m.get('source_status_id')
        if src:
            return {'source_tweet_id': str(src)}
    return None


TWEETS_MODE = {
    'label': 'delete tweet',
    'url': "https://x.com/i/api/graphql/nxpZCY2K-I6QoFHAHeojFQ/DeleteTweet",
    'query_id': "nxpZCY2K-I6QoFHAHeojFQ",
    'extract': _tweet_extract,
    'key': 'tweet_id',
}

RETWEETS_MODE = {
    'label': 'delete retweet',
    'url': "https://x.com/i/api/graphql/ZyZigVsNiFO6v1dEks1eWg/DeleteRetweet",
    'query_id': "ZyZigVsNiFO6v1dEks1eWg",
    'extract': _retweet_extract,
    'key': 'source_tweet_id',
}

LIKES_MODE = {
    'label': 'unlike tweet',
    'url': "https://x.com/i/api/graphql/ZYKSe-w7KEslx3JhSIk5LA/UnfavoriteTweet",
    'query_id': "ZYKSe-w7KEslx3JhSIk5LA",
    'extract': lambda d: {'tweet_id': d['like']['tweetId']},
    'key': 'tweet_id',
}

# Community-reported safe pacing (gist: aymericbeaumet/d1d6799a1b765c3c8bc0b675b1a1547d):
# ~500 requests per 5-15min window. Use a 3s floor and a periodic longer rest.
MIN_SLEEP = 3.0
REST_EVERY = 50
REST_SECONDS = 30


def get_items(json_data, extract):

    result = []
    skipped = 0
    data = json.loads(json_data)

    for d in data:
        item = extract(d)
        if item is None:
            skipped += 1
            continue
        result.append(item)

    return result, skipped


def load_items(path, extract):

    with open(path, encoding='UTF-8') as f:
        raw = f.read()
    # skip data until first '['
    i = raw.find('[')
    return get_items(raw[i:], extract)

def parse_req_headers(request_file):

    sess = {}

    with open(request_file) as f:
        line = f.readline()
        while line:
            try:
                k,v = line.split(':', 1)
                val = v.lstrip().rstrip()
                sess[k] = val
            except:
                # ignore empty lines
                pass

            line = f.readline()

    return sess

def main(ac, av):

    if ac != 4:
        print(f"[!] usage: {av[0]} <tweets.js> <like.js> <req-headers>")
        return

    tweet_items, _ = load_items(av[1], TWEETS_MODE['extract'])
    retweet_items, _ = load_items(av[1], RETWEETS_MODE['extract'])
    like_items, _ = load_items(av[2], LIKES_MODE['extract'])

    session = parse_req_headers(av[3])

    print(f"[i] {len(tweet_items)} tweets to delete, "
          f"{len(retweet_items)} retweets to remove (of those with media only), "
          f"{len(like_items)} likes to remove")

    run_batch(session, tweet_items, TWEETS_MODE)
    run_batch(session, retweet_items, RETWEETS_MODE)
    run_batch(session, like_items, LIKES_MODE)


def run_batch(session, items, mode):
    total = len(items)
    if total == 0:
        print(f"[i] nothing to do for '{mode['label']}'")
        return
    print(f"[i] starting '{mode['label']}' batch: {total} items")
    started = time.time()
    for n, item in enumerate(items, 1):
        print(f"[#] {mode['label']} {n}/{total}")
        delete_tweet(session, item, mode)
        elapsed = time.time() - started
        rate = n / elapsed if elapsed > 0 else 0
        eta = (total - n) / rate if rate > 0 else 0
        print(f"[i] progress {n}/{total} "
              f"({rate*60:.1f}/min, ETA {eta/60:.1f}min)")
        if n % REST_EVERY == 0 and n != total:
            print(f"[z] scheduled rest: completed {n}, pausing {REST_SECONDS}s")
            time.sleep(REST_SECONDS)


def delete_tweet(session, item, mode):

    key = mode['key']
    print(f"[*] {mode['label']} {item[key]}")
    delete_url = mode['url']
    data = {"variables": item, "queryId": mode['query_id']}

    # set or re-set correct content-type header
    session["content-type"] = 'application/json'

    backoff = 60
    while True:
        r = requests.post(delete_url, data=json.dumps(data), headers=session)
        print(r.status_code, r.reason)
        print(r.text[:500] + '...')

        limit = r.headers.get('x-rate-limit-limit', '?')
        remaining_hdr = r.headers.get('x-rate-limit-remaining', '?')
        reset_hdr = r.headers.get('x-rate-limit-reset', '0')
        reset = int(reset_hdr) if reset_hdr.isdigit() else 0
        now = int(time.time())
        window = max(reset - now, 1)
        reset_at = time.strftime('%H:%M:%S', time.localtime(reset)) if reset else '?'

        print(f"[rl] limit={limit} remaining={remaining_hdr} "
              f"reset_in={window}s (at {reset_at})")

        if r.status_code == 429:
            sleep_s = max(window, backoff) if reset else backoff
            print(f"[!] 429 rate limited — sleeping {sleep_s}s "
                  f"(backoff floor={backoff}s)")
            time.sleep(sleep_s)
            backoff = min(backoff * 2, 900)
            continue

        remaining = int(remaining_hdr) if remaining_hdr.isdigit() else -1

        if remaining > 0:
            # spread what's left evenly across the rest of the window, plus jitter
            base = window / remaining
            sleep_s = base + random.uniform(0.3, 1.2)
            reason = f"pace: {window}s / {remaining} left = {base:.2f}s + jitter"
        elif reset:
            # no budget left — wait for the window to reset
            sleep_s = window + random.uniform(1.0, 3.0)
            reason = f"budget exhausted, waiting {window}s for reset"
        else:
            sleep_s = random.uniform(3.0, 5.0)
            reason = "no rate-limit headers returned, default jitter"

        # enforce a floor so we never outrun the community-observed safe rate
        floor = MIN_SLEEP + random.uniform(0, 1.0)
        if floor > sleep_s:
            reason += f" — bumped up to floor {floor:.2f}s"
            sleep_s = floor

        print(f"[~] sleep {sleep_s:.2f}s ({reason})")
        time.sleep(sleep_s)
        return


if __name__ == '__main__':

    main(len(sys.argv), sys.argv)
