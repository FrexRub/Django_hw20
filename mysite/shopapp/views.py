import logging
import json
from csv import DictWriter

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.core.cache import cache
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, reverse, redirect, get_object_or_404
from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.parsers import MultiPartParser
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .forms import ProductForm, OrderForm
from .common import save_csv_products
from .models import Product, Order, ProductImage
from .serializers import (
    ProductSerializer,
    OrderSerializer,
    DetailSerializer,
    OrderFullSerializer,
)

log = logging.getLogger(__name__)


class UserOrdersListView(LoginRequiredMixin, ListView):
    template_name = "shopapp/orders-list-users.html"

    def get_queryset(self):
        if self.kwargs["user_id"]:
            user_id: int = self.kwargs["user_id"]
        else:
            user_id: int = 1
        self.owner: User = get_object_or_404(User, pk=user_id)
        return (
            Order.objects.select_related("user")
            .prefetch_related("products")
            .filter(user=self.owner)
        )

    def get_context_data(self, **kwargs):
        log.info("Show orders list by user %s:", self.owner.username)
        context = super().get_context_data(**kwargs)
        context["username"] = self.owner.username
        context["user_id"] = self.owner.pk
        return context


def export_user_orders_json(request: Request, user_id: int):
    # проверка данных кеша по ключу
    cache_key = f"orders_data_{user_id}"
    orders_json = cache.get(cache_key)

    if orders_json is None:
        user: User = get_object_or_404(User, pk=user_id)

        queryset = (
            Order.objects.select_related("user")
            .prefetch_related("products")
            .filter(user=user)
            .order_by("pk")
        )
        serializer = OrderSerializer(queryset, many=True)
        orders_json = json.dumps(
            {"orders": serializer.data},
            indent=4,
        )

        # сохранение данных кеша по ключу
        cache.set("cache_key", orders_json, 300)

    # создаем файл с данными
    file_name = f"orders-export-{user_id}.json"
    with open(file_name, "w") as outfile:
        outfile.write(orders_json)

    # читаем файл для отправки клиенту
    file_name_out = "orders-export.json"
    with open(file_name, "r") as fh:
        response = HttpResponse(fh.read(), content_type="application/json")

    response["Content-Disposition"] = f"attachment; filename={file_name_out}"

    return response


@extend_schema(tags=["Products"])
@extend_schema_view(
    list=extend_schema(
        summary="Получить список имеющихся товаров",
    ),
    update=extend_schema(
        summary="Изменение товара",
        request=ProductSerializer,
        responses={
            status.HTTP_200_OK: ProductSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
        examples=[
            OpenApiExample(
                "Product example",
                description="Пример заполнения карточки товара",
                value={
                    "name": "New Product",
                    "description": "Info about new Product",
                    "price": "12.99",
                    "discount": 5,
                    "archived": False,
                    "preview": None,
                },
                status_codes=[str(status.HTTP_200_OK)],
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Изменение данных в карточке товара",
        description="Возможно вносить частичные изменения в карточку товара",
    ),
    create=extend_schema(
        summary="Создание нового товара",
        request=ProductSerializer,
        responses={
            status.HTTP_200_OK: ProductSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
        examples=[
            OpenApiExample(
                "Product example",
                description="Пример заполнения карточки товара",
                value={
                    "name": "New Product",
                    "description": "Info about new Product",
                    "price": "12.99",
                    "discount": 5,
                    "archived": False,
                    "preview": None,
                },
                status_codes=[str(status.HTTP_200_OK)],
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Детальная информация о товаре",
        responses={
            status.HTTP_200_OK: ProductSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
    ),
)
class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = [
        "name",
        "description",
        "price",
        "discount",
        "archived",
    ]
    filter_backends = [
        SearchFilter,
        OrderingFilter,
    ]
    search_fields = [
        "name",
        "description",
    ]
    ordering_fields = [
        "name",
        "price",
        "discount",
    ]

    @extend_schema(
        summary="Архивирование товара",
    )
    def destroy(self, request, *args, **kwargs):
        isinstance = self.get_object()
        isinstance.archived = True
        isinstance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
        # return super().destroy(request, *args, **kwargs)

    @action(methods=["get"], detail=False)
    def download_csv(self, request: Request):
        response = HttpResponse(content_type="text/csv")
        file_name = "products-export.csv"
        response["Content-Disposition"] = f"attachment; filename={file_name}"
        # Фильтрация результатов фильтрами, указанными в данном классе
        queryset = self.filter_queryset(self.get_queryset())
        fields = [
            "name",
            "description",
            "price",
            "discount",
        ]
        # Загрузка только указанных полей
        queryset = queryset.only(*fields)

        # Записываем в response как в обычный файл
        writer = DictWriter(
            response,
            fieldnames=fields,
        )
        writer.writeheader()
        for product in queryset:
            writer.writerow({field: getattr(product, field) for field in fields})

        return response

    @action(methods=["post"], detail=False, parser_classes=[MultiPartParser])
    def upload_csv(self, request: Request):
        products = save_csv_products(
            request.FILES["file"].file,
            encoding=request.encoding,
        )
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)


@extend_schema(tags=["Orders"])
@extend_schema_view(
    list=extend_schema(
        summary="Получить список имеющихся заказов",
        responses={
            status.HTTP_200_OK: OrderFullSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
    ),
    update=extend_schema(
        summary="Изменение заказа",
        request=OrderSerializer,
        responses={
            status.HTTP_200_OK: OrderSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
        examples=[
            OpenApiExample(
                "Order example",
                description="Пример создания заказа",
                value={
                    "delivery_address": "ul Mira 11",
                    "promocode": "SALE",
                    "user": 1,
                    "products": [1, 3],
                    "receipt": None,
                },
                status_codes=[str(status.HTTP_200_OK)],
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Изменение данных в заказе",
        description="Возможно вносить частичные изменения в заказ",
    ),
    create=extend_schema(
        summary="Создание нового заказа",
        request=OrderSerializer,
        responses={
            status.HTTP_200_OK: ProductSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
        examples=[
            OpenApiExample(
                "Product example",
                description="Пример создания заказа",
                value={
                    "delivery_address": "ul Mira 11",
                    "promocode": "SALE",
                    "user": 1,
                    "products": [1, 3],
                    "receipt": None,
                },
                status_codes=[str(status.HTTP_200_OK)],
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Детальная информация о заказе",
        responses={
            status.HTTP_200_OK: OrderFullSerializer,
            status.HTTP_400_BAD_REQUEST: DetailSerializer,
            status.HTTP_500_INTERNAL_SERVER_ERROR: OpenApiResponse(
                response=None,
                description="Что-то пошло не так",
            ),
        },
    ),
)
class OrderViewSet(ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    filterset_fields = [
        "delivery_address",
        "promocode",
        "user",
        "products",
    ]
    filter_backends = [
        DjangoFilterBackend,
        OrderingFilter,
    ]
    ordering_fields = [
        "delivery_address",
        "promocode",
        "products",
    ]

    @extend_schema(
        summary="Удаление заказа",
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ShopIndexView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        log.info("Open shop index")
        context = {}
        return render(request, "shopapp/shop-index.html", context=context)


class ProductDetailsView(DetailView):
    template_name = "shopapp/products-details.html"
    queryset = Product.objects.prefetch_related("images")
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        log.info("Show details of %s", self.object.name)
        context = super().get_context_data(**kwargs)
        return context


class ProductsListView(ListView):
    template_name = "shopapp/products-list.html"
    context_object_name = "products"
    queryset = Product.objects.filter(archived=False)

    def get_context_data(self, **kwargs):
        log.info("Show products list (only not archived)")
        context = super().get_context_data(**kwargs)
        return context


class ProductCreateView(CreateView):
    model = Product
    fields = "name", "price", "description", "discount", "preview"
    success_url = reverse_lazy("shopapp:products_list")

    def get_context_data(self, **kwargs):
        log.info("Create product")
        context = super().get_context_data(**kwargs)
        return context


class ProductUpdateView(UpdateView):
    model = Product
    log.info("Update product")
    template_name_suffix = "_update_form"
    form_class = ProductForm

    def get_success_url(self):
        log.debug("Generate success url product details")
        return reverse(
            "shopapp:product_details",
            kwargs={"pk": self.object.pk},
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        log.debug("Add images for product")
        for image in form.files.getlist("images"):
            ProductImage.objects.create(
                product=self.object,
                image=image,
            )

        return response

    def get_context_data(self, **kwargs):
        log.info("Update info of %s", self.object.name)
        context = super().get_context_data(**kwargs)
        return context


class ProductDeleteView(DeleteView):
    model = Product
    success_url = reverse_lazy("shopapp:products_list")

    def form_valid(self, form):
        log.info("Archived product")
        success_url = self.get_success_url()
        self.object.archived = True
        self.object.save()
        return HttpResponseRedirect(success_url)


class OrdersListView(LoginRequiredMixin, ListView):
    queryset = Order.objects.select_related("user").prefetch_related("products")

    def get_context_data(self, **kwargs):
        log.info("Show orders' list")
        context = super().get_context_data(**kwargs)
        return context


class OrderDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "shopapp.view_order"
    queryset = Order.objects.select_related("user").prefetch_related("products")

    def get_context_data(self, **kwargs):
        log.info("Show orders details")
        context = super().get_context_data(**kwargs)
        return context


class ProductsDataExportView(View):
    def get(self, request: HttpRequest) -> JsonResponse:
        products = Product.objects.order_by("pk").all()
        products_data = [
            {
                "pk": product.pk,
                "name": product.name,
                "price": product.price,
                "archived": product.archived,
            }
            for product in products
        ]
        return JsonResponse({"products": products_data})


def order_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        log.debug("Create order (start POST metod")
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            url = reverse("shopapp:orders_list")
            return redirect(url)
    else:
        log.debug("Create order (open form")
        form = OrderForm()
    context = {"form": form}
    return render(request, "shopapp/create-order.html", context=context)


class LatestProductsFeed(Feed):
    title = "Shop - list products"
    link = reverse_lazy("shopapp:products_list")
    description = "Products in the shop."

    def items(self):
        return Product.objects.order_by("-created_at")[:3]

    def item_title(self, item: Product):
        return item.name

    def item_description(self, item: Product):
        return item.description[:100]

    def item_link(self, item: Product):
        return reverse("shopapp:product_details", kwargs={"pk": item.pk})
