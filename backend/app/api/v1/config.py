from fastapi import APIRouter

from app.config import settings
from app.schemas.config import DeploymentConfigResponse

router = APIRouter(tags=["config"])


@router.get("/config/deployment", response_model=DeploymentConfigResponse)
async def get_deployment_config():
    return DeploymentConfigResponse(cloud_mode=settings.CLOUD_MODE)
