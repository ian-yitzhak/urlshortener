import random
import string
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

class URL(models.Model):
    original_url = models.URLField(max_length=2000)
    short_code = models.CharField(max_length=10, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    
    # Analytics fields
    last_clicked = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['short_code']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.short_code} -> {self.original_url[:50]}..."

    def save(self, *args, **kwargs):
        if not self.short_code:
            self.short_code = self.generate_short_code()
        super().save(*args, **kwargs)

    def generate_short_code(self):
        length = 6
        characters = string.ascii_letters + string.digits
        while True:
            code = ''.join(random.choice(characters) for _ in range(length))
            if not URL.objects.filter(short_code=code).exists():
                return code

    def get_absolute_url(self):
        return reverse('redirect_url', kwargs={'short_code': self.short_code})

    def get_short_url(self):
        from django.conf import settings
        domain = getattr(settings, 'DOMAIN', 'http://localhost:8000')
        return f"{domain}/{self.short_code}"

    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    def increment_click(self):
        self.click_count += 1
        self.last_clicked = timezone.now()
        self.save(update_fields=['click_count', 'last_clicked'])

class Click(models.Model):
    url = models.ForeignKey(URL, on_delete=models.CASCADE, related_name='clicks')
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    referer = models.URLField(blank=True, null=True, max_length=2000)
    
    # Parsed user agent data
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    device = models.CharField(max_length=100, blank=True)
    
    # Location data (you can integrate with GeoIP)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-clicked_at']
        indexes = [
            models.Index(fields=['url', '-clicked_at']),
            models.Index(fields=['clicked_at']),
        ]

    def __str__(self):
        return f"Click on {self.url.short_code} at {self.clicked_at}"
