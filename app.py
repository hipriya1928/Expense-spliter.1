from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
from typing import List
import traceback

from config import Config
from database import Database
from models import Expense, Participant
from utils import (
    calculate_settlements,
    send_whatsapp_notification,
    validate_expense_data
)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize database
db = Database()

@app.route('/')
def index():
    """Render main application page"""
    return render_template('index.html')

@app.route('/api/expenses', methods=['POST'])
def create_expense():
    """Create a new expense"""
    try:
        data = request.get_json()
        
        # Validate input data
        is_valid, error_message = validate_expense_data(data)
        if not is_valid:
            return jsonify({'error': error_message}), 400
        
        total_amount = float(data['total_amount'])
        num_people = int(data['num_people'])
        description = data.get('description', '').strip()
        
        # Create participants
        participants_data = data.get('participants', [])
        participants = []
        
        if participants_data:
            # Use provided participant details
            for p_data in participants_data:
                participant = Participant(
                    name=p_data['name'].strip(),
                    contribution=float(p_data.get('contribution', 0)),
                    phone_number=p_data.get('phone_number', '').strip() or None
                )
                participants.append(participant)
        else:
            # Create default participants with equal split
            per_person = total_amount / num_people
            for i in range(num_people):
                participant = Participant(
                    name=f"Person {i+1}",
                    contribution=per_person,
                    phone_number=None
                )
                participants.append(participant)
        
        # Calculate settlements
        participants, settlements = calculate_settlements(participants, total_amount)
        
        # Create expense object
        expense = Expense(
            id=None,
            total_amount=total_amount,
            num_people=num_people,
            description=description or f"Expense for {num_people} people",
            created_at=datetime.now(),
            participants=participants
        )
        
        # Save to database
        expense_id = db.save_expense(expense)
        expense.id = expense_id
        
        # Send WhatsApp notifications if requested
        send_notifications = data.get('send_notifications', False)
        notification_results = []
        
        if send_notifications:
            month = expense.created_at.strftime('%B %Y')
            for participant in participants:
                if participant.phone_number:
                    success = send_whatsapp_notification(participant, settlements, month)
                    notification_results.append({
                        'name': participant.name,
                        'success': success
                    })
        
        return jsonify({
            'success': True,
            'expense': expense.to_dict(),
            'settlements': [s.to_dict() for s in settlements],
            'notifications': notification_results
        }), 201
    
    except Exception as e:
        print(f"Error creating expense: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    """Get all expenses or filter by month"""
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        if year and month:
            expenses = db.get_expenses_by_month(year, month)
        else:
            expenses = db.get_all_expenses()
        
        return jsonify({
            'success': True,
            'expenses': [e.to_dict() for e in expenses]
        }), 200
    
    except Exception as e:
        print(f"Error getting expenses: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['GET'])
def get_expense(expense_id):
    """Get a specific expense"""
    try:
        expense = db.get_expense_by_id(expense_id)
        
        if not expense:
            return jsonify({'error': 'Expense not found'}), 404
        
        # Recalculate settlements for display
        _, settlements = calculate_settlements(expense.participants, expense.total_amount)
        
        return jsonify({
            'success': True,
            'expense': expense.to_dict(),
            'settlements': [s.to_dict() for s in settlements]
        }), 200
    
    except Exception as e:
        print(f"Error getting expense: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense"""
    try:
        success = db.delete_expense(expense_id)
        
        if not success:
            return jsonify({'error': 'Expense not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Expense deleted successfully'
        }), 200
    
    except Exception as e:
        print(f"Error deleting expense: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/history/months', methods=['GET'])
def get_history_months():
    """Get list of months with expenses"""
    try:
        expenses = db.get_all_expenses()
        
        # Extract unique year-month combinations
        months = set()
        for expense in expenses:
            months.add((expense.created_at.year, expense.created_at.month))
        
        # Sort and format
        months_list = sorted(list(months), reverse=True)
        formatted_months = [
            {
                'year': year,
                'month': month,
                'display': datetime(year, month, 1).strftime('%B %Y')
            }
            for year, month in months_list
        ]
        
        return jsonify({
            'success': True,
            'months': formatted_months
        }), 200
    
    except Exception as e:
        print(f"Error getting history months: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/test-notification', methods=['POST'])
def test_notification():
    """Test WhatsApp notification"""
    try:
        data = request.get_json()
        
        if not data.get('phone_number'):
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Create test participant
        participant = Participant(
            name=data.get('name', 'Test User'),
            contribution=100,
            phone_number=data['phone_number'],
            settlement_amount=10.50
        )
        
        # Create test settlement
        settlements = [
            Settlement(
                from_person="Alice",
                to_person=participant.name,
                amount=10.50
            )
        ]
        
        success = send_whatsapp_notification(participant, settlements, "Test Month")
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Test notification sent successfully'
            }), 200
        else:
            return jsonify({
                'error': 'Failed to send notification. Check Twilio credentials.'
            }), 500
    
    except Exception as e:
        print(f"Error sending test notification: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("Starting Expense Splitter Application...")
    print(f"Database: {Config.DATABASE_PATH}")
    print(f"Twilio configured: {bool(Config.TWILIO_ACCOUNT_SID)}")
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)