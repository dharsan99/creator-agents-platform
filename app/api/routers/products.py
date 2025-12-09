"""Products API router."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CreatorIdDep, SessionDep
from app.domain.products.service import ProductService
from app.domain.schemas import ProductCreate, ProductResponse
from app.domain.types import ProductType

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    creator_id: CreatorIdDep,
    session: SessionDep,
    product_data: ProductCreate,
) -> ProductResponse:
    """Create a new product."""
    service = ProductService(session)
    product = service.create_product(creator_id, product_data)
    return ProductResponse.model_validate(product)


@router.get("", response_model=list[ProductResponse])
def list_products(
    creator_id: CreatorIdDep,
    session: SessionDep,
    product_type: Optional[ProductType] = Query(None),
) -> list[ProductResponse]:
    """List all products for the creator."""
    service = ProductService(session)
    products = service.list_products(creator_id, product_type)
    return [ProductResponse.model_validate(product) for product in products]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    creator_id: CreatorIdDep,
    session: SessionDep,
    product_id: UUID,
) -> ProductResponse:
    """Get a specific product."""
    service = ProductService(session)
    product = service.get_product(product_id)

    if not product or product.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    creator_id: CreatorIdDep,
    session: SessionDep,
    product_id: UUID,
    updates: dict,
) -> ProductResponse:
    """Update a product."""
    service = ProductService(session)
    product = service.get_product(product_id)

    if not product or product.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    product = service.update_product(product_id, **updates)
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    creator_id: CreatorIdDep,
    session: SessionDep,
    product_id: UUID,
) -> None:
    """Delete a product."""
    service = ProductService(session)
    product = service.get_product(product_id)

    if not product or product.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    service.delete_product(product_id)
