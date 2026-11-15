from django.contrib import admin
from django.db import models
from django.forms import Textarea,TextInput
from .models import  usreg, Inquiry, GalleryItem, CustomerReview, MenuCategory, MenuItem, MenuOrder

# 1. User Registration Admin
@admin.register(usreg)
class adminusreg(admin.ModelAdmin):
    list_display = ('id', 'fn', 'email', 'phoneno', 'un', 'psw', 'cpws')

# 2. Inquiry Admin
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_no', 'location', 'email', 'event_type', 'event_date', 'created_at')
    list_filter = ('event_type', 'event_date', 'created_at')
    search_fields = ('full_name', 'phone_no', 'email', 'location')
    ordering = ('-created_at',)

# 3. Customer Reviews Admin
@admin.register(CustomerReview)
class CustomerReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'rating', 'is_approved', 'created_at')
    list_editable = ('is_approved',)
    list_filter = ('is_approved', 'rating')

# 4. Gallery Admin
@admin.register(GalleryItem)
class GalleryAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'media_type')
    list_filter = ('category', 'media_type')
    search_fields = ('title',)

# 5. Menu Category Admin
@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_price')
    prepopulated_fields = {'slug': ('name',)}

# 6. Menu ITEM Admin (BIGGER TEXT BOXES)
@admin.register(MenuItem)
class MenuItem(admin.ModelAdmin):
    list_display = ('item_name', 'category', 'extra_price', 'is_available')


formfield_overrides = {
    # This makes the Item Name (CharField) wider and taller
    models.CharField: {
        'widget': TextInput(attrs={
            'style': 'width: 100%; max-width: 800px; height: 45px; font-size: 18px; font-weight: bold; border: 2px solid #b89564;'
        })
    },
    # This keeps the Description or other TextFields large if you have them
    models.TextField: {
        'widget': Textarea(attrs={'rows': 5, 'cols': 80, 'style': 'width: 100%; max-width: 800px;'})
    },
}

from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.core.mail import send_mail
from django.conf import settings
from .models import MenuOrder  # Ensure this matches your app structure


@admin.register(MenuOrder)
class MenuOrderAdmin(admin.ModelAdmin):  # Renamed to MenuOrderAdmin
    list_display = ('id', 'user', 'category', 'event_date', 'total_amount', 'status')

    formfield_overrides = {
        models.TextField: {
            'widget': Textarea(attrs={'rows': 15, 'cols': 100, 'style': 'width: 100%; border: 2px solid #b89564;'})
        },
    }

    def save_model(self, request, obj, form, change):
        # Detect if status changed to 'rejected'
        if change and 'status' in form.changed_data and obj.status == 'rejected':
            # Pass 'request' so we can show success/error messages in the UI
            self.send_rejection_email(request, obj)

        super().save_model(request, obj, form, change)

    def send_rejection_email(self, request, order):
        subject = f"Update regarding your Order #{order.id} - The Hungry Palette"

        message = (
            f"Dear {order.user.username},\n\n"
            f"We regret to inform you that your order for the {order.category} "
            f"scheduled for {order.event_date} has been rejected.\n\n"
            f"REFUND STATUS: A full refund of ₹{order.total_amount} has been initiated "
            f"to your original payment method. It may take 5-7 business days to reflect.\n\n"
            f"Warm regards,\nThe Hungry Palette Team"
        )

        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [order.user.email],
                fail_silently=False,
            )
            # Notify the Admin that the email was actually sent
            self.message_user(request, f"Rejection email sent to {order.user.email}")
        except Exception as e:
            # Show the error in the Django Admin red box
            self.message_user(request, f"Email failed: {e}", level='ERROR')

# admin.py
from .models import CustomizedOrder

@admin.register(CustomizedOrder)
class CustomizedOrderAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'event_date', 'total_price', 'status')
    list_filter = ('status', 'event_date')
    search_fields = ('customer_name', 'email')
    # This allows the admin to change status/notes easily
    fields = ('customer_name', 'email', 'event_date', 'guests', 'selected_items', 'total_price', 'advance_amount', 'status', 'admin_note')

    # Inside admin.py under CustomizedOrderAdmin
    def save_model(self, request, obj, form, change):
        if change:  # Only if updating an existing order
            if obj.status == 'Confirmed':
                subject = "Booking Confirmed: Your Event with The Hungry Palette"

                msg = f"""
            Dear {obj.customer_name},

            We are delighted to inform you that your customized catering order for {obj.event_date} has been officially CONFIRMED! 

            Thank you for choosing The Hungry Palette to be a part of your special occasion. We have successfully received your menu selection and are already preparing to deliver an exceptional culinary experience for your {obj.guests} guests.

            --- EVENT SUMMARY ---
            Event Date: {obj.event_date}
            Guest Count: {obj.guests}
            Total Quote: ₹{obj.total_price:,.2f}
            Advance Paid: ₹{obj.advance_amount:,.2f}

            --- WHAT’S NEXT? ---
            Our Event Management Team will reach out to you 48 hours before the event to finalize the logistics and setup requirements. In the meantime, if you have any adjustments or questions, please do not hesitate to contact us.

            We look forward to making your event truly flavor-full!

            Warm regards,

            The Event Management Team
            The Hungry Palette
            Phone: +91 9387654279
            Email: hungrypalette@gmail.com
            """
            elif obj.status == 'Rejected':
                subject = f"Update regarding your inquiry - The Hungry Palette"

                msg = f"""
                Dear {obj.customer_name},

                Thank you for reaching out to The Hungry Palette and for your interest in our bespoke catering services.

                After reviewing our schedule for {obj.event_date}, we regret to inform you that we are unable to fulfill your customized order at this time due to prior commitments and full booking capacity.

                We understand how important your event is, and we apologize for any inconvenience this may cause. We would love the opportunity to serve you in the future—please feel free to reach out to us for any upcoming occasions.

                Warm regards,

                The Event Management Team
                The Hungry Palette
                Phone: +91 9387654279
                Email: hungrypalette@gmail.com
                """
        elif obj.status == 'Date Change Requested':
            msg = f"""
           Dear {obj.customer_name},

           Thank you for choosing The Hungry Palette. 

           We have received your custom menu inquiry for {obj.event_date}. Currently, our team is fully committed on that specific date; however, we do have availability on nearby dates and would be delighted to host your event then.

           Admin Note: {obj.admin_note if obj.admin_note else "Please contact us to discuss alternative timing."}

           Best regards,
           The Hungry Palette Team
               """