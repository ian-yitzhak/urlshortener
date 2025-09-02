Django URL shortener with analytics.

Setup
bashgit clone https://github.com/ian-yitzhak/urlshortener.git
cd urlshortener
pip install Django django-extensions user-agents django-ratelimit
python manage.py migrate
python manage.py runserver
Visit http://localhost:8000

Features

Shorten URLs with custom codes
Click analytics and tracking
Clean Bootstrap interface
Rate limiting protection