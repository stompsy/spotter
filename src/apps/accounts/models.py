from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)

    def __str__(self) -> str:
        return self.get_full_name() or self.display_name or self.username
