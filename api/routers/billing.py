import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user
from database import get_session
from models import User
from config import settings

router = APIRouter(prefix="/billing", tags=["Billing"])

# Initialize Stripe with your secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

@router.post("/create-checkout-session")
async def create_checkout_session(
    current_user: User = Depends(get_current_user)
):
    try:
        print(current_user.id)
        # We tell Stripe to build a hosted payment page
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": settings.STRIPE_PRICE_ID, # The ID you got from the dashboard
                    "quantity": 1,
                },
            ],
            mode="payment", # 'payment' for one-time, 'subscription' for recurring
            
            # THE MAGIC LINK: We stamp the PostgreSQL user's UUID onto the Stripe session
            client_reference_id=str(current_user.id),
            
            # Where to send the user after they pay (or cancel)
            success_url="http://localhost:3000/?payment=success",
            cancel_url="http://localhost:3000/?payment=cancelled",
        )
        
        # Return the secure Stripe URL to the Next.js frontend
        return {"checkout_url": session.url}
        
    except Exception as e:
        print(f"Stripe Error: {e}")
        raise HTTPException(status_code=500, detail="Could not create checkout session")