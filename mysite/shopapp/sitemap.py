from django.contrib.sitemaps import Sitemap

from .models import Product


class ShopSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.9

    def items(self):
        return Product.objects.order_by('-created_at')

    def lastmod(self, obj):
        return obj.created_at

