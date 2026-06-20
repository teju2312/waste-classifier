from django.urls import path
from .views import HomeView, PredictView, HistoryView, PredictAPIView

urlpatterns = [
    path('',          HomeView.as_view(),       name='home'),
    path('predict/',  PredictView.as_view(),    name='predict'),
    path('history/',  HistoryView.as_view(),    name='history'),
    path('api/predict/', PredictAPIView.as_view(), name='api_predict'),
]
