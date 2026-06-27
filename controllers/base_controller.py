"""Base controller with common functionality."""

from flask import jsonify
from typing import Any, Dict


class BaseController:
    """Base controller with common response handling."""
    
    @staticmethod
    def success_response(data: Any = None, message: str = None) -> Dict[str, Any]:
        """Create a success response.
        
        Args:
            data: Response data
            message: Optional message
            
        Returns:
            Dictionary with success flag and data
        """
        response = {
            'success': True,
            'data': data
        }
        if message:
            response['message'] = message
        return response
    
    @staticmethod
    def error_response(message: str, error_code: str = None) -> Dict[str, Any]:
        """Create an error response.
        
        Args:
            message: Error message
            error_code: Optional error code
            
        Returns:
            Dictionary with success flag and error message
        """
        response = {
            'success': False,
            'error': message
        }
        if error_code:
            response['error_code'] = error_code
        return response
    
    @staticmethod
    def json_response(data: Any, status_code: int = 200):
        """Convert data to Flask JSON response.
        
        Args:
            data: Data to convert
            status_code: HTTP status code (default 200)
            
        Returns:
            Flask JSON response
        """
        from flask import make_response
        response = make_response(jsonify(data), status_code)
        return response
