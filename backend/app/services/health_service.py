from app.schemas.health import HealthResponse

SERVICE_NAME = "recipe-tree-visualizer"


def get_health_status() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME)
