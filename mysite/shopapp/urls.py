from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ShopIndexView,
    ProductDetailsView,
    ProductsListView,
    OrdersListView,
    OrderDetailView,
    ProductCreateView,
    ProductUpdateView,
    ProductDeleteView,
    ProductsDataExportView,
    ProductViewSet,
    OrderViewSet,
    order_create,
    LatestProductsFeed,
    UserOrdersListView,
    export_user_orders_json,
)

app_name = "shopapp"

router = DefaultRouter()
router.register("products", ProductViewSet)
router.register("orders", OrderViewSet)

urlpatterns = [
    path("", ShopIndexView.as_view(), name="index"),
    path("api/", include(router.urls)),
    path("products/", ProductsListView.as_view(), name="products_list"),
    path("products/export/", ProductsDataExportView.as_view(), name="products-export"),
    path("products/create/", ProductCreateView.as_view(), name="product_create"),
    path("products/latest/feed/", LatestProductsFeed(), name="products_feed"),
    path("products/<int:pk>/", ProductDetailsView.as_view(), name="product_details"),
    path(
        "products/<int:pk>/update/", ProductUpdateView.as_view(), name="product_update"
    ),
    path(
        "products/<int:pk>/archive/", ProductDeleteView.as_view(), name="product_delete"
    ),
    path("orders/", OrdersListView.as_view(), name="orders_list"),
    path(
        "users/<int:user_id>/orders/",
        UserOrdersListView.as_view(),
        name="user_orders_list",
    ),
    path(
        "users/<int:user_id>/orders/export/",
        export_user_orders_json,
        name="user_orders_export",
    ),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_details"),
    path("orders/create/", order_create, name="orders_create"),
]
