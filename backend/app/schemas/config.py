from pydantic import BaseModel


class DeploymentConfigResponse(BaseModel):
    cloud_mode: bool
