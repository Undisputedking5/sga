from django.shortcuts import redirect

def login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get("uid"):
            return redirect("core:login")
        return view_func(request, *args, **kwargs)
    return wrapper

def superadmin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.session.get("role") != "superadmin":
            return redirect("core:login")
        return view_func(request, *args, **kwargs)
    return wrapper