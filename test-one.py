##
# test-one.py -- single-tweet diagnostic for de-x.py
#
# usage: python test-one.py <tweet_id> <req-headers.txt>
#
# Sends one DeleteTweet request and prints the full response so you can
# tell whether the queryId is stale, the tweet requires a different
# endpoint (retweets use DeleteRetweet), or something else is going on.
##

import sys
import json
import importlib.util
import pathlib
import requests

_here = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("de_x", _here / "de-x.py")
_de_x = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_de_x)
TWEETS_MODE = _de_x.TWEETS_MODE
parse_req_headers = _de_x.parse_req_headers


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <tweet_id> <req-headers.txt>")
        return

    tweet_id = sys.argv[1]
    session = parse_req_headers(sys.argv[2])

    # Strip anything that will break the request:
    # - HTTP/2 pseudo-headers (":method", ":path", ":authority", ...)
    # - empty keys from bad split
    # - stale content-length (requests recomputes it)
    # - host (requests sets it from URL)
    cleaned = {}
    dropped = []
    for k, v in session.items():
        kl = k.strip().lower()
        if not kl or kl.startswith(':') or kl in ('content-length', 'host'):
            dropped.append(k)
            continue
        cleaned[k] = v
    cleaned["content-type"] = "application/json"

    url = TWEETS_MODE["url"]
    data = {
        "variables": {"tweet_id": tweet_id},
        "queryId": TWEETS_MODE["query_id"],
    }

    print(f"[>] POST {url}")
    print(f"[>] body: {json.dumps(data)}")
    if dropped:
        print(f"[>] dropped bogus headers: {dropped}")
    print(f"[>] sending {len(cleaned)} headers: "
          f"{sorted(k.lower() for k in cleaned)}")
    r = requests.post(url, data=json.dumps(data), headers=cleaned)

    print(f"\n[<] {r.status_code} {r.reason}")
    print("[<] response headers:")
    for k in ("x-rate-limit-limit", "x-rate-limit-remaining",
              "x-rate-limit-reset", "x-transaction-id",
              "content-type", "x-response-time"):
        if k in r.headers:
            print(f"    {k}: {r.headers[k]}")
    print(f"\n[<] body:\n{r.text}")


if __name__ == "__main__":
    main()
