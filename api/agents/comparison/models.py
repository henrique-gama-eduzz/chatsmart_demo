from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class Analysis(BaseModel):
    """Model representing an analysis for comparison purposes"""
    id: int = Field(..., description="Unique identifier for the analysis")
    name: str = Field(..., description="Name of the analysis")
    dependent_vars: List[str] = Field(..., description="List of dependent variables")
    independent_vars: List[str] = Field(..., description="List of independent variables")
    content: str = Field(..., description="Content/description of the analysis")
    results: Optional[Dict[str, Any]] = Field(None, description="Results of the analysis")

class ComparisonInput(BaseModel):
    """Input model for comparison request"""
    analysis1: Analysis = Field(..., description="First analysis to compare")
    analysis2: Analysis = Field(..., description="Second analysis to compare") 
    same_dataset: bool = Field(True, description="Whether both analyses use the same dataset")

class ComparisonResult(BaseModel):
    """Output model for comparison result"""
    insights: str = Field(..., description="Insights from comparing the analyses")
    improvement_suggestions: str = Field(..., description="Suggestions for improvement based on comparison") 
    variable_comparison: Optional[Dict[str, Any]] = None
    result_comparison: Optional[Dict[str, Any]] = None
