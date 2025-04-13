# bot-trap

Static file server that detects and blocks bad crawlers.


## Why

I got tired of OpenAI, Meta and other companies crawling my personal blog constantly. They don't respect `robots.txt` and they change their `User-Agent` if you attempt to block them.


## How it works

`bot-trap` is a simple static file HTTP server that will also serve a special bad path (`/bot-trap` by default). It will add this bad path to your `robots.txt`, so it should always be ignored by any respecful crawlers, and no human should reach it either.

Anyone who accesses that path will get their IP and user agent logged and added to a block list. All subsequent requests from that IP will be blocked.

I recommend you also add an un-clickable link (invisible `<a>`) to your served HTML to bait naughty bots into trying to access that.


## Example

You can try it out yourself.

1. Run `uv run python main.py example/bot-trap.json` to start a server on `0.0.0.0:8080`. 
2. Make some requests to it and verify that it responds with the files under `example/public/`.
3. Request `/robots.txt` and verify that it contains `Disallow: /bot-trap` for all user agents.
4. Request `/bot-trap`. You'll see a log saying that your IP has been blocked. You can check `example/blocklist.txt` to verify your IP is there.
5. Make the same requests as in step 2. The content should be replaced by whatever is in `example/bullshit.txt`.
