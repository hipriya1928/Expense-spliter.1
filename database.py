import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from models import Expense, Participant
from config import Config

class Database:
    """Database manager for expense records"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_amount REAL NOT NULL,
                num_people INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                participants_data TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_expense(self, expense: Expense) -> int:
        """Save expense to database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        participants_json = json.dumps([p.to_dict() for p in expense.participants])
        
        cursor.execute('''
            INSERT INTO expenses (total_amount, num_people, description, created_at, participants_data)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            expense.total_amount,
            expense.num_people,
            expense.description,
            expense.created_at.isoformat(),
            participants_json
        ))
        
        expense_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return expense_id
    
    def get_all_expenses(self) -> List[Expense]:
        """Retrieve all expenses"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM expenses ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        expenses = []
        for row in rows:
            participants_data = json.loads(row['participants_data'])
            participants = [
                Participant(
                    name=p['name'],
                    contribution=p['contribution'],
                    phone_number=p.get('phone_number'),
                    settlement_amount=p['settlement_amount']
                )
                for p in participants_data
            ]
            
            expense = Expense(
                id=row['id'],
                total_amount=row['total_amount'],
                num_people=row['num_people'],
                description=row['description'],
                created_at=datetime.fromisoformat(row['created_at']),
                participants=participants
            )
            expenses.append(expense)
        
        return expenses
    
    def get_expenses_by_month(self, year: int, month: int) -> List[Expense]:
        """Retrieve expenses for a specific month"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM expenses 
            WHERE strftime('%Y', created_at) = ? 
            AND strftime('%m', created_at) = ?
            ORDER BY created_at DESC
        ''', (str(year), str(month).zfill(2)))
        
        rows = cursor.fetchall()
        conn.close()
        
        expenses = []
        for row in rows:
            participants_data = json.loads(row['participants_data'])
            participants = [
                Participant(
                    name=p['name'],
                    contribution=p['contribution'],
                    phone_number=p.get('phone_number'),
                    settlement_amount=p['settlement_amount']
                )
                for p in participants_data
            ]
            
            expense = Expense(
                id=row['id'],
                total_amount=row['total_amount'],
                num_people=row['num_people'],
                description=row['description'],
                created_at=datetime.fromisoformat(row['created_at']),
                participants=participants
            )
            expenses.append(expense)
        
        return expenses
    
    def get_expense_by_id(self, expense_id: int) -> Optional[Expense]:
        """Retrieve a specific expense by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM expenses WHERE id = ?', (expense_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        participants_data = json.loads(row['participants_data'])
        participants = [
            Participant(
                name=p['name'],
                contribution=p['contribution'],
                phone_number=p.get('phone_number'),
                settlement_amount=p['settlement_amount']
            )
            for p in participants_data
        ]
        
        return Expense(
            id=row['id'],
            total_amount=row['total_amount'],
            num_people=row['num_people'],
            description=row['description'],
            created_at=datetime.fromisoformat(row['created_at']),
            participants=participants
        )
    
    def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted