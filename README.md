# de-x.py

**Language:** [English](README.md) · [한국어](README.ko.md)

### About this version
Since the original version(3 years ago), a lot has been changed. This script has been updated to support X's current rate-limiting, authentication requirements, and endpoint changes. 

**This script can be used to delete the whole history of your tweets, retweets, and replies — and to remove all of your likes in the same run.**

As Elmo restricted access to Twitter's APIs, many tools that did the same job doesn't work anymore, without registering a developer account at X/Twitter.

However, this small script does not depend on those restricted APIs. There is no need to register a developer account nor is it necessary to pay for API access. Only a few manual steps need to be carried out by the user, these steps are explained in detail below.

## Preparation

1. Request an archive of your data at X/Twitter. This archive will be available for download after a few days (mine took like 2 days). If your data is ready for download, you'll receive a notification in your Twitter-App or via E-mail. ![Request Twitter archive at X](doc/archive.png)
2. Once your archive has been downloaded, you need to extract the ZIP-Archive on your disk. You'll need two files from the archive: `tweets.js` (every tweet/reply/retweet with its tweet-ID) and `like.js` (every tweet you have liked, with its tweet-ID).
3. To enable this python script to delete posts with the tweet-IDs from your archive, you must provide session information as well, otherwise the python script will not be able to authorize. X's current anti-abuse checks reject requests that are missing any of the headers a real browser sends, so you need to capture the **full** header set — not just three or four. The easiest way:
   1. Edge/Chrome: Log into X as usual, then open DevTools (`Ctrl-Shift-i` / `Cmd-Opt-i`) and switch to the *Network* tab. Delete any one tweet (or unlike any one post) so that a request to `/i/api/graphql/…/DeleteTweet` (or `/UnfavoriteTweet`) appears in the panel. Right-click that request → **Copy → Copy as cURL**. This captures every header the browser actually sent, including the ones X now requires (`x-client-transaction-id`, `x-twitter-auth-type`, `x-twitter-active-user`, `x-csrf-token`, `x-twitter-client-language`, `user-agent`, `referer`, `origin`, `accept`, `accept-language`, `cookie`, `authorization`, and the `sec-*` set). ![Copy & Paste session headers at twitter.com](doc/session.png)
   2. Firefox: same flow via *Network → Copy → Copy as cURL*.
   3. burp suite: record a logged-in X session and copy the client request headers of a real `DeleteTweet` call.
4. Paste every `-H 'key: value'` line from the cURL into `request-headers.txt`, one header per line in `key: value` form (strip the `-H '...'` wrapper). A working file looks roughly like this:
```
accept: */*
accept-language: ko,en;q=0.9,en-US;q=0.8
authorization: Bearer AAAAAAAAAAAAAAAAAAAAANR[...]
cookie: [...] auth_token=[...]; ct0=[...]; twid=u%3D[...]; _twitter_sess=[...]
origin: https://x.com
referer: https://x.com/
sec-ch-ua: "Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"
sec-ch-ua-mobile: ?0
sec-ch-ua-platform: "macOS"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 [...]
x-client-transaction-id: [base64 blob — see caveat below]
x-csrf-token: [same value as the ct0 cookie]
x-twitter-active-user: yes
x-twitter-auth-type: OAuth2Session
x-twitter-client-language: en
```

> **Important:** a minimal file with only `Authorization`, `X-Csrf-Token`, and `Cookie` will not work — X replies with `404 Not Found` and an empty body on every delete call. `x-client-transaction-id`, `x-twitter-auth-type`, `x-twitter-active-user`, `referer`, and `user-agent` are required.

> **`x-client-transaction-id` caveat:** the browser recomputes this value for every request, but this script sends the same captured value every time. That usually works for a few hundred deletes, then X starts rejecting with `404`. If that happens, capture a fresh `DeleteTweet` request from the browser and replace just that one line in `request-headers.txt`.

## Run

After you've received your twitter archive and edited a request-header file for a current session (as explained above), we can call our script:

```
python3 de-x.py tweets.js like.js request-headers.txt
```

The script runs three passes, in order:

1. **`DeleteTweet`** — your original tweets and replies listed in `tweets.js`.
2. **`DeleteRetweet`** — retweets from `tweets.js`. X requires the *source* tweet's id for this endpoint, but the archive only carries the source id for retweets that have media attached, so RTs without media are skipped and reported in the startup summary.
3. **`UnfavoriteTweet`** — every entry in `like.js`.

If a request hangs with `404 Not Found` and an empty body, see the `x-client-transaction-id` caveat in the Preparation section — X is rejecting the request because of the replayed header.

### Debugging a single call

A small helper is included for sanity-checking one tweet before you kick off the full run:

```
python3 test-one.py <tweet_id> request-headers.txt
```

It prints the outgoing headers, the status code, the rate-limit response headers, and the response body so you can tell whether your session is being accepted.

## Rate limiting

X rate-limits `DeleteTweet`, `DeleteRetweet`, and `UnfavoriteTweet` independently (~200 requests per window for each). The script tries hard not to trip those limits:

- It reads the `x-rate-limit-remaining` / `x-rate-limit-reset` headers returned on every response and spreads the remaining budget evenly across the rest of the window.
- A **3 second floor** is enforced between requests, matching the community-observed safe base rate (see [this gist thread](https://gist.github.com/aymericbeaumet/d1d6799a1b765c3c8bc0b675b1a1547d?permalink_comment_id=4694790#file-delete-likes-from-twitter-md)).
- After every **50 requests** the script takes a **30 second rest**.
- If a 429 is returned anyway, it waits until the advertised reset time (or does exponential backoff, 60s → 15min cap) and retries the same ID, so nothing is skipped.

This means long runs are slow but steady — plan for hours, not minutes, if you have thousands of tweets or likes to remove.

## Background

If you know the tweet-id, you can delete the corresponding tweet by calling an API with that specific ID, and no rate limiting will be in place. So the first and most important step is to get a list of all tweets (and thus tweet-ids) that shall be deleted. You can do this, using twitter-APIs, but these APIs are restricted and you have to pay for it. Even if you pay for it, there are quite a few limitations and you might not be able to gather a list of all of your tweets.

Thus, it is easier to simply request an archive of all tweets that you have posted so far. This dataset includes all meta-data and, of course, also the tweet-id we are looking for in the first place. You don't have to pay for it, it is complete and machine readable: win.

The archive contains a file called `tweets.js` which is basically a JSON encoded data structure, a list of all of your tweets. It also contains `like.js`, the same shape but for tweets you have liked.

X's `DeleteTweet`, `DeleteRetweet`, and `UnfavoriteTweet` GraphQL endpoints are not restricted behind the paid developer program, and can be called from a normal logged-in session as long as the request carries the exact header set a browser sends. Using this approach, you can delete around 3000 tweets in roughly 30 min (*) — though with the conservative pacing described above, expect it to take longer on large archives.

### Retweets caveat

`DeleteRetweet` takes the **source tweet's** id (the id of the original tweet that was retweeted), not the id the archive records for your retweet. The Twitter archive only carries the source id in `extended_entities.media[].source_status_id` for RTs that contained media, so retweets of plain-text posts can't be un-retweeted from the archive alone. Those rows are counted and skipped on startup; to clean them up you'd need a separate step that resolves each retweet id → source id via the web API first.

(*) while sitting in a high-speed train of *Deutsche Bahn* somewhere between Amsterdam and Hamburg, using 4G network.

## Conclusion

There is no *One Click Delete Everything* tool available and it never will. This is due to Twitter's massive restrictions on using their APIs to control your own data. Of course, they would like to keep your data. Forever. However, If you don't want your data being archived at Twitter until global heat finally also kills all machines on planet earth, you should spend some time and effort to delete them - free of charge. Maybe it is possible to build a *One Click Delete Everything* tool using this approach, and maybe it is even user-friendly. I know, the one above is not user friendly, but hopefully this readme is, and hopefully it enables your daughter/neighbor/friend to assist with deleting stuff from the Internet that you don't want to see there anymore. In my opinion, everyone should have the right and the opportunity to delete their own content from the Internet without problems, without barriers, and without paying money; regardless of their origin.

