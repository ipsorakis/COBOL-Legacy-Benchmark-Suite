import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.services.portfolio_inquiry import PositionNotFoundError, inquire_portfolio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inquiry", tags=["inquiry"])

RESP_NORMAL = 0
RESP_NOTFND = 13


class PositionResponse(BaseModel):
    """One INVESTMENT_POSITIONS row, the relational form of the POSREC layout."""

    model_config = ConfigDict(from_attributes=True)

    investment_id: str
    position_date: date
    quantity: Decimal
    cost_basis: Decimal
    market_value: Decimal
    currency_code: str
    last_maint_date: datetime
    last_maint_user: str


class PortfolioInquiryResponse(BaseModel):
    portfolio_id: str
    position_date: date
    response_code: int
    positions: list[PositionResponse]
    total_cost_basis: Decimal
    total_market_value: Decimal


class InquiryErrorResponse(BaseModel):
    """COMMAREA error fields carried by INQCOM."""

    response_code: int
    error_message: str


@router.get(
    "/portfolio/{portfolio_id}",
    response_model=PortfolioInquiryResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": InquiryErrorResponse,
            "description": "No positions exist for the portfolio.",
        }
    },
)
def inquire_portfolio_positions(
    portfolio_id: Annotated[str, Path(min_length=1, max_length=8)],
    session: Annotated[Session, Depends(get_session)],
    position_date: Annotated[date | None, Query()] = None,
) -> PortfolioInquiryResponse:
    inquiry = inquire_portfolio(session, portfolio_id, position_date)
    return PortfolioInquiryResponse(
        portfolio_id=inquiry.portfolio_id,
        position_date=inquiry.position_date,
        response_code=RESP_NORMAL,
        positions=[PositionResponse.model_validate(position) for position in inquiry.positions],
        total_cost_basis=inquiry.total_cost_basis,
        total_market_value=inquiry.total_market_value,
    )


def position_not_found_handler(request: Request, exc: PositionNotFoundError) -> JSONResponse:
    """INQPORT's NOTFND path: the COMMAREA carries the response code and message."""
    logger.info(
        "Portfolio inquiry found no positions",
        extra={"portfolio_id": exc.portfolio_id, "position_date": str(exc.position_date)},
    )
    body = InquiryErrorResponse(response_code=RESP_NOTFND, error_message=str(exc))
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body.model_dump())
