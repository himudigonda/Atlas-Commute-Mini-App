from datetime import datetime
from enum import Enum
from typing import Annotated, List, Optional, Union, Dict, Any
from typing_extensions import TypedDict
import operator

from pydantic import BaseModel, Field, field_validator, ConfigDict

# --- Enums for Strict Categorization ---
class TrafficStatus(str, Enum):
    CLEAR = "clear"
    MODERATE = "moderate"
    HEAVY = "heavy"
    GRIDLOCK = "gridlock"

class FlightStatus(str, Enum):
    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    BOARDING = "boarding"

class DecisionAction(str, Enum):
    WAIT = "wait"
    NUDGE_LEAVE_NOW = "nudge_leave_now"
    NUDGE_BOOK_UBER = "nudge_book_uber"

# --- Domain Entities (The "Nouns") ---

class GeoLocation(BaseModel):
    """Represents a physical location point."""
    address: str = Field(..., description="Human readable address")
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lng: Optional[float] = Field(None, ge=-180, le=180)

class TrafficMetrics(BaseModel):
    """Data returned from Traffic Tool."""
    distance_meters: int = Field(..., ge=0)
    duration_seconds: int = Field(..., ge=0)
    traffic_delay_seconds: int = Field(0, ge=0, description="Additional time due to traffic")
    status: TrafficStatus
    route_summary: str

class FlightMetrics(BaseModel):
    """Data returned from Flight Tool."""
    flight_number: str
    status: FlightStatus
    scheduled_departure: datetime
    estimated_departure: datetime
    gate: Optional[str] = None
    terminal: Optional[str] = None

# --- User Intent & Context (The "Inputs") ---

class UserContext(BaseModel):
    """Structured context extracted from user input via Flash model."""
    user_id: str
    origin: str
    destination: str = Field(..., description="Target destination (e.g., Airport)")
    flight_number: str = Field(..., pattern=r"^[A-Z0-9]{2,}\d+$")
    target_arrival_time: Optional[datetime] = Field(
        None, 
        description="When user wants to be at the destination"
    )
    
    model_config = ConfigDict(extra="ignore")

# --- Agent Decisions (The "Outputs") ---

class CommutePlan(BaseModel):
    """The final reasoning result from the Pro model."""
    metrics_analyzed: bool = True
    buffer_minutes_remaining: float
    recommended_action: DecisionAction
    reasoning_trace: str = Field(..., description="Short explanation of the decision logic")
    notification_message: Optional[str] = Field(None, description="Drafted message for the user")

# --- LangGraph State (The "Memory") ---

class SchedulerState(TypedDict):
    """
    The shared memory state for the LangGraph workflow.
    Tracks the lifecycle of a request from raw input to final notification.
    Includes Self-Healing mechanisms (retry_count, error_log).
    """
    # 1. Inputs
    raw_query: str
    user_context: Optional[UserContext]
    
    # 2. External World Data (Hydrated by Tools)
    traffic_data: Optional[TrafficMetrics]
    flight_data: Optional[FlightMetrics]
    
    # 3. Reasoning & Outputs
    plan: Optional[CommutePlan]
    
    # 4. Self-Healing & Observability
    # Annotated[..., operator.add] allows us to append errors rather than overwrite
    error_log: Annotated[List[str], operator.add] 
    retry_count: int
    execution_trace: Annotated[List[str], operator.add]
