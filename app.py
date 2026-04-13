"""
Web app for Email Automation - Gmail OAuth, Dashboard, and Workflow activation.
"""
import os
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

app = FastAPI(
    title="Email Automation",
    description="AI-powered Gmail automation - draft replies and label emails",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def get_oauth_flow():
    """Build OAuth flow with web redirect_uri."""
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
    return Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


# ----- Pages -----

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page - Connect Gmail or go to dashboard if already logged in."""
    logged_in = TOKEN_PATH.exists()
    return templates.TemplateResponse("index.html", {"request": request, "logged_in": logged_in})


@app.get("/auth/gmail")
async def auth_gmail():
    """Start Gmail OAuth - redirect to Google."""
    if not CREDENTIALS_PATH.exists():
        raise HTTPException(status_code=500, detail="credentials.json not found. Add it from Google Cloud Console.")
    flow = get_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return RedirectResponse(url=authorization_url)


@app.get("/auth/callback")
async def auth_callback(code: str = None, error: str = None):
    """OAuth callback - exchange code for tokens, save, redirect to dashboard."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
    }
    with open(TOKEN_PATH, "w") as f:
        import json
        json.dump(token_data, f, indent=2)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard - email view and Activate button."""
    logged_in = TOKEN_PATH.exists()
    return templates.TemplateResponse("dashboard.html", {"request": request, "logged_in": logged_in})


# ----- API -----

@app.get("/api/auth/status")
async def auth_status():
    """Check if user is logged in (token exists)."""
    return {"logged_in": TOKEN_PATH.exists()}


@app.get("/api/emails")
async def list_emails():
    """List recent unanswered emails (optional preview)."""
    if not TOKEN_PATH.exists():
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        from src.tools.GmailTools import GmailToolsClass
        gmail = GmailToolsClass()
        emails = gmail.fetch_unanswered_emails(max_results=10)
        return {
            "emails": [
                {
                    "subject": e.get("subject"),
                    "sender": e.get("sender"),
                    "id": e.get("id"),
                    "body_preview": (e.get("body") or "")[:120] + ("…" if len(e.get("body") or "") > 120 else ""),
                }
                for e in emails
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run-workflow")
async def run_workflow():
    """Run the email automation workflow (same logic as main.py)."""
    if not TOKEN_PATH.exists():
        raise HTTPException(status_code=401, detail="Not logged in. Connect Gmail first.")
    try:
        from src.graph import Workflow
        load_dotenv()
        config = {"recursion_limit": 100}
        workflow = Workflow()
        initial_state = {
            "emails": [],
            "current_email": {
                "id": "", "threadId": "", "messageId": "", "references": "",
                "sender": "", "subject": "", "body": "",
            },
            "email_category": "",
            "generated_email": "",
            "rag_queries": [],
            "retrieved_documents": "",
            "writer_messages": [],
            "sendable": False,
            "trials": 0,
        }
        steps = []
        for output in workflow.app.stream(initial_state, config):
            for key in output:
                steps.append(key)
        return {"success": True, "steps": steps}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
