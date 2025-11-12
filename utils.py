import re
from typing import List, Tuple
from twilio.rest import Client
from models import Participant, Settlement
from config import Config

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    if not phone:
        return False
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Phone number should have 10-15 digits
    return 10 <= len(digits) <= 15

def format_phone_number(phone: str) -> str:
    """Format phone number for WhatsApp (E.164 format)"""
    if not phone:
        return None
    
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # If doesn't start with country code, assume +1 (US)
    if len(digits) == 10:
        digits = '1' + digits
    
    return f'whatsapp:+{digits}'

def calculate_settlements(participants: List[Participant], total_amount: float) -> Tuple[List[Participant], List[Settlement]]:
    """
    Calculate who owes whom based on contributions
    Returns updated participants with settlement_amount and list of settlements
    """
    if not participants:
        return [], []
    
    # Calculate per-person share
    per_person_share = total_amount / len(participants)
    
    # Calculate settlement amounts for each participant
    for participant in participants:
        participant.settlement_amount = participant.contribution - per_person_share
    
    # Create lists of debtors (owe money) and creditors (receive money)
    debtors = [p for p in participants if p.settlement_amount < -0.01]
    creditors = [p for p in participants if p.settlement_amount > 0.01]
    
    # Sort for optimal settlement
    debtors.sort(key=lambda x: x.settlement_amount)
    creditors.sort(key=lambda x: x.settlement_amount, reverse=True)
    
    # Generate settlements
    settlements = []
    i, j = 0, 0
    
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        
        debt_amount = abs(debtor.settlement_amount)
        credit_amount = creditor.settlement_amount
        
        settlement_amount = min(debt_amount, credit_amount)
        
        settlements.append(Settlement(
            from_person=debtor.name,
            to_person=creditor.name,
            amount=settlement_amount
        ))
        
        # Update balances
        debtor.settlement_amount += settlement_amount
        creditor.settlement_amount -= settlement_amount
        
        # Move to next debtor/creditor if balance is settled
        if abs(debtor.settlement_amount) < 0.01:
            i += 1
        if abs(creditor.settlement_amount) < 0.01:
            j += 1
    
    return participants, settlements

def send_whatsapp_notification(participant: Participant, settlements: List[Settlement], month: str) -> bool:
    """
    Send WhatsApp notification to participant
    Returns True if successful, False otherwise
    """
    # Check if Twilio credentials are configured
    if not Config.TWILIO_ACCOUNT_SID or not Config.TWILIO_AUTH_TOKEN:
        print(f"Twilio credentials not configured. Skipping notification for {participant.name}")
        return False
    
    # Check if participant has phone number
    if not participant.phone_number:
        print(f"No phone number for {participant.name}")
        return False
    
    try:
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        
        # Build message
        message = f"Hi {participant.name}! Your expense split for {month} is ready.\n\n"
        
        if participant.settlement_amount > 0.01:
            message += f"You get back ${abs(participant.settlement_amount):.2f}.\n\n"
            message += "Settlement details:\n"
            
            # Find who owes this participant
            for settlement in settlements:
                if settlement.to_person == participant.name:
                    message += f"• {settlement.from_person} owes you ${settlement.amount:.2f}\n"
        
        elif participant.settlement_amount < -0.01:
            message += f"You owe ${abs(participant.settlement_amount):.2f}.\n\n"
            message += "Settlement details:\n"
            
            # Find who this participant owes
            for settlement in settlements:
                if settlement.from_person == participant.name:
                    message += f"• Pay ${settlement.amount:.2f} to {settlement.to_person}\n"
        
        else:
            message += "You're all settled up! No payments needed.\n"
        
        message += "\nReply CONFIRM to acknowledge."
        
        # Send message
        formatted_phone = format_phone_number(participant.phone_number)
        
        twilio_message = client.messages.create(
            from_=Config.TWILIO_WHATSAPP_NUMBER,
            body=message,
            to=formatted_phone
        )
        
        print(f"WhatsApp notification sent to {participant.name}: {twilio_message.sid}")
        return True
    
    except Exception as e:
        print(f"Error sending WhatsApp notification to {participant.name}: {str(e)}")
        return False

def validate_expense_data(data: dict) -> Tuple[bool, str]:
    """
    Validate expense input data
    Returns (is_valid, error_message)
    """
    # Check required fields
    if 'total_amount' not in data:
        return False, "Total amount is required"
    
    if 'num_people' not in data:
        return False, "Number of people is required"
    
    # Validate total amount
    try:
        total_amount = float(data['total_amount'])
        if total_amount < Config.MIN_AMOUNT:
            return False, f"Total amount must be at least ${Config.MIN_AMOUNT}"
        if total_amount > Config.MAX_AMOUNT:
            return False, f"Total amount cannot exceed ${Config.MAX_AMOUNT}"
    except (ValueError, TypeError):
        return False, "Invalid total amount"
    
    # Validate number of people
    try:
        num_people = int(data['num_people'])
        if num_people < 1:
            return False, "Number of people must be at least 1"
        if num_people > Config.MAX_PARTICIPANTS:
            return False, f"Number of people cannot exceed {Config.MAX_PARTICIPANTS}"
    except (ValueError, TypeError):
        return False, "Invalid number of people"
    
    # Validate participants if provided
    participants = data.get('participants', [])
    if participants:
        if len(participants) != num_people:
            return False, f"Number of participants ({len(participants)}) must match num_people ({num_people})"
        
        total_contributions = 0
        for p in participants:
            if 'name' not in p or not p['name'].strip():
                return False, "All participants must have a name"
            
            try:
                contribution = float(p.get('contribution', 0))
                if contribution < 0:
                    return False, f"Contribution for {p['name']} cannot be negative"
                total_contributions += contribution
            except (ValueError, TypeError):
                return False, f"Invalid contribution amount for {p['name']}"
            
            # Validate phone number if provided
            phone = p.get('phone_number', '').strip()
            if phone and not validate_phone_number(phone):
                return False, f"Invalid phone number for {p['name']}"
        
        # Check if contributions match total (with small tolerance for rounding)
        if abs(total_contributions - total_amount) > 0.01:
            return False, f"Sum of contributions (${total_contributions:.2f}) must equal total amount (${total_amount:.2f})"
    
    return True, ""