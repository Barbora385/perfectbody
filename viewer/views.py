import json

import requests
from unidecode import unidecode
from django.contrib.auth.models import Group
from django.shortcuts import render, get_object_or_404, redirect

from django.http import JsonResponse

from accounts.models import UserProfile, Address
from products.models import Product


def clean_city_name(city):
    return ''.join(c for c in city if not c.isdigit()).strip()

def translate_weather_description(description):
    translations = {
        "Sunny": "Slunečno",
        "Cloudy": "Zataženo",
        "Partly cloudy": "Částečně zataženo",
        "Mist": "Mlha",
        "Rain": "Déšť",
        "Snow": "Sníh",
        "Thunderstorm": "Bouřka",
        "Fog": "Mlha",
        "Clear": "Jasno",
        "Overcast": "Převážně zataženo",
    }
    return translations.get(description, description)

def get_weather(city):
    url = f"https://wttr.in/{city}?format=j1"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            current_condition = data['current_condition'][0]
            return {
                'city': city,
                'temperature': current_condition['temp_C'],
                'description': translate_weather_description(current_condition['weatherDesc'][0]['value']),
                'humidity': current_condition['humidity'],
            }
        else:
            print(f"Chyba API Wttr.in: {response.status_code}")
    except Exception as e:
        print(f"Chyba při získávání počasí: {e}")
    return None

def home(request):
    name_day = get_name_day()

    default_cities = ['Brno', 'Praha', 'Ostrava']
    weather_data = []

    if request.user.is_authenticated:
        address = Address.objects.filter(user=request.user).order_by('-id').first()
        if address:
            user_city = clean_city_name(address.city)
            weather = get_weather(user_city)
            if weather:
                weather_data.append(weather)

    if not weather_data:
        for city in default_cities:
            weather = get_weather(city)
            if weather:
                weather_data.append(weather)

    return render(request, 'home.html', {'name_day': name_day, 'weather_data': weather_data})

def get_name_day():
    try:
        response = requests.get('https://nameday.abalin.net/api/V1/today?country=cz')
        if response.status_code == 200:
            data = response.json()
            if 'nameday' in data and 'cz' in data['nameday']:
                return data['nameday']['cz']
            else:
                return "Není dostupné"
        else:
            return "API nedostupné"
    except Exception as e:
        print(f"Chyba při získávání jmenin: {e}")
        return "Chyba"


def products(request):
    products = Product.objects.filter(product_type='merchantdise')
    print(products)
    return render(request, 'products.html', {'products': products})

def product(request, pk):
    if Product.objects.filter(id=pk):
        product_detail = Product.objects.get(id=pk)
        context = {'product': product_detail}
        return render(request, "product.html", context)
    return products(request)

def services(request):
    services = Product.objects.filter(product_type='service')
    return render(request, 'services.html', {"services": services})

def service(request, pk):
    if Product.objects.filter(id=pk):
        service_detail = Product.objects.get(id=pk)
        context = {'service': service_detail}
        return render(request, "service.html", context)
    return services(request)

def trainers(request):
    return render(request, 'trainers.html')

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect

def add_to_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)
    product = get_object_or_404(Product, id=product_id)

    if product_id_str in cart:
        cart[product_id_str]['quantity'] += 1
    else:
        cart[product_id_str] = {
            'name': product.product_name,
            'price': float(product.price),
            'quantity': 1,
        }

    request.session['cart'] = cart

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_total = sum(item['quantity'] * item['price'] for item in cart.values())
        return JsonResponse({
            'success': True,
            'cart': cart,
            'cart_total': f"{cart_total:.2f}"
        })
    else:
        return redirect('cart')


def view_cart(request):
    cart = request.session.get('cart', {})
    for product_id, item in cart.items():
        item['total'] = item['quantity'] * item['price']
    total = sum(item['quantity'] * item['price'] for item in cart.values())
    return render(request, 'cart.html', {"cart": cart, "total": total})



def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)

    if product_id_str in cart:
        del cart[product_id_str]

    request.session['cart'] = cart
    return redirect('cart')

def update_cart(request, product_id):
    cart = request.session.get('cart', {})
    product_id_str = str(product_id)

    if product_id_str in cart:
        new_quantity = int(request.POST.get('quantity', 1))
        if new_quantity > 0:
            cart[product_id_str]['quantity'] = new_quantity
        else:
            del cart[product_id_str]

    request.session['cart'] = cart
    return redirect('cart')



def update_cart_ajax(request, product_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart = request.session.get('cart', {})
        product_id_str = str(product_id)

        if product_id_str in cart:
            try:
                data = json.loads(request.body)
                new_quantity = int(data.get('quantity', 1))
                if new_quantity > 0:
                    cart[product_id_str]['quantity'] = new_quantity
                    request.session['cart'] = cart
                    total = sum(item['quantity'] * item['price'] for item in cart.values())
                    item_total = cart[product_id_str]['quantity'] * cart[product_id_str]['price']

                    response = {
                        'success': True,
                        'item_total': f"{item_total:.2f}",
                        'cart_total': f"{total:.2f}"
                    }
                    print("Response JSON:", response)
                    return JsonResponse(response)

                else:
                    del cart[product_id_str]
                    request.session['cart'] = cart
                    total = sum(item['quantity'] * item['price'] for item in cart.values())

                    response = {'success': True, 'cart_total': f"{total:.2f}"}
                    print("Response JSON:", response)
                    return JsonResponse(response)

            except (ValueError, KeyError) as e:
                error_response = {'success': False, 'error': 'Invalid data'}
                print("Error JSON:", error_response)
                return JsonResponse(error_response)
        else:
            error_response = {'success': False, 'error': 'Product not found'}
            print("Error JSON:", error_response)
            return JsonResponse(error_response)

    error_response = {'success': False, 'error': 'Invalid request'}
    print("Error JSON:", error_response)
    return JsonResponse(error_response)





def user_profile_view(request, username):
    user = get_object_or_404(UserProfile, username=username)
    is_trainer = user.groups.filter(name='trainer').exists()
    if request.user.is_authenticated and request.user == user:
        return redirect('profile')
    return render(request, 'user_profile.html', {'user': user, 'is_trainer': is_trainer})

def get_name_day():
    try:
        response = requests.get('https://nameday.abalin.net/api/V1/today?country=cz')
        if response.status_code == 200:
            data = response.json()
            if 'nameday' in data and 'cz' in data['nameday']:
                return data['nameday']['cz']
            else:
                return "Není dostupné"
        else:
            return "API nedostupné"
    except Exception as e:
        return f"Chyba: {e}"


def normalize_for_search(text):
    return unidecode(text).lower()

def search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        # Pokud není dotaz, zobrazíme prázdné výsledky
        return render(request, 'search_results.html', {
            'query': query,
            'products': [],
            'services': [],
            'trainers': [],
        })

    # Normalizace dotazu
    normalized_query = normalize_for_search(query)

    # Hledání v produktech
    products = [
        product for product in Product.objects.filter(product_type='merchantdise')
        if normalized_query in normalize_for_search(product.product_name)
        or normalized_query in normalize_for_search(product.product_description or "")
    ]

    # Hledání ve službách
    services = [
        service for service in Product.objects.filter(product_type='service')
        if normalized_query in normalize_for_search(service.product_name)
        or normalized_query in normalize_for_search(service.product_description or "")
    ]

    # Hledání u trenérů
    trainers_group = Group.objects.filter(name='trainer').first()
    if trainers_group:
        trainers = [
            trainer for trainer in UserProfile.objects.filter(groups__in=[trainers_group])
            if normalized_query in normalize_for_search(trainer.first_name)
            or normalized_query in normalize_for_search(trainer.last_name)
        ]
    else:
        trainers = []

    return render(request, 'search_results.html', {
        'query': query,
        'products': products,
        'services': services,
        'trainers': trainers,
    })

