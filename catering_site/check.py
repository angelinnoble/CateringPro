from CateringPro.catering_site import settings
import google.generativeai as genai
from django.conf import settings

# Use your actual API key here
genai.configure(api_key=settings.GEMINI_API_KEY)

print("--- Searching for Available Models ---")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"FOUND: {m.name}")
except Exception as e:
    print(f"Error: {e}")