from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_iso_date, get_session_token, parse_price_to_cents


class maintenance_view(View):
    template_name = "maintenance_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        health_checks = services.check_services_health()
        rabbitmq_queues = services.get_rabbitmq_queues()
        groups = services.get_groups(token, all_groups=True)
        active_gid = request.session.get("active_group_id") or (groups[0].get("id") if groups else None)
        logs_raw = services.get_activity_logs(token, group_id=active_gid)

        logs = [
            {
                "action": item.get("action") or "evento",
                "description": item.get("description") or item.get("entity_type") or "-",
                "created_at_fmt": format_iso_date(item.get("created_at"), with_time=True),
            }
            for item in logs_raw[:25]
        ]

        api_base = getattr(settings, "PUBLIC_API_BASE_URL", settings.API_BASE_URL)
        host_only = api_base.split("://")[-1].split(":")[0].split("/")[0] or "127.0.0.1"
        rabbitmq_console_url = f"http://{host_only}:15672/#/queues"

        return render(
            request,
            self.template_name,
            {
                "active_nav": "maintenance",
                "api_base_url": api_base,
                "rabbitmq_console_url": rabbitmq_console_url,
                "health_checks": health_checks,
                "rabbitmq_queues": rabbitmq_queues,
                "checked_at": datetime.now().strftime("%H:%M:%S"),
                "logs": logs,
                "groups": groups,
                "active_gid": active_gid,
            },
        )


class maintenance_health_json_view(View):
    def get(self, request):
        token = get_session_token(request)
        if not token:
            return JsonResponse({"error": "Não autenticado."}, status=401)
        return JsonResponse(
            {
                "health_checks": services.check_services_health(),
                "rabbitmq_queues": services.get_rabbitmq_queues(),
                "checked_at": datetime.now().strftime("%H:%M:%S"),
            }
        )


class maintenance_simulate_offer_view(View):
    def post(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        product_name = (request.POST.get("product_name") or "Café Pilão Tradicional 500g").strip()
        market_name = (request.POST.get("market_name") or "Atacadão").strip()
        price_cents = parse_price_to_cents(request.POST.get("price") or "12,90") or 1290
        ean = (request.POST.get("ean") or "").strip()
        city = (request.POST.get("city") or "São Paulo").strip()

        payload = {
            "product_name": product_name,
            "market_name": market_name,
            "price_cents": price_cents,
            "category": "Mercearia",
            "city": city,
            "is_promotion": True,
            "broadcast_alert": True,
        }
        if ean:
            payload["ean"] = ean

        try:
            created = services.create_community_offer(token, payload)
            messages.success(
                request,
                f"Oferta #{created.get('id')} disparada! Notificação enviada para os aplicativos móveis.",
            )
        except services.APIError as exc:
            messages.error(request, f"Erro ao simular oferta: {exc}")

        return redirect(r("maintenance"))
