# Telegram Computer-Use Agent

A personal AI agent you command from Telegram. It works on its own Linux
desktop — opening a browser, reading pages, filling forms — and replies with
the answer and a screenshot of what it did. It also reads and writes Gmail and
Google Calendar directly through their APIs.

Built on Anthropic's computer-use demo container, driving `sampling_loop`
directly rather than the bundled Streamlit UI.

```
You (Telegram) → bridge.py → Claude → virtual desktop (browser, shell)
                           ↘ Gmail / Calendar API
          answer + screenshot ←
```

## Why it exists

A computer-use agent is only useful if you can reach it from where you are.
The demo container ships a web UI that needs a laptop open in front of you.
This replaces that with a phone.

## What it does

- **Browses and acts.** "Find three cleaning companies in Hendon that publish
  their prices" — it searches, opens each site, reads them, reports back.
- **Email and calendar, without a browser.** Gmail through the API is one call
  and a fraction of a penny; the same job by driving Gmail in Firefox is ~15
  screenshots and several minutes.
- **Stops before anything irreversible.** Sending, paying, booking, deleting
  and submitting all pause for confirmation.
- **Remembers the conversation**, so "archive them" knows what *them* is.
- **Takes a role.** A markdown file in `roles/` defines the job — competitor
  monitor, personal assistant — without touching the code.

## Design decisions worth explaining

**Role files load in front of the safety rules, never instead of them.** A
role can narrow what the agent does; it cannot widen it. The system prompt is
assembled as `role + tool docs + safety rules`, in that order, so the rules
have the last word.

**Screenshots are stripped from conversation history.** They are both the
expensive part of each request and useless to a follow-up question — the text
of what happened is what "archive them" actually needs. Keeping the last six
exchanges as text costs almost nothing.

**Email content is data, never instruction.** An agent that browses the web
and can send email is a prompt-injection target: a page or a message can carry
text aimed at the agent rather than the reader. The prompt states this
explicitly, and sending is gated behind a human confirmation regardless.

**Guards live in code as well as the prompt.** `send_email` raises on an empty
subject or a stub body. A prompt can be talked past; a `ValueError` cannot.

**Model and tool version must be a supported pair.** The API rejects a
mismatch outright rather than falling back, so the defaults are pinned and the
tested combinations are documented in `bridge.py`.

**Pleasantries do not start tasks.** "Thanks" used to spin up the whole agent
loop — screenshots, API calls, real money — to say you're welcome. Social
messages get an emoji; confirmations like "yes" only pass through when a
conversation is actually in progress.

## Running it

Needs Docker, an Anthropic API key, and a Telegram bot token.

```bash
docker run -d --name pc-dehren \
  --restart unless-stopped --memory=4g \
  --env-file ~/.agent.env \
  -p 127.0.0.1:8080:8080 \
  ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest
```

Then `start-bridge.ps1` copies `bridge.py`, the connector and the chosen role
into the container and starts the bridge.

Credentials are read from files outside the repo and passed in via
`--env-file`, never on a command line where they would land in shell history.

### Gmail and Calendar (optional)

Needs a Google Cloud project with the Gmail and Calendar APIs enabled, an
OAuth client of type **Desktop app**, and your own account added as a test
user. `authorise.py` runs once on the host to grant access; the resulting
token is copied into the container and refreshes itself from then on.

## Commands

| | |
|---|---|
| any message | run it as a task |
| `/v <task>` | show each step as it happens |
| `/new` | clear the conversation |
| `/role` | show the loaded role |

## Files

| | |
|---|---|
| `bridge.py` | the bridge: polls Telegram, runs the agent loop, reports back |
| `google_connector.py` | Gmail and Calendar through their APIs |
| `authorise.py` | one-time Google OAuth, run on the host |
| `roles/*.md` | what the agent's job is |
| `start-bridge.ps1` | deploy and restart |
| `speed-patch.sh` | cuts the container's hardcoded 2s screenshot delay |

## Known limits

- **Runs on a laptop**, so the bot is silent when the lid is shut. Designed to
  move to a VPS; nothing in it assumes otherwise.
- **The agent does not know where it is.** Maps geolocates the container by IP,
  so directions need an explicit origin.
- **Cost scales with steps, not tasks.** A lookup is pennies; open-ended
  research across several sites is pounds. Narrow instructions are cheaper
  instructions.
- **One task at a time**, by design — concurrent tasks on one desktop would
  fight over the mouse.
