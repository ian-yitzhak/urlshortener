from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.create_short_url, name='create_short_url'),
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('my-urls/', views.my_urls, name='my_urls'),
    path('api/create/', views.api_create_url, name='api_create_url'),
    path('<str:short_code>/', views.redirect_url, name='redirect_url'),
    path('<str:short_code>/stats/', views.url_detail, name='url_detail'),
]