import os
import stripe
from fastapi import HTTPException

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
YOUR_DOMAIN = os.getenv("YOUR_DOMAIN", "http://localhost:8000")

# Define your pricing plans
PRICES = {
    "starter": "price_123456789", # Replace with actual Stripe Price ID
    "pro": "price_987654321"     # Replace with actual Stripe Price ID
}

def create_checkout_session(user_email: str, plan: str = "starter"):
    """Create a Stripe Checkout Session"""
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': PRICES[plan],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=YOUR_DOMAIN + "/dashboard?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=YOUR_DOMAIN + "/pricing",
            customer_email=user_email,
            metadata={'user_email': user_email}
        )
        return session.url
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def handle_webhook(payload: bytes, sig_header: str):
    """Verify and handle Stripe Webhooks"""
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_email = session['metadata']['user_email']
        # TODO: Update user subscription status in DB to 'active'
        print(f"Payment successful for {user_email}")
        
    elif event['type'] == 'customer.subscription.deleted':
        # TODO: Downgrade user to 'free' plan
        pass

    return {"status": "success"}