from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    index_view, AccountViewSet, CreditCardViewSet,
    CategoryViewSet, TransactionViewSet, DashboardView
)

router = DefaultRouter()
router.register(r'accounts', AccountViewSet, basename='account')
router.register(r'credit-cards', CreditCardViewSet, basename='credit-card')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', index_view, name='index'),
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/', include(router.urls)),
]

