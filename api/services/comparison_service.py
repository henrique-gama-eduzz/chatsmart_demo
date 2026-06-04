from typing import Dict, Any, List, Optional
import logging
from ..agents.comparison.models import Analysis, ComparisonResult
from ..agents.comparison_agent import compare_analyses

logger = logging.getLogger("lean-six-sigma-api.comparison-service")

class ComparisonService:
    """Service for comparing analyses"""
    
    async def compare_analyses(self, analysis1: Analysis, analysis2: Analysis) -> ComparisonResult:
        """
        Compare two analyses
        
        Args:
            analysis1: First analysis
            analysis2: Second analysis
            
        Returns:
            A comparison result with insights and suggestions
        """
        try:
            logger.info(f"Comparing analyses {analysis1.id} and {analysis2.id}")
            
            # Convert to dictionaries for the comparison agent
            analysis1_dict = analysis1.dict()
            analysis2_dict = analysis2.dict()
            
            # Call the comparison agent
            result = compare_analyses(analysis1_dict, analysis2_dict)
            
            # Return the result
            return ComparisonResult(
                insights=result.get("insights", "No insights available"),
                improvement_suggestions=result.get("improvement_suggestions", "No suggestions available")
            )
        except Exception as e:
            logger.error(f"Error comparing analyses: {str(e)}")
            return ComparisonResult(
                insights="An error occurred while comparing analyses",
                improvement_suggestions="Please try again later"
            )
    
    async def get_comparison_by_ids(self, analysis1_id: int, analysis2_id: int) -> ComparisonResult:
        """
        Compare two analyses by their IDs
        
        Args:
            analysis1_id: ID of the first analysis
            analysis2_id: ID of the second analysis
            
        Returns:
            A comparison result with insights and suggestions
        """
        try:
            logger.info(f"Comparing analyses with IDs {analysis1_id} and {analysis2_id}")
            
            # In a real implementation, you would fetch the analyses from a database
            # For now, we'll create dummy analyses
            
            analysis1 = Analysis(
                id=analysis1_id,
                name=f"Analysis {analysis1_id}",
                dependent_vars=["y1", "y2"],
                independent_vars=["x1", "x2", "x3"],
                content="Dummy analysis 1",
                results={"success": True, "interpretation": "This is a dummy interpretation"}
            )
            
            analysis2 = Analysis(
                id=analysis2_id,
                name=f"Analysis {analysis2_id}",
                dependent_vars=["y1", "y3"],
                independent_vars=["x2", "x4", "x5"],
                content="Dummy analysis 2",
                results={"success": True, "interpretation": "This is another dummy interpretation"}
            )
            
            # Call the comparison agent
            return await self.compare_analyses(analysis1, analysis2)
        except Exception as e:
            logger.error(f"Error comparing analyses by IDs: {str(e)}")
            return ComparisonResult(
                insights="An error occurred while comparing analyses",
                improvement_suggestions="Please try again later"
            )
