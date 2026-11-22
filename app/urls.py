from django.urls import path
from .views.login_view import login_view
from .views.cadastro_view import cadastro_view
urlpatterns = [
    path('', login_view.as_view(), name="login"),
    path('cadastro/',cadastro_view.as_view(), name="cadastro")
]
