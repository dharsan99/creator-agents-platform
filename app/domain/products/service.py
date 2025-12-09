"""Product domain service."""
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.infra.db.models import Product
from app.domain.schemas import ProductCreate
from app.domain.types import ProductType


class ProductService:
    """Service for managing creator products."""

    def __init__(self, session: Session):
        self.session = session

    def create_product(self, creator_id: UUID, data: ProductCreate) -> Product:
        """Create a new product."""
        product = Product(
            creator_id=creator_id,
            name=data.name,
            type=data.type.value,
            price_cents=data.price_cents,
            currency=data.currency,
            meta=data.meta,
        )
        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def get_product(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID."""
        return self.session.get(Product, product_id)

    def list_products(
        self, creator_id: UUID, product_type: Optional[ProductType] = None
    ) -> list[Product]:
        """List products for a creator, optionally filtered by type."""
        statement = select(Product).where(Product.creator_id == creator_id)

        if product_type:
            statement = statement.where(Product.type == product_type.value)

        return list(self.session.exec(statement).all())

    def update_product(self, product_id: UUID, **kwargs) -> Product:
        """Update product attributes."""
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        for key, value in kwargs.items():
            if hasattr(product, key) and value is not None:
                setattr(product, key, value)

        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def delete_product(self, product_id: UUID) -> bool:
        """Delete a product."""
        product = self.get_product(product_id)
        if not product:
            return False

        self.session.delete(product)
        self.session.commit()
        return True
