import uuid
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

from enum import Enum
from sqlalchemy import Enum as saEnum

# Enum voor transaction status
class TransactionStatus(Enum):
    PAID = "paid"
    NOT_PAID = "not_paid"

# Enum voor service status
class ServiceStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    NOT_COMPLETED = "not_completed"
    
class location_type(Enum):
    Antwerp = 'Antwerp'
    East_Flanders = 'East Flanders'
    Flemish_Brabant = 'Flemish Brabant'
    Limburg = 'Limburg'
    West_Flanders = 'West Flanders'

# User Entity
class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)  # userID
    auth_id = db.Column(db.String(128), nullable=False, default=uuid.uuid4)  # Standaardwaarde toevoegen
    first_name = db.Column(db.String(80), nullable=False)  # Voornaam
    last_name = db.Column(db.String(80), nullable=False)  # Achternaam
    email = db.Column(db.String(120), unique = True, nullable=False)
    password_hash = db.Column(db.String(225), nullable=False)  # Gehashed wachtwoord
    username = db.Column(db.String(80), unique=True, nullable=False) 

   
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='reviewer', lazy=True)

    def __init__(self, first_name, last_name, email, password=None, username=None, **kwargs):
        if password:
            self.set_password(password)  # Als er een wachtwoord is, gebruik de set_password functie
        else:
            self.password_hash = None  # Of geef een andere standaardwaarde als je dat wilt
        if username is None:  # Als username niet opgegeven is, gebruik email
            username = email.split('@')[0]  # Dit maakt de username gelijk aan het gedeelte voor de @ in het emailadres
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.username = username
        super().__init__(**kwargs)

    def set_password(self, password):
        """Slaat een gehashte versie van het wachtwoord op."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Controleert of het wachtwoord correct is."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.first_name}>'

# Andere tabellen blijven hetzelfde...
class Listing(db.Model):  
    __tablename__ = 'listing'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)  # Leeftijd van de aanbieder
    bio = db.Column(db.String(500), nullable=False)  # Bio van de aanbieder
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location = db.Column(saEnum(location_type), nullable=False)
    price = db.Column(db.Float, nullable=False)  # Prijs per uur
    services = db.Column(db.JSON, nullable=False)  # Services (zoals dogwalks, daycare, etc.)
    available_period_start = db.Column(db.Date, nullable=False)
    available_period_end = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.ARRAY(db.Time), nullable=False)
    end_time = db.Column(db.ARRAY(db.Time), nullable=False)
    selected_days = db.Column((db.String), nullable=True)  # Comma-separated days string

    reviews_received = db.relationship('Review', foreign_keys='Review.reviewed_listing_id', backref='listing', lazy=True)
    provider = db.relationship('Users', foreign_keys=[provider_id], backref=db.backref('provided_listings', lazy=True))
    
    def __repr__(self):
        return f"<Listing {self.name}>"
        
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # notificationID
    type = db.Column(db.String(50), nullable=False)
    viewed = db.Column(db.Boolean, default=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return f'<Notification {self.type}>'
 

# Dog Booking (Subkind of Transaction)
class DogBooking(db.Model):
    __tablename__ = 'dog_booking'
    id = db.Column(db.Integer, primary_key=True)  # DogBookingID
    start_time_booking = db.Column(db.Time, nullable=False)
    end_time_booking = db.Column(db.Time, nullable=False)
    day_booking = db.Column((db.String), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name_dogsitter = db.Column(db.String(100), db.ForeignKey('listing.name'), nullable=False)
    price_dogsitter = db.Column(db.Float, db.ForeignKey('listing.price'), nullable=False)
    #dogs_booked = db.Column(db.Integer, nullable=False)#
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)

    def __repr__(self):
        return f'<DogBooking {self.id}>'


# Transaction Entity
class Transaction(db.Model):
    __tablename__ = 'transaction'
    id = db.Column(db.Integer, primary_key=True)  # transactionID
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    dog_booking_id = db.Column(db.Integer, db.ForeignKey('dog_booking.id'))

    status = db.Column(saEnum(TransactionStatus), default=TransactionStatus.NOT_PAID)  # Default is now 'not_paid'
    service_status = db.Column(saEnum(ServiceStatus), default=ServiceStatus.NOT_COMPLETED)  # Default is now 'not_completed'

    listing = db.relationship('Listing', backref='Transaction')
    buyer = db.relationship('Users', backref='Transaction')

    def __repr__(self):
        return f'<Transaction {self.id} - {self.status} - Service {self.service_status}>'


# Available Time Slot Entity
class AvailableTimeSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # TimeSlotID
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)

    def __repr__(self):
        return f'<AvailableTimeSlot {self.id}>'


# Category Entity
class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)  # CategoryID
    name = db.Column(db.String(120), nullable=False)

    def __repr__(self):
        return f'<Category {self.name}>'


# Review Entity (Relator)
class Review(db.Model):
    __tablename__ = 'review'
    id = db.Column(db.Integer, primary_key=True)  # ReviewID
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    reviewed_listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<Review {self.id}>'


# Message Entity
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # MessageID
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<Message {self.id}>'
