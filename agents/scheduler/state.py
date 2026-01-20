from typing import Annotated, Optional, List
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
import operator

class AgentContext(BaseModel):
    raw_data: dict = Field(default_factory=dict)
    processed_at: str = Field(description="ISO timestamp")

class SchedulerState(TypedDict):
    input_query: str
    extracted_intent: Optional[str]
    context_data: Annotated[List[dict], operator.add]
    decision: Optional[str]
    retry_count: int
    error_log: Annotated[List[str], operator.add]
