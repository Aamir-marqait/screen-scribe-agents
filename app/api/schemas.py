from pydantic import BaseModel, Field


class SubtopicRequest(BaseModel):
    subtopic: str = Field(..., min_length=1)


class OutputResponse(BaseModel):
    output: str
