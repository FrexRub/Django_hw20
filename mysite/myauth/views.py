import logging

from django.contrib.auth.decorators import (
    login_required,
    permission_required,
    user_passes_test,
)
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LogoutView
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views import View
from django.shortcuts import reverse
from django.views.generic import (
    TemplateView,
    CreateView,
    UpdateView,
    ListView,
    DetailView,
)
from django.contrib.auth.mixins import (
    UserPassesTestMixin,
)

from .models import Profile
from .forms import ProfileForm, UserUpdateForm

log = logging.getLogger(__name__)


class AboutMeView(TemplateView):
    template_name = "myauth/about-me.html"

    def get_context_data(self, **kwargs):
        log.info("Show info about user")
        context = super().get_context_data(**kwargs)
        return context


class AboutMeUpdateView(UserPassesTestMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = "myauth/about-me_update_form.html"

    def test_func(self):
        log.debug("Сhecking user rights %s", self.request.user)
        return (
            self.get_object().user == self.request.user
        ) or self.request.user.is_staff

    def get_success_url(self):
        return reverse("myauth:user_details", kwargs={"pk": self.object.user.pk})

    def get_context_data(self, **kwargs):
        log.info("Update detail about user: %s", self.object.user.username)
        context = super().get_context_data(**kwargs)
        context["user_name"] = self.object.user.username
        if self.request.POST:
            context["user_form"] = UserUpdateForm(
                self.request.POST, instance=self.object.user
            )
        else:
            context["user_form"] = UserUpdateForm(instance=self.object.user)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        user_form = context["user_form"]
        with transaction.atomic():
            if all([form.is_valid(), user_form.is_valid()]):
                user_form.save()
                form.save()
            else:
                context.update({"user_form": user_form})
                return self.render_to_response(context)
        return super().form_valid(form)


class UserDetailsView(DetailView):
    log.info("Show detail about user")
    template_name = "myauth/about-me.html"
    model = User
    context_object_name = "user"

    def get_context_data(self, **kwargs):
        log.info("Get info about user %s", self.object.username)
        context = super().get_context_data(**kwargs)
        context["user_info"] = self.object.username
        return context


class ListUsersView(ListView):
    template_name = "myauth/users-list.html"
    context_object_name = "users"
    model = User

    def get_context_data(self, **kwargs):
        log.info("Show list users")
        context = super().get_context_data(**kwargs)
        return context


class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = "myauth/register.html"
    success_url = reverse_lazy("myauth:about-me")

    def form_valid(self, form):
        log.info("Register user")
        response = super().form_valid(form)
        Profile.objects.create(user=self.object)
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password1")
        user = authenticate(
            self.request,
            username=username,
            password=password,
        )
        log.debug("Login new user as %s", username)
        login(request=self.request, user=user)
        return response


class MyLogoutView(LogoutView):
    next_page = reverse_lazy("myauth:login")

    def get_context_data(self, **kwargs):
        log.info("Logout user %s", self.request.user)
        context = super().get_context_data(**kwargs)
        return context


@user_passes_test(lambda u: u.is_superuser)
def set_cookie_view(request: HttpRequest) -> HttpResponse:
    response = HttpResponse("Cookie set")
    response.set_cookie("fizz", "buzz", max_age=3600)
    return response


def get_cookie_view(request: HttpRequest) -> HttpResponse:
    value = request.COOKIES.get("fizz", "default value")
    return HttpResponse(f"Cookie value: {value!r}")


@permission_required("myauth.view_profile", raise_exception=True)
def set_session_view(request: HttpRequest) -> HttpResponse:
    request.session["foobar"] = "spameggs"
    return HttpResponse("Session set!")


@login_required
def get_session_view(request: HttpRequest) -> HttpResponse:
    value = request.session.get("foobar", "default")
    return HttpResponse(f"Session value: {value!r}")


class FooBarView(View):
    def get(self, request: HttpRequest) -> JsonResponse:
        return JsonResponse({"foo": "bar", "spam": "eggs"})
