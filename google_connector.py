"""Gmail and Calendar access for the agent, through Google's API.

The alternative - driving Gmail in Firefox - costs a screenshot per step and
takes minutes. This returns structured data in one call, so "what's in my
inbox" is a second rather than fifteen screenshots.

Authorisation happens once, interactively, via authorise.py. After that the
stored token refreshes itself.
"""
import base64
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CREDS_FILE = os.environ.get("GOOGLE_CREDS", "/home/computeruse/.google-creds.json")
TOKEN_FILE = os.environ.get("GOOGLE_TOKEN", "/home/computeruse/.google-token.json")

# The account's own "send mail as" display name is whatever Gmail has stored
# (it was "Dez Hun"), and the API cannot change that setting. Setting the
# From header per message overrides it for anything the agent sends.
FROM_NAME = os.environ.get("GOOGLE_FROM_NAME", "Dehren Hunter")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",   # read, label, archive, trash
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

_services: dict = {}


def _service(name: str, version: str):
    """Build (and cache) an authorised API client."""
    if name in _services:
        return _services[name]
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "Not authorised yet - run authorise.py once to grant access."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    svc = build(name, version, credentials=creds, cache_discovery=False)
    _services[name] = svc
    return svc


# ---------------------------------------------------------------- Gmail

def list_email(query: str = "in:inbox", limit: int = 15) -> str:
    """List messages matching a Gmail search query (same syntax as the app)."""
    svc = _service("gmail", "v1")
    res = svc.users().messages().list(
        userId="me", q=query, maxResults=min(limit, 50)
    ).execute()
    ids = [m["id"] for m in res.get("messages", [])]
    if not ids:
        return f"No messages match: {query}"

    lines = []
    for mid in ids:
        m = svc.users().messages().get(
            userId="me", id=mid, format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        h = {x["name"]: x["value"] for x in m["payload"].get("headers", [])}
        labels = m.get("labelIds", [])
        flag = "UNREAD " if "UNREAD" in labels else ""
        lines.append(
            f"[{mid}] {flag}{h.get('From', '?')[:45]}\n"
            f"    {h.get('Subject', '(no subject)')[:70]}\n"
            f"    {h.get('Date', '')[:31]} | {m.get('snippet', '')[:90]}"
        )
    return f"{len(lines)} message(s) matching '{query}':\n\n" + "\n\n".join(lines)


def read_email(message_id: str) -> str:
    """Full text of one message."""
    svc = _service("gmail", "v1")
    m = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    h = {x["name"]: x["value"] for x in m["payload"].get("headers", [])}

    def extract(part) -> str:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                "utf-8", "replace")
        for sub in part.get("parts", []) or []:
            found = extract(sub)
            if found:
                return found
        return ""

    body = extract(m["payload"]) or m.get("snippet", "")
    return (f"From: {h.get('From')}\nTo: {h.get('To')}\n"
            f"Date: {h.get('Date')}\nSubject: {h.get('Subject')}\n"
            f"Labels: {', '.join(m.get('labelIds', []))}\n\n{body[:4000]}")


def send_email(to: str, subject: str, body: str) -> str:
    """Send a message. Gated by the confirmation rule in the agent's prompt.

    The subject and body checks are deliberate: an agent that skips them
    produces mail that reads like a system notification, which is worse than
    not sending at all when it goes to a customer.
    """
    if not subject.strip():
        raise ValueError("Subject is empty - every email needs one.")
    if len(body.strip()) < 20:
        raise ValueError(
            "Body is too short to be a real email. Include a greeting, the "
            "reason for writing, and a sign-off."
        )
    svc = _service("gmail", "v1")
    address = svc.users().getProfile(userId="me").execute()["emailAddress"]

    msg = EmailMessage()
    msg["From"] = f"{FROM_NAME} <{address}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Sent to {to} (id {sent['id']})"


def modify_email(message_id: str, add: list[str] | None = None,
                 remove: list[str] | None = None) -> str:
    """Add or remove labels. Archive = remove INBOX. Read = remove UNREAD."""
    svc = _service("gmail", "v1")
    svc.users().messages().modify(
        userId="me", id=message_id,
        body={"addLabelIds": add or [], "removeLabelIds": remove or []},
    ).execute()
    bits = []
    if add:
        bits.append(f"+{','.join(add)}")
    if remove:
        bits.append(f"-{','.join(remove)}")
    return f"{message_id}: {' '.join(bits)}"


def list_labels() -> str:
    svc = _service("gmail", "v1")
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    return "\n".join(f"{l['id']}  {l['name']}" for l in labels)


def create_label(name: str) -> str:
    svc = _service("gmail", "v1")
    made = svc.users().labels().create(userId="me", body={"name": name}).execute()
    return f"Created label '{name}' (id {made['id']})"


# ------------------------------------------------------------- Calendar

def list_events(days: int = 7, calendar_id: str = "primary") -> str:
    svc = _service("calendar", "v3")
    now = datetime.now(timezone.utc)
    res = svc.events().list(
        calendarId=calendar_id,
        timeMin=now.isoformat(),
        timeMax=(now + timedelta(days=days)).isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=50,
    ).execute()
    events = res.get("items", [])
    if not events:
        return f"Nothing in the next {days} days."
    lines = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        # The id is printed WHOLE. This listing is the only place the agent
        # sees one, so a truncated id here means delete_event gets a broken
        # id and Google answers 404 - the event silently survives. Calendar
        # ids are ~26 characters, and a recurring instance is longer still.
        lines.append(f"[{e['id']}] {start[:16]}  {e.get('summary', '(no title)')}"
                     + (f"  @ {e['location'][:40]}" if e.get("location") else ""))
    return f"{len(events)} event(s) in the next {days} days:\n\n" + "\n".join(lines)


def create_event(summary: str, start: str, end: str,
                 description: str = "", location: str = "") -> str:
    """Create an event. start/end are ISO 8601, e.g. 2026-10-30T14:00:00."""
    svc = _service("calendar", "v3")
    made = svc.events().insert(calendarId="primary", body={
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start, "timeZone": "Europe/London"},
        "end": {"dateTime": end, "timeZone": "Europe/London"},
    }).execute()
    return f"Created '{summary}' at {start} ({made['id']})"


def delete_event(event_id: str) -> str:
    svc = _service("calendar", "v3")
    svc.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"Deleted event {event_id}"
