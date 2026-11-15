from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.db.models import Count  # Required for get_booked_dates
from decimal import Decimal
from google import genai


def ai_planner(request):
    if request.method == "POST":
        user_prompt = request.POST.get('prompt')
        try:
            # Force v1 stable API
            client = genai.Client(
                api_key=settings.GEMINI_API_KEY,
                http_options={'api_version': 'v1'}
            )

            # TRY 1: The Modern 2026 Standard
            try:
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=user_prompt
                )
            except:
                # TRY 2: The 2.5 Flash (If available in your region)
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=user_prompt
                    )
                except:
                    # TRY 3: The 1.5 Flash (Old stable)
                    response = client.models.generate_content(
                        model='gemini-1.5-flash',
                        contents=user_prompt
                    )

            return JsonResponse({'suggestion': response.text})

        except Exception as e:
            print(f"--- SYSTEM ERROR: {str(e)} ---")
            return JsonResponse({'error': "The Muse is adjusting her veil."}, status=500)

    return render(request, 'services/ai_muse.html')
# Models
from .models import MenuCategory, MenuItem, MenuOrder, Inquiry, GalleryItem, CustomerReview,CustomizedOrder
from services.models import usreg


# ------------------ Availability Helper ------------------

def get_booked_dates(request):
    """
    Returns dates that already have 2 or more bookings.
    Used by the calendar to disable 'Full' dates.
    """
    # Filter MenuOrder to find dates with 2 or more entries
    booked_dates = MenuOrder.objects.values('event_date') \
        .annotate(dcount=Count('event_date')) \
        .filter(dcount__gte=2) \
        .values_list('event_date', flat=True)

    # Format dates as strings for JS: "YYYY-MM-DD"
    date_list = [d.strftime("%Y-%m-%d") for d in booked_dates if d]
    return JsonResponse(date_list, safe=False)


# ------------------ Review & Success ------------------

def submit_review(request):
    if request.method == "POST":
        name = request.POST.get('name')
        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text')

        if name and review_text:
            CustomerReview.objects.create(
                name=name,
                rating=rating,
                review_text=review_text,
                is_approved=False
            )
            messages.success(request, "Your review has been submitted and is awaiting approval!")
        else:
            messages.error(request, "Please provide both a name and your review.")
    return redirect('home')


def booking_success(request, order_id=None):
    if order_id:
        order = get_object_or_404(MenuOrder, id=order_id)
        balance = order.total_amount - order.advance_paid
        context = {'order': order, 'balance': balance}
    else:
        total = Decimal(str(request.session.get('temp_total', 0)))
        advance = Decimal(str(request.session.get('temp_advance', 0)))
        context = {
            'total': total,
            'advance': advance,
            'balance': total - advance,
            'name': request.session.get('temp_name', 'Valued Customer'),
            'order': None
        }
    return render(request, 'services/booking_success.html', context)


# ------------------ Order Management ------------------

def pay_balance(request, order_id):
    order = get_object_or_404(MenuOrder, id=order_id)
    if order.is_fully_paid:
        messages.info(request, "This order is already fully paid.")
        return redirect('order_summary', order_id=order.id)

    balance_amount = order.total_amount - order.advance_paid

    if request.method == "POST":
        order.is_fully_paid = True
        order.status = "Confirmed"
        order.save()
        messages.success(request, f"Payment Successful! Final balance cleared.")
        return redirect('order_summary', order_id=order.id)

    return render(request, 'pay_balance.html', {'order': order, 'balance': balance_amount})


def order_summary(request, order_id):
    order = get_object_or_404(MenuOrder, id=order_id)

    # Custom Security Check: Match session ID to Order User ID
    session_user_id = request.session.get('id')
    if not session_user_id or (order.user and order.user.id != session_user_id):
        messages.error(request, "You do not have permission to view this receipt.")
        return redirect('home')

    return render(request, 'order_summary.html', {'order': order})


# ------------------ Menu Selection ------------------

def menu_selection(request, slug):
    user_id = request.session.get('id')
    if not user_id:
        messages.error(request, "Please login to access the menu.")
        return redirect('login')

    category = get_object_or_404(MenuCategory, slug=slug)
    included = category.items.filter(is_extra=False)
    extras = category.items.filter(is_extra=True)

    if request.method == "POST":
        c_name = request.POST.get('guest_name')
        c_email = request.POST.get('guest_email')
        event_date = request.POST.get('event_date')
        guest_count = int(request.POST.get('guest_count', 1))

        # 1. FINAL AVAILABILITY CHECK (Server-side)
        existing_bookings = MenuOrder.objects.filter(event_date=event_date).count()
        if existing_bookings >= 2:
            messages.error(request, "Sorry, this date just became fully booked. Please select another.")
            return redirect('menu_selection', slug=slug)

        # 2. CHECK EXTRAS AVAILABILITY
        selected_extra_ids = request.POST.getlist('extra_items')
        unavailable_items = MenuItem.objects.filter(id__in=selected_extra_ids, is_available=False)

        if unavailable_items.exists():
            item_names = ", ".join([item.item_name for item in unavailable_items])
            messages.error(request, f"Sorry, {item_names} is currently unavailable.")
            return redirect('menu_selection', slug=slug)

        # 3. CALCULATE
        total = Decimal(str(category.base_price)) * guest_count
        selected_extras_objects = []
        for item_id in selected_extra_ids:
            item = MenuItem.objects.get(id=item_id)
            total += Decimal(str(item.extra_price)) * guest_count
            selected_extras_objects.append(item)

        advance = total * Decimal('0.25')
        user_obj = usreg.objects.filter(id=user_id).first()

        # 4. CREATE ORDER
        new_order = MenuOrder.objects.create(
            user=user_obj,
            category=category,
            event_date=event_date,
            guest_count=guest_count,
            total_amount=total,
            advance_paid=advance,
            custom_requests=request.POST.get('custom_food_notes', ''),
            is_paid=True,
            is_fully_paid=False,
            status='Pending'
        )
        if selected_extras_objects:
            new_order.extra_items.set(selected_extras_objects)

        # 5. NOTIFY
        send_order_confirmation_email(c_name, c_email, category.name, event_date, advance)

        messages.success(request, "Booking Successful!")
        return redirect('booking_success', order_id=new_order.id)

    return render(request, 'services/menu_selection.html', {
        'category': category, 'included': included, 'extras': extras
    })


# ------------------ Auth & Registration ------------------

def registration(request):
    if request.method == "POST":
        fn = request.POST.get('fn')
        un = request.POST.get('un')
        psw = request.POST.get('psw')
        cpws = request.POST.get('cpws')

        if psw != cpws:
            messages.error(request, "Passwords do not match.")
        elif usreg.objects.filter(un=un).exists():
            messages.error(request, "Username already taken.")
        else:
            usreg.objects.create(
                fn=fn, email=request.POST.get('email'),
                phoneno=request.POST.get('phoneno'), un=un, psw=psw
            )
            messages.success(request, "Account created! Please login.")
            return redirect('login')
    return render(request, 'services/registration.html')


def login(request):
    if request.session.get('id'):
        return redirect('home')

    if request.method == "POST":
        username = request.POST.get('un')
        password = request.POST.get('psw')
        u = usreg.objects.filter(un=username, psw=password).first()

        if u:
            request.session['id'] = u.id
            request.session['name'] = u.fn
            request.session['right'] = u.rights
            request.session.modified = True

            next_url = request.POST.get('next')
            if u.rights == "admin":
                return redirect("/sap/")
            return redirect(next_url if next_url else 'home')

        messages.error(request, "Invalid username or password.")
    return render(request, "services/login.html", {'next': request.GET.get('next', '')})


def logout_view(request):
    request.session.flush()
    return redirect('/')


# ------------------ Emails & AI ------------------

def send_order_confirmation_email(name, email, package, date, advance):
    subject = "Booking Confirmed - The Hungry Palette"
    message = f"Hi {name},\n\nYour booking for {package} on {date} is confirmed.\nAdvance Paid: ₹{advance}."
    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
    except Exception as e:
        print(f"Email Error: {e}")

# ------------------ Static Wrappers ------------------
def home(request): return render(request, 'services/index.html')


def our_taste(request): return render(request, 'services/taste.html')


def why_us(request): return render(request, 'services/why_us.html')


def gallery(request):
    items = GalleryItem.objects.all().order_by('-uploaded_at')
    return render(request, 'services/gallery.html', {'items': items})


def taste_experience(request):
    # 1. Indentation Fix: The session check must be inside the function
    user_id = request.session.get('id')
    if not user_id:
        messages.error(request, "Please login to curate your Taste Experience.")
        return redirect('login')

    # 2. Indentation Fix: MENU_DATA must be indented to be part of the function
    MENU_DATA = {
        "WELCOME DRINK": [
            ("GINGER LIME", 40), ("MINT LIME", 40), ("RAW MANGO & LIME", 45),
            ("STRAWBERRY MIST", 60), ("CURRACO BLUE", 70), ("KIWI MIST", 70),
            ("ORANGE MIST", 60), ("MANGO PUNCH", 80), ("FRESH JUICE", 90),
            ("PASSION FRUIT", 110), ("BUTTER MILK", 30), ("LYCHEE", 85)
        ],
        "SNACKS": [
            ("MEAT BALLS", 120), ("CRISPY FRIED", 130), ("VEG SAMOSA", 25),
            ("SPRING ROLL", 45), ("PAKODA", 35), ("CHICKEN 65", 140),
            ("ASSORTED CANAPES", 90), ("FRENCH FRIES", 60)
        ],
        "SOUP": [
            ("SWEET CORN CHICKEN", 100), ("CREAM OF CHICKEN", 110), ("HOT & SOUR CHICKEN", 100),
            ("CHICKEN NOODLE SOUP", 95), ("CLEAR CHICKEN SOUP", 90), ("NADAN MUTTON SOUP", 150),
            ("CREAM OF TOMATO", 80), ("CREAM OF MUSHROOM", 110), ("CLEAR VEG SOUP", 75)
        ],
        "SALADS": [
            ("VEG CRUDITIES", 50), ("GREEN SALAD", 40), ("TOSSED SALAD", 50),
            ("CHANNA /ALOO CHAT", 60), ("BEAN SPROUTS SALAD", 70), ("VEG COCKTAIL SALAD", 80),
            ("MACRONI SALAD", 85), ("RUSSIAN SALAD", 95), ("KIMCHI SALAD", 80),
            ("HAWAIN SALAD", 110), ("CAESAR SALAD", 120), ("COLESLAW SALAD", 70),
            ("TOMATO ONION SALAD", 40), ("PASTA SALAD", 90), ("GREEK SALAD", 110)
        ],
        "FISH": [
            ("MEEN POLLICHATHU", 280), ("MASALA FRIED FISH", 180), ("FISH MOILY / MAPPAS", 220),
            ("MALABAR FISH CURRY", 200), ("KERALA FISH CURRY", 190), ("ALAPPEY FISH CURRY", 210),
            ("MEEN MULAGITTATHU", 190), ("MEEN MANGA CURRY", 210), ("MEEN VARUTHARACHATHU", 210),
            ("FRIED FISH MASALA", 200), ("FISH MANCHURIAN", 180), ("CHILLY FISH", 180),
            ("FISH SALT N PEPPER", 190), ("CRUMB FRIED FISH", 200), ("TAWA GRILLED FISH", 250),
            ("FISH ROAST", 210), ("GRILLED FISH CONTI", 280), ("BAKED FISH", 260)
        ],
        "MUTTON": [
            ("NADAN MUTTON CURRY", 320), ("MUTTON PIRALAN", 330), ("MUTTON ROAST", 340),
            ("MUTTON ROGANJOSH", 350), ("MUTTON STEW", 320), ("MUTTON KORMA", 320),
            ("MUTTON VINDALOO", 330), ("MUTTON CHAPS", 350), ("PEPPER MUTTON ROAST", 340)
        ],
        "DUCK": [
            ("DUCK ROAST", 250), ("DUCK PIRALAN", 250), ("DUCK MAPPAS", 260),
            ("DUCK KUTTANADAN STYLE", 270), ("DUCK PEPPER FRY", 260), ("DUCK CURRY", 240)
        ],
        "CHICKEN": [
            ("NADAN CHICKEN CURRY", 180), ("MALABAR CHICKEN CURRY", 180),
            ("CHICKEN ROAST", 190), ("CHICKEN STEW", 180),
            ("CHICKEN PEPPER MASALA", 200), ("PEPPER CHICKEN DRY", 210),
            ("KOZHI PORICHATHU", 190), ("CHICKEN CHETTINADU", 200),
            ("BUTTER CHICKEN", 220), ("CHICKEN DO PYAZA", 210),
            ("CHILLY CHICKEN", 180), ("GARLIC CHICKEN", 190),
            ("GINGER CHICKEN", 190), ("SEZCHUWAN CHICKEN", 200),
            ("CHICKEN KHORMA", 210), ("TANDOOR CHICKEN", 260),
            ("GRILLED CHICKEN", 260), ("CHICKEN AMRITSARY", 230),
            ("CHICKEN AUGRATIN", 240), ("CHICKEN POTATO PIE", 220),
            ("KALI MURGH", 230), ("CHICKEN KASHA", 210),
            ("CHICKEN MAKHANI", 220), ("DRAGON CHICKEN", 210),
            ("DUM KA MURGH", 240), ("KADAI CHICKEN", 200),
            ("KASHMIRI CHICKEN", 220), ("RESHMI KEBAB", 250),
            ("ROASTED CHICKEN STUFF", 280), ("TANGERI KEBAB", 250),
            ("CHICKEN PIRATTU", 200), ("CHICKEN MAPPAS", 190)
        ],
        "BEEF": [
            ("NADAN BEEF FRY", 190), ("BEEF COCONUT FRY", 200), ("BEEF ULARTHU", 200),
            ("BEEF PEPPER FRY", 210), ("BEEF MASALA / ROAST", 190), ("CHILLY BEEF", 180),
            ("BEEF VARUTHARACHATHU / STIR FRIED BEEF", 210), ("SECHZWAN BEEF", 200),
            ("BEEF LASSAGNE", 250), ("BEEF WITH OYSTER", 240), ("BEEF PIRALAN", 210),
            ("BEEF CRISPY FRY", 220), ("BEEF VINDALOO", 200), ("BEEF CHAPS", 230), ("BEEF DRY FRY", 210)
        ],
        "PORK": [
            ("NADAN PORK CURRY", 210), ("PORK VARUTHARACHATHU", 220), ("PORK ROAST", 220),
            ("PORK COCONUT FRY", 230), ("CHILLY PORK", 210), ("PORK VINDALOO", 220)
        ],
        "VEGETARIAN": [
            ("THORAN", 40), ("PULISSERY", 50), ("VEG STEW", 90), ("ALOO GOBI", 110),
            ("PANEER BUTTER", 160), ("PALAK PANEER", 160), ("VEG AUGRATIN", 150)
        ],
        "RICE & BIRIYANI": [
            ("MUTTON BIRIYANI", 350), ("CHICKEN BIRIYANI", 220), ("GHEE RICE", 120),
            ("VEG PULAO", 110), ("KASHMIRI PULAO", 150), ("KERALA RICE", 60)
        ],
        "BREADS": [
            ("APPAM", 15), ("IDIYAPPAM", 15), ("KALLAPPAM", 15), ("PATHIRI", 12),
            ("KERALA PARATHA", 18), ("CHAPPATHY", 12), ("COIN PARATHA", 20)
        ],
        "NADAN COUNTER": [
            ("KAPPA BIRIYANI", 120), ("PIDI WITH KOZI CURRY", 150), ("KAPPA WITH FISH CURRY", 160),
            ("PUTTU WITH BEEF ROAST", 180)
        ],
        "DESSERTS": [
            ("ASSORTED PASTRY", 70), ("FRESH FRUIT TRIFFLE", 90), ("CHOCOLATE MOUSSE", 110),
            ("CHOCO BROWNIE", 80), ("VANILLA ICECREAM", 40), ("PAYASAM", 60),
            ("STRAWBERRY CHEESE CAKE", 150), ("CUT FRUITS", 70)
        ],
    }

    if request.method == "POST":
        c_name = request.POST.get('name')
        c_email = request.POST.get('email')
        event_date = request.POST.get('date')
        guests = int(request.POST.get('guests', 1))
        selected_foods = request.POST.getlist('selected_foods')  # List of names

        try:
            total_price = float(request.POST.get('final_total_val', 0))
        except:
            total_price = 0

        advance_price = total_price * 0.25

        # --- NEW: SAVE TO DATABASE ---
        new_custom_order = CustomizedOrder.objects.create(
            customer_name=c_name,
            email=c_email,
            event_date=event_date,
            guests=guests,
            selected_items=", ".join(selected_foods),  # Turn list into a string
            total_price=total_price,
            advance_amount=advance_price
        )

        # Email Preparation
        subject = f"Custom Menu Quote - {c_name}"
        message = f"""
        Dear {c_name},

        Thank you for choosing The Hungry Palette! We have received your menu inquiry.

        --- EVENT SUMMARY ---
        Guest Count: {guests}
        Total Estimated Bill: ₹{total_price:,.2f}
        Advance Due (25%): ₹{advance_price:,.2f}

        --- CONTACT INFORMATION ---
        Phone: +91 9387654279
        Email: hungrypalette@gmail.com

        --- REFUND & CANCELLATION POLICY ---
        • Booking confirmed on 25% advance.
        • Cancellation before 90 days: 50% refund of advance.
        • Cancellation within 30-90 days: 25% refund of advance.
        • Cancellation within 30 days: Non-refundable.

        Warm regards,
        The Hungry Palette Team
        """

        try:
            send_mail(subject, message, settings.EMAIL_HOST_USER, [c_email])
        except Exception as e:
            print(f"EMAIL ERROR: {e}")

        # SAVE TO SESSION
        request.session['temp_total'] = total_price
        request.session['temp_advance'] = advance_price
        request.session['temp_name'] = c_name

        # Final Redirection
        return redirect('booking_success')

    # This handles the GET request to show the page
    return render(request, 'services/taste_experience.html', {'menu': MENU_DATA})
# Add this to your views.py
def services(request):
    return render(request, 'services/services.html')
# Add these to the bottom of your services/views.py

def occasions(request):
    return render(request, 'services/occasions.html')
def contact(request):
    """Handles the contact page and the inquiry form submission."""
    if request.method == "POST":
        fname = request.POST.get('fn')
        phone = request.POST.get('ph')
        loc = request.POST.get('loc')
        eml = request.POST.get('em')
        etype = request.POST.get('et')
        edate = request.POST.get('ed')
        msg = request.POST.get('msg')

        # Save to Database
        Inquiry.objects.create(
            full_name=fname,
            phone_no=phone,
            location=loc,
            email=eml,
            event_type=etype,
            event_date=edate,
            comment=msg
        )

        # Send Email Notification
        try:
            subject = "New Inquiry Received - The Hungry Palette"
            body = f"Hi {fname}, thank you for reaching out! We will contact you shortly."
            send_mail(subject, body, settings.EMAIL_HOST_USER, [eml])
        except Exception as e:
            print(f"Email Error: {e}")

        messages.success(request, "Your inquiry has been submitted successfully!")
        return redirect('contact_page')

    return render(request, 'services/contact.html')


def save_inquiry(request):
    """
    Handles quick inquiries from the footer or sidebar across multiple pages.
    """
    if request.method == "POST":
        # Get data from the POST request
        # Ensure these 'names' match your HTML form input names exactly!
        full_name = request.POST.get('name')
        phone = request.POST.get('phone')
        location = request.POST.get('location')
        email = request.POST.get('email')
        event_type = request.POST.get('event')
        event_date = request.POST.get('date')
        comment = request.POST.get('comment')

        # Create the record in the Inquiry table
        Inquiry.objects.create(
            full_name=full_name,
            phone_no=phone,
            location=location,
            email=email,
            event_type=event_type,
            event_date=event_date,
            comment=comment
        )

        messages.success(request, "Your inquiry has been sent! We will contact you shortly.")

    # Redirect back to the page the user was on
    return redirect(request.META.get('HTTP_REFERER', '/'))