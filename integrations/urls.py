from django.urls import path

from . import views

urlpatterns = [path("integrations/n8n/callback/", views.n8n_callback, name="n8n_callback")]
