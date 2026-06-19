from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    company = models.CharField(max_length=150, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True)
    default_key_column = models.CharField(max_length=100, blank=True)
    email_notifications = models.BooleanField(default=True)
    total_comparisons = models.PositiveIntegerField(default=0)
    total_files_uploaded = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user.username} — Profile'

    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return None

    def get_initials(self):
        fn = self.user.first_name
        ln = self.user.last_name
        if fn and ln:
            return f'{fn[0]}{ln[0]}'.upper()
        return self.user.username[:2].upper()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()