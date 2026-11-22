from django.views import View
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate,login
from django.urls import reverse as r

class login_view(View):
    def get(sekf, request):
        
        # if request.user.is_authenticated:
        #     return redirect()
        
        return render(request, "login_template.html")