from fastapi import APIRouter, HTTPException
from loguru import logger

from app.graph.errors import GraphValidationError
from app.schemas.graph import CalculateProductionRequest, ProductionPlan
from app.services.graph_service import graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/calculate", response_model=ProductionPlan)
def calculate_production(request: CalculateProductionRequest) -> ProductionPlan:
    logger.info(
        "POST /graph/calculate target={} rate={}/min version={}",
        request.target_item_id,
        request.target_rate_per_minute,
        request.version,
    )
    try:
        return graph_service.calculate_production(request)
    except GraphValidationError as exc:
        logger.error("Production calculation failed: {}", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
