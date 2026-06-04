from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any

from ..agents.comparison.models import Analysis, ComparisonResult, ComparisonInput
from ..services.comparison_service import ComparisonService
from ..agents.comparison_agent import compare_analyses as compare_with_agent

router = APIRouter()

@router.post("/compare-analyses", 
             response_model=ComparisonResult,
             status_code=status.HTTP_200_OK,
             summary="Compare two analyses",
             description="Compare two analyses and generate a detailed comparison")
async def compare_analyses(
    input_data: ComparisonInput,
    comparison_service: ComparisonService = Depends(lambda: ComparisonService())
):
    """
    Compare two analyses and return a detailed comparison
    
    - **analysis1**: First analysis to compare
    - **analysis2**: Second analysis to compare
    
    Returns a detailed comparison with similarities, differences, and recommendations
    """
    return await comparison_service.compare_analyses(
        analysis1=input_data.analysis1,
        analysis2=input_data.analysis2
    )

@router.get("/compare/{analysis1_id}/{analysis2_id}", 
            response_model=ComparisonResult,
            status_code=status.HTTP_200_OK,
            summary="Compare two analyses by ID",
            description="Compare two analyses by their IDs and generate a detailed comparison")
async def get_comparison(
    analysis1_id: int, 
    analysis2_id: int,
    comparison_service: ComparisonService = Depends(lambda: ComparisonService())
):
    """
    Compare two analyses by their IDs
    
    - **analysis1_id**: ID of the first analysis
    - **analysis2_id**: ID of the second analysis
    
    Returns a detailed comparison with similarities, differences, and recommendations
    """
    return await comparison_service.get_comparison_by_ids(
        analysis1_id=analysis1_id,
        analysis2_id=analysis2_id
    )

@router.post("/ai-insights", 
             status_code=status.HTTP_200_OK,
             summary="Generate AI insights for two analyses",
             description="Compare two analyses and generate AI insights using LangGraph agent")
async def get_ai_insights(analysis1: Dict[str, Any], analysis2: Dict[str, Any], same_dataset: bool = True):
    """
    Generate AI insights comparing two analyses
    
    - **analysis1**: First analysis data
    - **analysis2**: Second analysis data
    - **same_dataset**: Whether the analyses are from the same dataset
    
    Returns insights and improvement suggestions
    """
    try:
        result = compare_with_agent(analysis1, analysis2, same_dataset)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating insights: {str(e)}"
        )
