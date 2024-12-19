from flask import Blueprint, request, redirect, url_for, render_template, session, flash, request
from .models import db, Users, Listing, Notification, DogBooking, Transaction, Category, AvailableTimeSlot, Review, Message, location_type, TransactionStatus, ServiceStatus
from werkzeug.utils import secure_filename
import os
from flask import current_app
from datetime import datetime, time


main = Blueprint('main', __name__)

# Home route
@main.route('/')
def index():
    user = None
    if 'user_id' in session:
        user = Users.query.get(session['user_id'])
    return render_template('index.html', username=user.username if user else None)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Zoek gebruiker op basis van e-mail
        user = Users.query.filter_by(email=email).first()

        if user:
            # Controleer of wachtwoord klopt
            if user.check_password(password):  # Zorg dat `check_password` goed is geïmplementeerd
                # Stel sessievariabelen in
                session['user_id'] = user.id  # Unieke identificatie van de gebruiker
                session['users_email'] = user.email  # Optioneel, voor extra info
                flash('Login successful!', 'success')

                # Verwerk de 'next' parameter als deze bestaat
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                
                # Stuur naar de hoofdpagina als er geen 'next' is
                return redirect(url_for('main.index'))
            else:
                flash('Invalid password. Please try again.', 'danger')  # Ongeldig wachtwoord
        else:
            flash('No account found with that email.', 'danger')  # Geen account gevonden

        # Blijf op de login-pagina bij foutieve invoer
        return redirect(url_for('main.login'))

    return render_template('login.html')

@main.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)  # Verwijder de gebruiker uit de sessie
    session.pop('users_email', None)  # Optioneel: Verwijder e-mail uit sessie
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))  # Verwijs naar de hoofdpagina of login-pagina

#About Us route
@main.route('/about')
def about():
    return render_template('about.html')

@main.route('/dogsitter_form', methods=['GET', 'POST'])
def dogsitter_form():
    if 'user_id' not in session:
        flash('You must be logged in to access this page.')
        return redirect(url_for('main.login', next=request.url))

    locations = [
        ('Antwerp', 'Antwerp'),
        ('East_Flanders', 'East Flanders'),
        ('West_Flanders', 'West Flanders'),
        ('Flemish_Brabant', 'Flemish Brabant'),
        ('Limburg', 'Limburg')
    ]
    services = ['Dogwalks', 'Daycare', 'Overnight Stay']
    # speciaal algoritme implementatie
    # Bereken demand index voor alle provincies
    demand_index_data = calculate_demand_index()
    
    price_ranges = {}
    for location, label in locations:
        # Haal de concurrentieprijzen in de huidige provincie op
        competitor_prices = [
            l.price for l in Listing.query.filter(Listing.location == location).all()
        ]

        if competitor_prices:
            avg_competitor_price = sum(competitor_prices) / len(competitor_prices)
        else:
            avg_competitor_price = 25.0  # Default gemiddelde prijs bij gebrek aan data

        # Demand index ophalen en omzetten naar prijsfactor
        demand_index = demand_index_data.get(location, 0.5)
        demand_factor = 0.9 + (demand_index * 0.3)  # Schaal tussen 0.9 en 1.2

        # Optimal price berekenen
        optimal_price = round(avg_competitor_price * demand_factor, 1)

        # Prijsrange opslaan
        price_ranges[label] = {
            "min": round(optimal_price *0.9, 1), # 1 cijfer na komma afronden EN een marge van 10% voor optimale prijs
            "max": round(optimal_price *1.1, 1)

        }
        # Haal de locatie uit het formulier en converteer naar de ENUM-waarde
         # Vervang spaties door underscores
    if request.method == 'POST':
        
            name = request.form['name']
            age = request.form['age']
            bio = request.form['bio']
            location = request.form['location']
            price = request.form['price']
            available_period_start = request.form['available_period_start']  # Ophalen uit formulier
            available_period_end = request.form['available_period_end']  # Ophalen uit formulier
            start_time = request.form.getlist('start_time')  # Ophalen als lijst
            end_time = request.form.getlist('end_time')  # Ophalen als lijst     # Tijd zonder tijdzone
            selected_days = request.form.getlist('days')
            formatted_days = "{" + ",".join(selected_days) + "}"
            
            location_enum = location_type[location.replace(' ', '_')]

            
            
            

            

            # Maak de nieuwe listing aan
            new_listing = Listing(
        name=name,
        age=int(age),
        bio=bio,
        provider_id=session['user_id'],
        location=location,
        price=float(price),
        services=request.form.getlist('services'),
        available_period_start=datetime.strptime(available_period_start, "%Y-%m-%d").date(),
        available_period_end=datetime.strptime(available_period_end, "%Y-%m-%d").date(),
        start_time=start_time, 
        end_time=end_time,     # Tijd zonder tijdzone
        selected_days=formatted_days
            )

            db.session.add(new_listing)
            db.session.commit()

            flash('Listing added successfully!', 'success')
            return redirect(url_for('main.index'))

        

    return render_template('dogsitter_form.html',  locations=locations, services=services, price_ranges=price_ranges)


# View notifications
@main.route('/notifications')
def notifications():
    if 'user_id' not in session:
        flash('You must be logged in to view notifications.')
        return redirect(url_for('main.login'))

    user_id = session['user_id']
    notifications = Notification.query.filter_by(receiver_id=user_id).all()
    return render_template('notifications.html', notifications=notifications)


# View listings
@main.route('/listings')
def listings():
    listings = Listing.query.all()
    return render_template('listings.html', listings=listings)

@main.route('/reviews', methods=['GET'])
def reviews():
    reviews = Review.query.all()
    for review in reviews:
        # Gebruik de relatie om de bijbehorende listing op te halen
        review.listing_name = review.listing.name  # Hier krijg je de naam van de listing
    return render_template('reviews.html', reviews=reviews)

# Add a review
@main.route('/add_review', methods=['GET','POST'])
def add_review():
    user_id = session.get('user_id')  # Controleer of de gebruiker is ingelogd
    if not user_id:
        flash('You must be logged in to add a review.')
        return redirect(url_for('main.login'))
     # Filter de boekingen om alleen de relevante listings voor de huidige gebruiker te krijgen
    bookings = DogBooking.query.filter_by(user_id=user_id).all()
    
    
     # Haal de boekingen van de huidige gebruiker op
    bookings = DogBooking.query.filter(DogBooking.user_id == user_id).all()

    # Haal de bijbehorende listings op van de geboekte users
    listings = []
    for booking in bookings:
        listing = Listing.query.filter_by(name=booking.name_dogsitter).first()
        if listing:
            listings.append(listing)

    
    if request.method == 'POST':
        score = request.form['score']
        comment = request.form['comment']
        reviewed_listing_id = request.form['reviewed_listing_id']
        
        new_review = Review(
            score=score,
            comment=comment,
            reviewed_listing_id=reviewed_listing_id,
            reviewer_id=session['user_id']
        )
        db.session.add(new_review)
        db.session.commit()
        flash('Review added successfully!')
        return redirect(url_for('main.reviews'))
    
    listings = Listing.query.all()
    return render_template('add_review.html', listings=listings)

@main.route('/services')
def services():
    return render_template('services.html')

# Route voor de betalingspagina
@main.route('/payment')
def payment():
    user_id = session.get('user_id')  # Haal de gebruiker uit de sessie
    if user_id:
        # Haal transacties op van de ingelogde gebruiker
        user_transactions = Transaction.query.filter_by(buyer_id=user_id).all()

        # Splits de transacties op status
        not_paid = [t for t in user_transactions if t.status == 'not_paid']
        paid = [t for t in user_transactions if t.status == 'paid']

        return render_template('payment.html', not_paid=not_paid, paid=paid)
    else:
        return render_template('payment.html', not_logged_in=True)

# Route voor betalen
@main.route('/pay/<int:transaction_id>', methods=['POST'])
def pay(transaction_id):
    user_id = session.get('user_id')  # Controleer of de gebruiker is ingelogd
    if user_id:
        # Zoek de transactie van de ingelogde gebruiker
        transaction = Transaction.query.filter_by(id=transaction_id, buyer_id=user_id, status='not_paid').first()
        if transaction:
            # Controleer of de service is uitgevoerd
            if transaction.service_status == 'completed':
                transaction.status = 'paid'  # Update de status naar betaald
                db.session.commit()  # Sla de wijziging op
                flash('Payment successful!')
            else:
                flash('The service has not been completed yet. You cannot pay at this moment.')
        else:
            flash('Invalid transaction or already paid.')
    else:
        flash('You must be logged in to make a payment.')

    return redirect(url_for('payment'))


# Send Message (User role: Any user can send messages)
@main.route('/send_message', methods=['GET', 'POST'])
def send_message():
    if 'user_id' not in session:
        flash('You must be logged in to send a message.')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        content = request.form['content']
        recipient_id = request.form['recipient_id']

        new_message = Message(
            sender_id=session['user_id'],
            content=content,
            timestamp=datetime.utcnow(),
            recipient_id=recipient_id
        )
        db.session.add(new_message)
        db.session.commit()
        flash('Message sent successfully!')
        return redirect(url_for('main.index'))

    return render_template('send_message.html')

# New Route: Find Dog Sitters
@main.route('/find-dog-sitters', methods=['GET'])
def find_dog_sitters():
    province = request.args.get('province', None)
    if province:
        # Query the database for listings in the selected province
        listings = Listing.query.filter_by(location=province).all()
        return render_template('listings.html', listings=listings, province=province)
    else:
        flash("Please select a valid province.")
        return redirect(url_for('main.index'))
    
    
# Sign-up route
@main.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Controleer of wachtwoorden overeenkomen
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('main.signup'))

        # Controleer of de gebruiker al bestaat
        if Users.query.filter_by(email=email).first():
            flash('Email is already registered. Please use a different email.', 'danger')
            return redirect(url_for('main.signup'))
        
        # Maak een nieuwe gebruiker
        new_user = Users(
            first_name=first_name,
            last_name=last_name, 
            username=email,
            email=email
        )
        new_user.set_password(password)  # Wachtwoord veilig opslaan
        db.session.add(new_user)
        db.session.commit()

        # Automatisch inloggen na registratie
        session['user_id'] = new_user.id
        flash('Registration successful! Welcome, {} {}.'.format(first_name, last_name), 'success')
        return redirect(url_for('main.index'))

    # Geen flash-berichten bij een GET-verzoek
    return render_template('signup.html')


@main.route('/dog_walks', methods = ['GET'])
def dog_walks():
    return render_template('dog_walks.html')

@main.route('/daycare', methods = ['GET'])
def daycare():
    return render_template('daycare.html')

@main.route('/overnight_stay', methods = ['GET'])
def overnight_stay():
    return render_template('overnight_stay.html')

@main.route('/book-dogsitter/<int:listing_id>', methods=['GET', 'POST'])
def book_dogsitter(listing_id):
    # Haal listing en tijden op
    if 'user_id' not in session:
        flash("You must be logged in to book a dogsitter.", "danger")
        return redirect(url_for('main.login'))
    
    listing = Listing.query.get_or_404(listing_id)
    
   
    if request.method == 'POST':
        day = request.form.get('day')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
         # Maak een nieuwe transactie aan (gebruik de prijs uit de listing)
        transaction = Transaction (
            listing_id=listing.id,
            buyer_id=session['user_id'],  # Stel de buyer_id in als de ingelogde gebruiker
            status=TransactionStatus.NOT_PAID,  # Deze wordt ingesteld
            service_status=ServiceStatus.NOT_COMPLETED  # Hier stellen we 'Not Completed' in  # Gebruik de enumwaarde, niet de string
            
        )
        db.session.add(transaction)
        db.session.commit()

        # Convert string naar Python-datetime objecten
        day = datetime.strptime(day, '%Y-%m-%d').date()
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()

         # Controleer of de dag en tijd binnen de beschikbaarheid valt
        if not (listing.available_period_start <= day <= listing.available_period_end) :
            flash("Selected date is outside the available range.", "danger")
            return redirect(url_for('main.book_dogsitter', listing_id=listing.id))
        
        if day.strftime('%A').lower() not in [d.lower() for d in listing.selected_days]: 
            print("Selected date is outside the available range.", "danger")
            return redirect(url_for('main.book_dogsitter', listing_id=listing.id))

        if start_time < listing.start_time[0] or end_time > listing.end_time[0]:
            flash("Time is outside the available range!", "danger")
            return redirect(url_for('main.book_dogsitter', listing_id=listing.id))

       
        
        # Als alles geldig is, voeg de boeking toe
        new_booking = DogBooking(
            start_time_booking=start_time,
            end_time_booking=end_time,
            day_booking=day.strftime('%Y-%m-%d'),
            user_id=session['user_id'],
            name_dogsitter=listing.name,
            price_dogsitter=listing.price,
            transaction_id=transaction.id,
            

        )
        db.session.add(new_booking)
        db.session.commit()

        flash("Booking successful!", "success")
        return redirect(url_for('main.index'))

    return render_template('book_dogsitter.html', listing=listing)



# special algorithm
@main.route('/bookings')
def bookings():

    # Zorg ervoor dat de gebruiker ingelogd is
    if 'user_id' not in session:
        flash("You must be logged in to view your bookings.", "danger")
        return redirect(url_for('main.login'))  # Redirect naar loginpagina als niet ingelogd

    # Haal alle boekingen op die behoren tot de ingelogde gebruiker
    user_bookings = DogBooking.query.filter_by(user_id=session['user_id']).all()
    return render_template('bookings.html', user_bookings=user_bookings)

@main.route('/cancel-booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    # Zoek de boeking op die geannuleerd moet worden
    booking = DogBooking.query.get_or_404(booking_id)

    # Zorg ervoor dat de boeking van de ingelogde gebruiker is
    if booking.user_id != session['user_id']:
        flash("You cannot cancel this booking.", "danger")
        return redirect(url_for('main.bookings'))

    # Verwijder de boeking
    db.session.delete(booking)
    db.session.commit()

    flash("Booking canceled successfully!", "success")
    return redirect(url_for('main.bookings'))

# special algorithm

@main.route('/calculate_optimal_price/<int:listing_id>', methods=['GET'])
def calculate_optimal_price(listing_id):
    """
    Calculate the optimal price for a listing based on demand, competitor prices, and available listings.
    """
    # pick the listing data
    listing = Listing.query.get(listing_id)
    if not listing:
        return {"error": "Listing not found"}

    # demand index for the location
    demand_index = calculate_demand_index_for_location(listing.location)

    # Fetch competitor prices and count available listings in the same location
    competitor_prices = [
        l.price for l in Listing.query.filter(Listing.location == listing.location, Listing.id != listing_id).all()
    ]
    available_listings = Listing.query.filter(Listing.location == listing.location).count()

    # Handle cases with no competitor data
    if not competitor_prices:
        return {"error": "No competitor data available"}

    # Calculate averages
    avg_competitor_price = sum(competitor_prices) / len(competitor_prices)

    # Example coefficients 
    b0, b1, b2, b3 = 20, 15, 0.5, 1.2

    # Calculate the optimal price
    optimal_price = round(b0 + b1 * demand_index + b2 * avg_competitor_price - b3 * available_listings, 2)

    return {
        "listing_id": listing_id,
        "optimal_price": optimal_price,
        "demand_index": demand_index,
        "avg_competitor_price": avg_competitor_price,
        "available_listings": available_listings
    }




def calculate_demand_index_for_location(location):
    """
    Helper function to calculate demand index for a specific location.
    """
    demand_index_data = calculate_demand_index()
    return demand_index_data.get(location, 0.5)  # Default to 0.5 if location not found

def calculate_demand_index():
    """
    Bereken de demand index per provincie: hoe minder dogsitters, hoe hoger de vraag.
    """
    # Fetch alle listings per provincie
    provinces = db.session.query(Listing.location, db.func.count(Listing.id)).group_by(Listing.location).all()

    # Bepaal min en max aantal dogsitters
    sitter_counts = [count for _, count in provinces]
    max_sitters = max(sitter_counts) if sitter_counts else 1  # Vermijd delen door nul

    # Demand index berekenen
    demand_index = {}
    for location, count in provinces:
        demand_index[location] = round((max_sitters - count) / max_sitters, 2)

    return demand_index
