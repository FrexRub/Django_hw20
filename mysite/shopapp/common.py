from csv import DictReader
from io import TextIOWrapper

from django.contrib.auth.models import User
from django.db import transaction

from .models import Product, Order


def save_csv_products(file, encoding):
    csv_file = TextIOWrapper(
        file,
        encoding,
    )
    reader = DictReader(csv_file)
    products = [Product(**row) for row in reader]
    Product.objects.bulk_create(products)
    return products


def save_csv_order(file, encoding):
    csv_file = TextIOWrapper(
        file,
        encoding,
    )
    reader = DictReader(csv_file)
    orders: list[Order] = list()

    for row in reader:
        with transaction.atomic():
            order: Order = Order(
                delivery_address=row["delivery_address"],
                promocode=row["promocode"],
                user=User.objects.get(username=row["user"]),
            )
            order.save()
            for pk_product in row["products"].split(","):
                product: Product = Product.objects.get(pk=pk_product)
                order.products.add(product)

            orders.append(order)

    return orders