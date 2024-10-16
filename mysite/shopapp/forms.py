from django import forms
from django.core.exceptions import ValidationError


from shopapp.models import Product, Order


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


def validate_price(value: int):
    if value < 0:
        msg = "the value must be greater than zero'"
        raise ValidationError(msg)


class ProductForm(forms.ModelForm):
    images = MultipleFileField(label="Select files", required=False)

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        self.fields["price"].validators = [validate_price]

    class Meta:
        model = Product
        fields = "name", "price", "description", "discount", "preview", "images"


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = "delivery_address", "promocode", "user", "products"


class CSVImportForm(forms.Form):
    csv_file = forms.FileField()
