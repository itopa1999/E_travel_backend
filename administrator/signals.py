from django.db.models.signals import post_save
from django.dispatch import receiver

from administrator.models import IdentityInfo, User, Wallet


@receiver(post_save, sender=User)
def Create_User_Account_Balance(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(user=instance, balance=0)
        IdentityInfo.objects.create(user = instance)