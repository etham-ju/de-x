##
# de-x.py -- delete all your tweets w/o API access
# Copyright 2023 Thorsten Schroeder
#
# Published under 2-Clause BSD License (https://opensource.org/license/bsd-2-clause/)
#
# Please see README.md for more information
##

import sys
import os
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
    'state': 'tweets',
    'url': "https://x.com/i/api/graphql/nxpZCY2K-I6QoFHAHeojFQ/DeleteTweet",
    'query_id': "nxpZCY2K-I6QoFHAHeojFQ",
    'extract': _tweet_extract,
    'key': 'tweet_id',
}

RETWEETS_MODE = {
    'label': 'delete retweet',
    'state': 'retweets',
    'url': "https://x.com/i/api/graphql/ZyZigVsNiFO6v1dEks1eWg/DeleteRetweet",
    'query_id': "ZyZigVsNiFO6v1dEks1eWg",
    'extract': _retweet_extract,
    'key': 'source_tweet_id',
}

LIKES_MODE = {
    'label': 'unlike tweet',
    'state': 'likes',
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

# Resume support: ids that finished (deleted or already-gone) are recorded
# here so a re-run skips them. Safe to delete to start over.
STATE_FILE = 'de-x.state.json'


def load_state():
    try:
        with open(STATE_FILE, encoding='UTF-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return {
        'tweets': set(data.get('tweets', [])),
        'retweets': set(data.get('retweets', [])),
        'likes': set(data.get('likes', [])),
    }


def save_state(state):
    serializable = {k: sorted(v) for k, v in state.items()}
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w', encoding='UTF-8') as f:
        json.dump(serializable, f, indent=2)
    # atomic replace so a crash mid-write can't corrupt the state file
    os.replace(tmp, STATE_FILE)


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
    state = load_state()

    print(f"[i] {len(tweet_items)} tweets to delete, "
          f"{len(retweet_items)} retweets to remove (of those with media only), "
          f"{len(like_items)} likes to remove")
    print(f"[i] state: already finished tweets={len(state['tweets'])} "
          f"retweets={len(state['retweets'])} likes={len(state['likes'])}")

    run_batch(session, tweet_items, TWEETS_MODE, state)
    run_batch(session, retweet_items, RETWEETS_MODE, state)
    run_batch(session, like_items, LIKES_MODE, state)


def run_batch(session, items, mode, state):
    bucket = state[mode['state']]
    key = mode['key']
    pending = [it for it in items if it[key] not in bucket]
    skipped_resume = len(items) - len(pending)
    total = len(pending)

    if skipped_resume:
        print(f"[i] '{mode['label']}': skipping {skipped_resume} already "
              f"recorded in {STATE_FILE}")
    if total == 0:
        print(f"[i] nothing to do for '{mode['label']}'")
        return

    print(f"[i] starting '{mode['label']}' batch: {total} items")
    started = time.time()
    stats = {'ok': 0, 'gone': 0, 'error': 0}
    for n, item in enumerate(pending, 1):
        print(f"[#] {mode['label']} {n}/{total}")
        outcome = delete_tweet(session, item, mode)
        stats[outcome] = stats.get(outcome, 0) + 1
        if outcome in ('ok', 'gone'):
            bucket.add(item[key])
            save_state(state)
        elapsed = time.time() - started
        rate = n / elapsed if elapsed > 0 else 0
        eta = (total - n) / rate if rate > 0 else 0
        print(f"[i] progress {n}/{total} "
              f"(ok={stats['ok']} skipped={stats['gone']} err={stats['error']}, "
              f"{rate*60:.1f}/min, ETA {eta/60:.1f}min)")
        if n % REST_EVERY == 0 and n != total:
            print(f"[z] scheduled rest: completed {n}, pausing {REST_SECONDS}s")
            time.sleep(REST_SECONDS)
    print(f"[=] '{mode['label']}' done: ok={stats['ok']} "
          f"already-gone={stats['gone']} errors={stats['error']}")


def _is_already_gone(status, body):
    """Detect responses that mean 'this tweet/like is already removed'."""
    if status == 404:
        # X returns 404 with empty body for already-deleted tweets/retweets
        return True
    if status == 200 and body:
        # GraphQL sometimes returns 200 with an errors array for missing tweets
        markers = (
            'No status found',
            'Tweet not found',
            'not authorized to view',
            "doesn't exist",
        )
        if any(m in body for m in markers):
            return True
    return False


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
        print(r.text[:500] + ('...' if len(r.text) > 500 else ''))

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

        if _is_already_gone(r.status_code, r.text):
            print(f"[skip] {item[key]} already gone — no action needed")
            outcome = 'gone'
        elif r.status_code == 200:
            outcome = 'ok'
        else:
            print(f"[!] unexpected status {r.status_code}, continuing")
            outcome = 'error'

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
        return outcome


if __name__ == '__main__':

    main(len(sys.argv), sys.argv)
