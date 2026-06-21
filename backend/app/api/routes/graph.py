from fastapi import APIRouter, HTTPException

from app.schemas.graph import CalculateProductionRequest, ProductionPlan
from app.services.graph_service import graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/calculate", response_model=ProductionPlan)
def calculate_production(request: CalculateProductionRequest) -> ProductionPlan:
    try:
        return graph_service.calculate_production(request)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
