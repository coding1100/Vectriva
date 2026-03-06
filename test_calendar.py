import sys
import os
from pathlib import Path

# Add src to python path so we can import modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from google.oauth2 import service_account
from googleapiclient.discovery import build

creds_path = "creds.json"
try:
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"]
    )
    service = build("calendar", "v3", credentials=creds)
    calendars = service.calendarList().list().execute()
    items = calendars.get("items", [])
    
    # Let's also check primary calendar explicitly just in case it's accessible but not in list
    try:
        primary = service.calendars().get(calendarId='primary').execute()
        print(f"Primary calendar check: {primary.get('summary')}")
    except Exception as pe:
        print(f"Primary check failed: {pe}")
    
        # Try to explicitly get the user's calendar if it doesn't show in the list
        try:
            user_cal = service.calendars().get(calendarId='awaisthewolf603@gmail.com').execute()
            print(f"Explicit fetch success! Found: {user_cal.get('summary')}")
            items.append(user_cal)
        except Exception as e:
            print("FAILED: No calendars are shared with this service account!")
            print(f"Error: {e}")
            
    if items:
        print(f"SUCCESS! Found {len(items)} calendar(s):")
        for cal in items:
            print(f"  - Name: {cal.get('summary')}")
            print(f"    ID: {cal.get('id')}")
            
except Exception as e:
    import traceback
    traceback.print_exc()
