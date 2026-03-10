from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    """No body required for session creation; session is created and id returned."""

    pass


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: str
