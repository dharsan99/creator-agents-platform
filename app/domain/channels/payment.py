"""Payment channel implementation."""
import logging
from typing import Any, Dict
from uuid import UUID
from sqlmodel import Session

from app.domain.channels.base import ChannelTool
from app.infra.db.models import Product

logger = logging.getLogger(__name__)


class PaymentChannel(ChannelTool):
    """Payment channel for generating payment links."""

    def __init__(self, session: Session, base_url: str = "https://topmate.io"):
        self.session = session
        self.base_url = base_url

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate payment payload."""
        required_fields = ["product_id"]
        return all(field in payload for field in required_fields)

    def execute(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate payment link for a product.

        In v1, this generates a simple payment link.
        In production, this would integrate with Stripe, Razorpay, etc.
        """
        if not self.validate_payload(payload):
            raise ValueError("Invalid payment payload")

        product_id = payload["product_id"]
        custom_amount = payload.get("amount_cents")  # Optional custom amount

        # Get product details
        product = self.session.get(Product, product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        if product.creator_id != creator_id:
            raise ValueError("Product does not belong to creator")

        amount_cents = custom_amount or product.price_cents

        # Generate payment link
        # In v1, this is a simple URL format
        # TODO: Integrate with actual payment provider
        payment_link = (
            f"{self.base_url}/pay/"
            f"{creator_id}/{product_id}/"
            f"{consumer_id}?amount={amount_cents}"
        )

        logger.info(
            f"Generated payment link for product {product_id}, "
            f"creator {creator_id}, consumer {consumer_id}"
        )

        return {
            "success": True,
            "payment_link": payment_link,
            "product_id": str(product_id),
            "product_name": product.name,
            "amount_cents": amount_cents,
            "currency": product.currency,
        }
