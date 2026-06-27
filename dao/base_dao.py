"""Base DAO class with serialization support."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseDAO(ABC):
    """Abstract base class for all DAOs.
    
    Provides interface for JSON serialization/deserialization and
    database operations. All DAOs must implement these methods.
    """
    
    @classmethod
    @abstractmethod
    def fromJson(cls, json_data: Dict[str, Any]) -> 'BaseDAO':
        """Deserialize JSON data to DAO instance.
        
        Args:
            json_data: Dictionary containing DAO data
            
        Returns:
            DAO instance populated with data from json_data
            
        Raises:
            ValueError: If json_data is invalid or missing required fields
            KeyError: If required fields are missing
        """
        pass
    
    @abstractmethod
    def toJson(self) -> Dict[str, Any]:
        """Serialize DAO instance to JSON-compatible dictionary.
        
        Returns:
            Dictionary representation of DAO instance
        """
        pass
    
    @classmethod
    @abstractmethod
    def find_by_id(cls, id: Any):
        """Find record by ID.
        
        Args:
            id: Primary key value
            
        Returns:
            DAO instance if found, None otherwise
        """
        pass
    
    @abstractmethod
    def save(self):
        """Insert or update record in database.
        
        Returns:
            The saved DAO instance
        """
        pass
    
    @abstractmethod
    def delete(self):
        """Delete record from database.
        
        Returns:
            True if deleted, False otherwise
        """
        pass
