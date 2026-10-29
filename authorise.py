"""One-time Google authorisation for the agent.

Run on the LAPTOP (not in the container): it opens a browser, you approve, and
it writes .google-token.json next to the credentials. That token file is then
copied into the container, where it refreshes itself from then on.

    python authorise.py

Google will warn "Google hasn't verified this app" - that is expected for an
app in testing mode. Advanced -> Go to dehrenagent (unsafe).
"""
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

CREDS = os.path.expanduser("~/.agent-google.json")
TOKEN = os.path.expanduser("~/.agent-google-token.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

if not os.path.exists(CREDS):
    sys.exit(f"Credentials not found at {CREDS}")

flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent")

with open(TOKEN, "w", encoding="utf-8") as fh:
    fh.write(creds.to_json())

print(f"\nAuthorised. Token written to {TOKEN}")
print("Scopes granted:")
for s in creds.scopes or []:
    print(f"  {s}")
