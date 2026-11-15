from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
class Inquiry(models.Model):
    EVENT_CHOICES = [
        ('Wedding', 'Wedding'),
        ('Birthday', 'Birthday'),
        ('Corporate', 'Corporate'),
        ('Engagement', 'Engagement'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('DateChange', 'Requested Date Change'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )
    full_name = models.CharField(max_length=150) # This is 'full_name'
    phone_no = models.CharField(max_length=15)
    location = models.CharField(max_length=200)
    email = models.EmailField()
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    event_date = models.DateField()
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

@receiver(post_save, sender=Inquiry)
def notify_date_change(sender, instance, created, **kwargs):
    if instance.status == 'DateChange':
        subject = "Important Update: Your Event with The Hungry Palette"

        # CHANGED: 'instance.name' to 'instance.full_name'
        message = f"""
        Dear {instance.full_name},

        Thank you for reaching out to The Hungry Palette! 

        We have reviewed your request for {instance.event_date}. Unfortunately, our kitchen is fully booked and at maximum capacity for that specific date.

        We would still love to cater your event! Would you be open to moving your celebration to a different date? Please let us know if you have any flexibility, and we will do our best to accommodate you.

        Warmly,
        The Hungry Palette Team
        """

        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [instance.email],
            fail_silently=False,
        )

class FoodItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    image_url = models.URLField(blank=True)

    def __str__(self):
        return self.name

class usreg(models.Model):
    fn=models.CharField(max_length=50)
    email=models.CharField(max_length=100)
    phoneno=models.CharField(max_length=10)
    un=models.CharField(max_length=50, unique=True)
    psw=models.CharField(max_length=50)
    cpws=models.CharField(max_length=50)
    rights=models.CharField(max_length=50,default='user')


class GalleryItem(models.Model):
    CATEGORY_CHOICES = [
        ('Wedding', 'Wedding & Betrothal'),
        ('Corporate', 'Corporate Events'),
        ('Cultural', 'Cultural & Religious'),
        ('Private', 'Private Parties'),
    ]

    MEDIA_TYPE_CHOICES = [
        ('Image', 'Photo'),
        ('Video', 'Video'),
    ]

    title = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    image_file = models.ImageField(upload_to='gallery/photos/', blank=True, null=True)
    video_file = models.FileField(upload_to='gallery/videos/', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.category})"
class CustomerReview(models.Model):
    name = models.CharField(max_length=100)
    review_text = models.TextField()
    rating = models.IntegerField(default=5) # 1 to 5 stars
    is_approved = models.BooleanField(default=False) # Admin must check this
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.name} - Approved: {self.is_approved}"
class MenuCategory(models.Model):
    name = models.CharField(max_length=100)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    slug = models.SlugField(unique=True) # e.g., 'standard-menu'

    def __str__(self):
        return self.name

class MenuItem(models.Model):
        category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items')
        item_name = models.TextField(max_length=200)
        extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
        is_extra = models.BooleanField(default=False)  # True if it's an optional add-on
        is_available = models.BooleanField(default=True)

        # If you have a description field, it looks like this:
        description = models.TextField(blank=True, null=True)
        def __str__(self):
            return f"{self.item_name} ({self.category.name})"
class MenuOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),  # Add this
    ]
    # Linking to your custom 'usreg' model
    user = models.ForeignKey(usreg, on_delete=models.CASCADE, null=True, blank=True)

    category = models.ForeignKey(MenuCategory, on_delete=models.SET_NULL, null=True)
    custom_requests = models.TextField(null=True, blank=True)

    event_date = models.DateField()

    guest_count = models.PositiveIntegerField(default=1)

    # Use ONLY ONE extras field (recommended)
    extra_items = models.ManyToManyField(MenuItem, blank=True)

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    is_paid = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    is_fully_paid = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[('Pending', 'Pending'), ('Confirmed', 'Confirmed')],
        default='Pending'
    )

    def __str__(self):
        return f"Order {self.id} - {self.category.name if self.category else 'N/A'}"

class CustomizedOrder(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Rejected', 'Rejected'),
        ('Date Change Requested', 'Date Change Requested'),
    ]

    customer_name = models.CharField(max_length=255)
    email = models.EmailField()
    event_date = models.DateField()
    guests = models.IntegerField()
    selected_items = models.TextField() # Stores the list of food as text
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    advance_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending')
    admin_note = models.TextField(blank=True, null=True) # For the date change message
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Custom Order - {self.customer_name} ({self.event_date})"