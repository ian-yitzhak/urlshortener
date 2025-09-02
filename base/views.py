import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django_ratelimit.decorators import ratelimit
from user_agents import parse
from .models import URL, Click

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def parse_user_agent(user_agent_string):
    user_agent = parse(user_agent_string)
    return {
        'browser': f"{user_agent.browser.family} {user_agent.browser.version_string}",
        'os': f"{user_agent.os.family} {user_agent.os.version_string}",
        'device': user_agent.device.family
    }

def home(request):
    recent_urls = URL.objects.filter(is_active=True)[:5]
    total_urls = URL.objects.filter(is_active=True).count()
    total_clicks = Click.objects.count()
    
    context = {
        'recent_urls': recent_urls,
        'total_urls': total_urls,
        'total_clicks': total_clicks,
    }
    return render(request, 'shortener/home.html', context)

@ratelimit(key='ip', rate='10/m', method='POST')
@require_http_methods(["GET", "POST"])
def create_short_url(request):
    if request.method == 'POST':
        original_url = request.POST.get('original_url', '').strip()
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        custom_code = request.POST.get('custom_code', '').strip()
        expires_in_days = request.POST.get('expires_in_days')
        
        if not original_url:
            messages.error(request, 'Please enter a valid URL')
            return redirect('home')
        
        # Add protocol if missing
        if not original_url.startswith(('http://', 'https://')):
            original_url = 'https://' + original_url
        
        try:
            url_obj = URL(
                original_url=original_url,
                title=title,
                description=description,
                created_by=request.user if request.user.is_authenticated else None
            )
            
            # Handle custom short code
            if custom_code:
                if URL.objects.filter(short_code=custom_code).exists():
                    messages.error(request, 'Custom code already exists. Please choose another.')
                    return redirect('home')
                url_obj.short_code = custom_code
            
            # Handle expiration
            if expires_in_days:
                try:
                    days = int(expires_in_days)
                    url_obj.expires_at = timezone.now() + timedelta(days=days)
                except ValueError:
                    pass
            
            url_obj.save()
            
            messages.success(request, f'Short URL created: {url_obj.get_short_url()}')
            return redirect('url_detail', short_code=url_obj.short_code)
            
        except Exception as e:
            messages.error(request, f'Error creating short URL: {str(e)}')
            return redirect('home')
    
    return redirect('home')

def redirect_url(request, short_code):
    url_obj = get_object_or_404(URL, short_code=short_code, is_active=True)
    
    if url_obj.is_expired():
        return render(request, 'shortener/expired.html', {'url': url_obj})
    
    # Record click analytics
    user_agent_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent_data = parse_user_agent(user_agent_string)
    
    click = Click.objects.create(
        url=url_obj,
        ip_address=get_client_ip(request),
        user_agent=user_agent_string,
        referer=request.META.get('HTTP_REFERER'),
        browser=user_agent_data['browser'],
        os=user_agent_data['os'],
        device=user_agent_data['device']
    )
    
    # Update URL click count
    url_obj.increment_click()
    
    return HttpResponseRedirect(url_obj.original_url)

def url_detail(request, short_code):
    url_obj = get_object_or_404(URL, short_code=short_code)
    recent_clicks = url_obj.clicks.all()[:10]
    
    # Analytics data for charts
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    
    # Clicks over time (last 30 days)
    daily_clicks = []
    for i in range(30):
        date = now - timedelta(days=29-i)
        count = url_obj.clicks.filter(clicked_at__date=date.date()).count()
        daily_clicks.append({
            'date': date.strftime('%m/%d'),
            'count': count
        })
    
    # Browser stats
    browser_stats = url_obj.clicks.values('browser').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # OS stats
    os_stats = url_obj.clicks.values('os').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    context = {
        'url': url_obj,
        'recent_clicks': recent_clicks,
        'daily_clicks': json.dumps(daily_clicks),
        'browser_stats': browser_stats,
        'os_stats': os_stats,
    }
    return render(request, 'shortener/url_detail.html', context)

@login_required
def my_urls(request):
    urls = URL.objects.filter(created_by=request.user, is_active=True)
    paginator = Paginator(urls, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'shortener/my_urls.html', context)

def analytics_dashboard(request):
    # Overall statistics
    total_urls = URL.objects.filter(is_active=True).count()
    total_clicks = Click.objects.count()
    today_clicks = Click.objects.filter(clicked_at__date=timezone.now().date()).count()
    
    # Top URLs by clicks
    top_urls = URL.objects.filter(is_active=True).order_by('-click_count')[:10]
    
    # Recent activity
    recent_clicks = Click.objects.select_related('url')[:20]
    
    context = {
        'total_urls': total_urls,
        'total_clicks': total_clicks,
        'today_clicks': today_clicks,
        'top_urls': top_urls,
        'recent_clicks': recent_clicks,
    }
    return render(request, 'shortener/analytics.html', context)

# API endpoint for creating URLs via AJAX
@csrf_exempt
@ratelimit(key='ip', rate='20/m', method='POST')
def api_create_url(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            original_url = data.get('url', '').strip()
            
            if not original_url:
                return JsonResponse({'error': 'URL is required'}, status=400)
            
            if not original_url.startswith(('http://', 'https://')):
                original_url = 'https://' + original_url
            
            url_obj = URL.objects.create(
                original_url=original_url,
                created_by=request.user if request.user.is_authenticated else None
            )
            
            return JsonResponse({
                'short_url': url_obj.get_short_url(),
                'short_code': url_obj.short_code,
                'original_url': url_obj.original_url
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)