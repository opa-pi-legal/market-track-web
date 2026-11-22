from django.urls import path
from .views.login_view import login_view
urlpatterns = [
    path('', login_view.as_view())
]
