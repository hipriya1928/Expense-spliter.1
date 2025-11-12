from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class Participant:
    """Represents a participant in an expense"""
    name: str
    contribution: float
    phone_number: Optional[str] = None
    settlement_amount: float = 0.0  # Positive means receives, negative means owes
    
    def to_dict(self):
        return {
            'name': self.name,
            'contribution': self.contribution,
            'phone_number': self.phone_number,
            'settlement_amount': self.settlement_amount
        }

@dataclass
class Expense:
    """Represents an expense record"""
    id: Optional[int]
    total_amount: float
    num_people: int
    description: str
    created_at: datetime
    participants: List[Participant]
    
    def to_dict(self):
        return {
            'id': self.id,
            'total_amount': self.total_amount,
            'num_people': self.num_people,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'participants': [p.to_dict() for p in self.participants]
        }

@dataclass
class Settlement:
    """Represents a settlement between two participants"""
    from_person: str
    to_person: str
    amount: float
    
    def to_dict(self):
        return {
            'from_person': self.from_person,
            'to_person': self.to_person,
            'amount': round(self.amount, 2)
        }