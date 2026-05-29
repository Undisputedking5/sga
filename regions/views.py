from django.shortcuts import render

# Create your views here.
def regions(request):
    return render(request, 'regions.html')