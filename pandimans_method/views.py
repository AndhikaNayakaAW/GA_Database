from django.shortcuts import render


def homepage(request):
    return render(request, 'homepage.html')


def login_view(request):
    return render(request, 'login.html')

def register(request):
    return render(request, 'register.html')
