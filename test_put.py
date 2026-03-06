import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vectriva.core.database import AsyncSessionLocal
from vectriva.models.database import Integration
from sqlalchemy import select
from vectriva.services.calendar_service import _get_service_account_credentials
import uuid

async def test_put():
    tenant_id = "a1e48fee-4432-474c-b60b-e6986497381d"
    calendar_id = "awaisthewolf603@gmail.com"
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
            )
        )
        integration = result.scalar_one_or_none()

        if not integration:
            sa_creds = _get_service_account_credentials()
            if not sa_creds:
                print("FAILED: SA Creds is None!")
                return
                
            integration = Integration(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                provider="google_calendar",
                calendar_id=calendar_id,
                encrypted_access_token="service_account",
            )
            db.add(integration)
        else:
            integration.calendar_id = calendar_id
            
        await db.commit()
        print(f"SUCCESS! Set calendar_id to {calendar_id}")

asyncio.run(test_put())
