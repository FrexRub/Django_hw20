from django.contrib.auth.models import User
from django.db import models


def user_directory_path(instance, filename):
    return 'user_{pk}/{filename}'.format(pk=instance.user.id, filename=filename)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(max_length=500, blank=True)
    agreement_accepted = models.BooleanField(default=False)
    avatar = models.ImageField(null=True, blank=True, upload_to=user_directory_path)
