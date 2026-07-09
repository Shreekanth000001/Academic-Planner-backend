from fastapi import APIRouter, Request, HTTPException, status, Depends
from svix.webhooks import Webhook, WebhookVerificationError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import User
from config import settings

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

CLERK_WEBHOOK_SECRET = settings.CLERK_WEBHOOK_SECRET

@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    payload = await request.body()

    headers_dict = dict(request.headers)

    svix_id = headers_dict.get("svix-id")
    svix_timestamp = headers_dict.get("svix-timestamp")
    svix_signature = headers_dict.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(status_code=400, detail="Missing Svix headers")

    try:
        wh = Webhook(CLERK_WEBHOOK_SECRET)
        event = wh.verify(payload, headers_dict)

    except WebhookVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event.get("type")
    data = event.get("data", {})

    if event_type == "user.created":
        clerk_id = data.get("id")
        
        email_addresses = data.get("email_addresses", [])
        email = email_addresses[0].get("email_address") if email_addresses else None
        
        if clerk_id and email:

            new_user = User(
                clerk_id=clerk_id,
                email=email
            )
            
            session.add(new_user)
            try:
                await session.commit()
                print(f"Success: Synced new Clerk user {email} to PostgreSQL.")
            except Exception as e:
                await session.rollback()
                print(f"Database error syncing user: {e}")
                raise HTTPException(status_code=500, detail="Database insertion failed")

    return {"status": "success"}