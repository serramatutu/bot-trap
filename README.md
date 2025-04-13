# bot-trap

Static file server that detects bad crawlers.


## Why

I got tired of OpenAI, Meta and other companies crawling my personal blog constantly. They don't respect `robots.txt` and they change their `User-Agent` if you attempt to block them.


## Installation

```
pip install bot-trap
```


## How it works

`bot-trap` is a simple static file HTTP server that will also serve a special bad path (`/bot-trap` by default). It will add this bad path to your `robots.txt`, so it should always be ignored by any respecful crawlers, and no human should reach it either.

Anyone who accesses that path will get their IP and user agent logged and added to a block list. You can choose whether any other requests by blocked requests will be hard-blocked (TLS connection termination) or soft-blocked (response with bullshit content).

I recommend you also add an un-clickable link (invisible `<a>`) to your served HTML to bait naughty bots into trying to access that.
