from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('taste/', views.our_taste, name='our_taste'),
    path('why-us/', views.why_us, name='why_us'),
    path('services/', views.services, name='services_page'),
    path('occasions/', views.occasions, name='occasions'),
    path('gallery/', views.gallery, name='gallery'),
    path('contact/', views.contact, name='contact_page'),
    path('save-inquiry/', views.save_inquiry, name='save_inquiry'),
    path('pp/', views.registration, name='register'),
    path('bb/',views.login,name='login'),
    path('ai-muse/', views.ai_planner, name='ai_muse'),
    path('logout/', views.logout_view, name='logout'),
    path('submit-review/', views.submit_review, name='submit_review'),
    path('ai-planner/', views.ai_planner, name='ai_planner'),
    path('menu/select/<slug:slug>/', views.menu_selection, name='menu_selection'),
    path('booking-confirmed/<int:order_id>/', views.booking_success, name='booking_success'),
    path('order-summary/<int:order_id>/', views.order_summary, name='order_summary'),
    path('pay-balance/<int:order_id>/', views.pay_balance, name='pay_balance'),
    path('taste-experience/', views.taste_experience, name='taste_experience'),
    path('booking-confirmed/', views.booking_success, name='booking_success'),
    path('booking-confirmed/<int:order_id>/', views.booking_success, name='booking_success'),
    path('booking-confirmed/', views.booking_success, name='inquiry_success'),
]
