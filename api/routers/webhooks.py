from fastapi import APIRouter, Request, HTTPException, status, Depends
from svix.webhooks import Webhook, WebhookVerificationError
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from database import get_session
from models import User
from config import settings

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

CLERK_WEBHOOK_SECRET = settings.CLERK_WEBHOOK_SECRET
STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET

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

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    # 1. Get the raw bytes and the Stripe signature header
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        # 2. CPU-Math: Stripe's SDK verifies the cryptographic signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        print("Invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        print("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 3. Process the Payment Event
    if event['type'] == 'checkout.session.completed':
        session_data = event.data.object
        
        # Access the property directly via dot notation
        user_uuid_str = session_data.client_reference_id

        if user_uuid_str:
            print(f"Payment received for user: {user_uuid_str}. Adding credits...")
            
            # 4. The Database Ledger Update
            import uuid
            user_uuid = uuid.UUID(user_uuid_str)
            
            # Fetch the user
            from sqlalchemy import select
            stmt = select(User).where(User.id == user_uuid)
            result = await session.execute(stmt)
            db_user = result.scalars().first()
            
            if db_user:
                # Add the 10 credits!
                db_user.credits_remaining += 1000
                session.add(db_user)
                
                try:
                    await session.commit()
                    print(f"Success: Added 10 credits to {db_user.email}")
                except Exception as e:
                    await session.rollback()
                    print(f"Failed to update ledger: {e}")

    # Always return a 200 OK so Stripe knows you received the event
    return {"status": "success"}