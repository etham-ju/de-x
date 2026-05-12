# de-x.py

**Language:** [English](README.md) · [한국어](README.ko.md)

### 이 버전에 대하여
원본이 공개된 지 3년이 지나면서 많은 부분이 바뀌었습니다. 이 스크립트는 현재 X의 rate limiting, 인증 요구사항, 그리고 엔드포인트 변경사항에 맞게 업데이트되어 있습니다.

**이 스크립트를 사용하면 본인의 모든 트윗, 리트윗, 답글을 한 번에 삭제할 수 있고, 좋아요도 같은 실행으로 제거할 수 있습니다.**

일론이 Twitter API 접근을 제한한 이후, 같은 일을 해주던 많은 도구들이 개발자 계정 등록 없이는 동작하지 않게 되었습니다.

하지만 이 작은 스크립트는 그런 제한된 API에 의존하지 않습니다. 개발자 계정을 등록할 필요도, API 사용료를 낼 필요도 없습니다. 사용자가 직접 해야 할 몇 가지 수동 단계만 있고, 아래에 자세히 설명되어 있습니다.

## 준비

1. X/Twitter에서 본인 데이터의 아카이브를 요청합니다. 보통 며칠 후에 다운로드가 가능해집니다 (저는 2일 정도 걸렸습니다). 준비가 되면 Twitter 앱이나 이메일로 알림이 옵니다. ![X에서 Twitter 아카이브 요청](doc/archive.png)
2. 아카이브가 다운로드되면 ZIP 파일을 풀어주세요. 두 파일이 필요합니다: `tweets.js` (모든 트윗/답글/리트윗과 tweet-ID), 그리고 `like.js` (좋아요를 누른 모든 트윗과 tweet-ID).
3. 이 파이썬 스크립트가 아카이브의 tweet-ID로 게시물을 삭제하려면 세션 정보도 함께 넘겨야 합니다. 그렇지 않으면 인증이 되지 않습니다. 현재 X의 anti-abuse 검사는 실제 브라우저가 보내는 헤더 중 하나라도 빠지면 요청을 거부하기 때문에, 헤더 3-4개만 복사하는 게 아니라 **전체 헤더 세트**를 그대로 캡처해야 합니다. 가장 쉬운 방법:
   1. Edge/Chrome: 평소처럼 X에 로그인한 뒤 DevTools를 엽니다 (`Ctrl-Shift-i` / `Cmd-Opt-i`). *Network* 탭으로 전환하고, 트윗 하나를 실제로 삭제(또는 좋아요 하나 취소)해서 `/i/api/graphql/…/DeleteTweet` (또는 `/UnfavoriteTweet`) 요청이 네트워크 패널에 나타나게 합니다. 그 요청에서 오른쪽 클릭 → **Copy → Copy as cURL**을 누르세요. 이렇게 하면 X가 현재 요구하는 헤더들을 포함해 브라우저가 실제로 보낸 모든 헤더가 한 번에 복사됩니다 (`x-client-transaction-id`, `x-twitter-auth-type`, `x-twitter-active-user`, `x-csrf-token`, `x-twitter-client-language`, `user-agent`, `referer`, `origin`, `accept`, `accept-language`, `cookie`, `authorization`, 그리고 `sec-*` 헤더들). ![twitter.com에서 세션 헤더 복사 & 붙여넣기](doc/session.png)
   2. Firefox: *Network → Copy → Copy as cURL* 로 같은 방식.
   3. burp suite: 로그인 상태의 X 세션을 기록해서 실제 `DeleteTweet` 호출의 클라이언트 요청 헤더를 복사.
4. cURL에 있는 모든 `-H 'key: value'` 줄을 `request-headers.txt`에 붙여넣습니다. `-H '...'` 껍데기는 떼고 한 줄에 `key: value` 형식으로 하나씩 넣으면 됩니다. 동작하는 파일은 대략 이런 모양입니다:
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
x-client-transaction-id: [base64 문자열 — 아래 주의사항 참고]
x-csrf-token: [ct0 쿠키와 같은 값]
x-twitter-active-user: yes
x-twitter-auth-type: OAuth2Session
x-twitter-client-language: en
```

> **중요:** `Authorization`, `X-Csrf-Token`, `Cookie` 세 줄만 있는 최소 파일은 동작하지 않습니다 — 모든 삭제 호출에 대해 X가 `404 Not Found` 와 빈 body 로 응답합니다. `x-client-transaction-id`, `x-twitter-auth-type`, `x-twitter-active-user`, `referer`, `user-agent` 모두 필수입니다.

> **`x-client-transaction-id` 주의사항:** 브라우저는 요청마다 이 값을 새로 계산하는 반면, 이 스크립트는 캡처된 하나의 값을 계속 재사용합니다. 보통 수백 건까지는 잘 동작하다가 그 이후 X가 `404` 로 거부하기 시작합니다. 그렇게 되면 브라우저에서 `DeleteTweet` 요청을 한 번 더 잡아서 `request-headers.txt` 의 그 한 줄만 새 값으로 교체하면 됩니다.

## 실행

트위터 아카이브를 받고 현재 세션용 request-header 파일을 만들었다면 (위 설명 참고), 이렇게 실행합니다:

```
python3 de-x.py tweets.js like.js request-headers.txt
```

스크립트는 세 단계로 순서대로 실행됩니다:

1. **`DeleteTweet`** — `tweets.js` 에 있는 본인 원본 트윗과 답글.
2. **`DeleteRetweet`** — `tweets.js` 에 있는 리트윗. 이 엔드포인트는 *원본* 트윗의 id를 요구하는데, 아카이브는 media 가 첨부된 리트윗에 대해서만 원본 id 를 가지고 있습니다. 따라서 media 없는 RT 는 스킵되며 시작 시 요약에 카운트가 표시됩니다.
3. **`UnfavoriteTweet`** — `like.js` 의 모든 항목.

요청이 `404 Not Found` 와 빈 body 로 실패하기 시작하면, 위 준비 섹션의 `x-client-transaction-id` 주의사항을 참고하세요 — X가 재사용된 헤더 때문에 요청을 거부하는 상황입니다.

### 단건 디버깅

전체 실행을 시작하기 전에 트윗 하나만 먼저 확인해볼 수 있는 헬퍼 스크립트가 포함되어 있습니다:

```
python3 test-one.py <tweet_id> request-headers.txt
```

실제로 전송되는 헤더, 상태 코드, rate-limit 응답 헤더, 그리고 응답 body 를 모두 출력해서 현재 세션이 정상적으로 인증되는지 확인할 수 있습니다.

## Rate limiting

X는 `DeleteTweet`, `DeleteRetweet`, `UnfavoriteTweet` 의 rate limit 을 각각 독립적으로 관리합니다 (각 엔드포인트마다 윈도우당 약 200 요청). 스크립트는 이 한계를 넘지 않도록 다음과 같이 동작합니다:

- 매 응답의 `x-rate-limit-remaining` / `x-rate-limit-reset` 헤더를 읽어서 남은 예산을 남은 윈도우 시간에 균등하게 분배합니다.
- 요청 간 **최소 3초** 간격을 강제합니다. 커뮤니티에서 검증된 안전한 기본 속도입니다 ([이 gist 스레드](https://gist.github.com/aymericbeaumet/d1d6799a1b765c3c8bc0b675b1a1547d?permalink_comment_id=4694790#file-delete-likes-from-twitter-md) 참고).
- **50 요청마다 30초 휴식**을 취합니다.
- 그럼에도 429 가 발생하면 서버가 알려준 reset 시간까지 기다리거나 (또는 지수 백오프 60초 → 최대 15분), 같은 ID 로 재시도하므로 누락 없이 진행됩니다.

즉 긴 작업은 느리지만 꾸준히 진행됩니다 — 트윗이나 좋아요가 수천 건이면 분 단위가 아닌 시간 단위가 걸린다고 예상하세요.

## 배경

tweet-id 를 알고 있으면 그 id 로 API를 호출해 해당 트윗을 삭제할 수 있고, 여기엔 별도의 rate limit 이 없습니다. 그래서 가장 먼저 해야 하는 일이자 가장 중요한 일은 삭제 대상인 모든 트윗의 id 목록을 확보하는 것입니다. Twitter API 로도 할 수 있지만 이 쪽은 제한되어 있고 비용이 듭니다. 비용을 낸다 하더라도 제약이 여럿 있어서 본인 트윗 전체 목록을 가져오지 못할 수도 있습니다.

그래서 본인이 지금까지 올린 모든 트윗의 아카이브를 요청하는 게 훨씬 쉽습니다. 이 데이터셋은 우리가 찾던 tweet-id 를 포함한 모든 메타데이터를 담고 있습니다. 무료이고, 완전하며, 기계가 읽을 수 있습니다.

아카이브에는 `tweets.js` 라는 파일이 있고, 이는 기본적으로 본인의 모든 트윗이 들어있는 JSON 인코딩 자료구조입니다. 그리고 동일한 구조의 `like.js` 에는 좋아요를 누른 트윗이 들어있습니다.

X의 `DeleteTweet`, `DeleteRetweet`, `UnfavoriteTweet` GraphQL 엔드포인트는 유료 개발자 프로그램 뒤에 제한되어 있지 않고, 요청이 브라우저가 보내는 것과 동일한 헤더 세트를 갖추기만 하면 일반 로그인 세션에서 호출할 수 있습니다. 이 방식으로 3,000 건 가량을 30분 내외에 삭제할 수 있습니다 (*) — 다만 위에 설명한 보수적인 pacing 때문에 대용량 아카이브는 더 걸립니다.

### 리트윗 주의사항

`DeleteRetweet` 은 내 리트윗의 id 가 아니라 **원본 트윗의 id** 를 받습니다. Twitter 아카이브는 `extended_entities.media[].source_status_id` 에만 원본 id 를 담고 있어서, 미디어가 없는 일반 텍스트 RT 는 아카이브만으로는 취소할 수 없습니다. 해당 항목들은 시작 시 카운트되어 스킵됩니다. 이 건들까지 정리하고 싶다면 별도 단계에서 웹 API 로 retweet id → source id 를 먼저 해석하는 과정이 필요합니다.

## 결론

*One Click Delete Everything* 도구는 존재하지 않고 앞으로도 없을 겁니다. 이는 Twitter 가 본인 데이터를 직접 통제할 수 있는 API 사용을 엄청나게 제한하기 때문입니다. 당연히 그들은 당신의 데이터를 가지고 있고 싶어합니다. 영원히. 하지만 지구상 모든 기계가 지구온난화로 끝장날 때까지 Twitter 에 본인 데이터가 보관되기를 원하지 않는다면, 시간과 노력을 조금 들여 직접 지우는 수밖에 없습니다 — 무료로요. 어쩌면 이 접근으로 *One Click Delete Everything* 같은 도구를 만들 수도 있고, 심지어 사용자 친화적으로도 만들 수 있을지 모릅니다. 위의 것은 사용자 친화적이지 않지만, 이 README 는 부디 친절해서 당신의 딸/이웃/친구가 인터넷에서 지우고 싶은 것들을 지울 수 있게 돕기를 바랍니다. 제 생각엔, 출신이 어떠하든 누구나 인터넷에서 본인의 콘텐츠를 문제 없이, 장벽 없이, 돈을 내지 않고 삭제할 수 있는 권리와 기회가 있어야 합니다.
