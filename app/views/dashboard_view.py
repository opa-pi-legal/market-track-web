import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse as r
from django.views import View

from app import services
from app.views.helpers import format_brl, get_session_token


def _parse_period_days(raw: str | None) -> tuple[str, int | None]:
    val = (raw or "30").strip().lower()
    if val == "7":
        return "7", 7
    if val == "all":
        return "all", None
    return "30", 30


def _within_days(created_raw: str | None, cutoff: datetime | None) -> bool:
    if cutoff is None or not created_raw:
        return True
    try:
        dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        return True


def _collect_dashboard_data(token: str, period_days: int | None = 30) -> dict:
    users = services.get_users(token)
    groups = services.get_groups(token)

    all_lists: list[dict] = []
    seen_list_ids: set = set()
    for g in groups:
        for sl in services.get_shopping_lists(token, group_id=g.get("id")):
            lid = sl.get("id")
            if lid not in seen_list_ids:
                seen_list_ids.add(lid)
                all_lists.append(sl)

    offers_all = services.get_community_offers(token, active_only=False)
    alerts_all = services.get_price_alerts(token, unread_only=False)
    markets_all = services.get_markets(token, all_groups=True)

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=period_days)) if period_days else None
    cutoff_30d = now - timedelta(days=30)

    offers_period = [o for o in offers_all if _within_days(o.get("created_at"), cutoff)]
    alerts_period = [a for a in alerts_all if _within_days(a.get("created_at"), cutoff)]

    offers_30d = sum(1 for o in offers_all if _within_days(o.get("created_at"), cutoff_30d))
    flagged_count = sum(
        1
        for o in offers_all
        if o.get("moderation_status") == "flagged"
        or int(o.get("abuse_reports_count") or 0) > 0
    )
    missing_geo_count = sum(
        1 for m in markets_all if m.get("latitude") is None or m.get("longitude") is None
    )

    offers_by_market: Counter = Counter()
    offers_by_category: Counter = Counter()
    prices_by_product: dict[str, list[int]] = defaultdict(list)

    for off in offers_period:
        market_name = (off.get("market_name") or "Outro").strip()
        category = (off.get("category") or "Geral").strip()
        product_name = (off.get("product_name") or "Produto").strip()
        price_cents = int(off.get("price_cents") or 0)

        offers_by_market[market_name] += 1
        offers_by_category[category] += 1
        if price_cents > 0:
            prices_by_product[product_name].append(price_cents)

    total_alerts = len(alerts_period)
    read_alerts = sum(1 for a in alerts_period if a.get("is_read") is True)
    unread_alerts = total_alerts - read_alerts
    alerts_read_pct = int(round((read_alerts / total_alerts) * 100)) if total_alerts else 0

    avg_product_rows = sorted(
        [
            {
                "label": name[:28],
                "avg_brl": round((sum(vals) / len(vals)) / 100, 2),
                "avg_fmt": format_brl(sum(vals) / len(vals)),
                "count": len(vals),
            }
            for name, vals in prices_by_product.items()
        ],
        key=lambda x: (-x["count"], x["label"]),
    )[:8]

    top_markets = [
        {"label": name, "count": count}
        for name, count in offers_by_market.most_common(8)
    ]
    top_categories = [
        {"label": name, "count": count}
        for name, count in offers_by_category.most_common(8)
    ]

    return {
        "total_users": len(users),
        "active_groups": len(groups),
        "total_lists": len(all_lists),
        "offers_30d": offers_30d,
        "offers_period_count": len(offers_period),
        "total_offers": len(offers_all),
        "total_alerts": total_alerts,
        "read_alerts": read_alerts,
        "unread_alerts": unread_alerts,
        "alerts_read_pct": alerts_read_pct,
        "flagged_count": flagged_count,
        "missing_geo_count": missing_geo_count,
        "avg_product_rows": avg_product_rows,
        "top_markets": top_markets,
        "top_categories": top_categories,
        "offers": offers_period,
    }


class dashboard_view(View):
    template_name = "dashboard_template.html"

    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        period_key, period_days = _parse_period_days(request.GET.get("days"))
        data = _collect_dashboard_data(token, period_days=period_days)

        # Atualiza contador da navbar sem custo extra
        request.session["_nav_mod_count"] = data["flagged_count"] + data["missing_geo_count"]

        charts = {
            "alerts": {
                "labels": ["Lidos", "Não lidos"],
                "values": [data["read_alerts"], data["unread_alerts"]],
            },
            "prices": {
                "labels": [row["label"] for row in data["avg_product_rows"]],
                "values": [row["avg_brl"] for row in data["avg_product_rows"]],
            },
            "markets": {
                "labels": [row["label"] for row in data["top_markets"]],
                "values": [row["count"] for row in data["top_markets"]],
            },
            "categories": {
                "labels": [row["label"] for row in data["top_categories"]],
                "values": [row["count"] for row in data["top_categories"]],
            },
        }

        period_labels = {"7": "últimos 7 dias", "30": "últimos 30 dias", "all": "todo o período"}

        context = {
            "active_nav": "dashboard",
            **data,
            "period_key": period_key,
            "period_label": period_labels[period_key],
            "charts_json": json.dumps(charts),
        }
        return render(request, self.template_name, context)


class dashboard_export_csv_view(View):
    def get(self, request):
        token = get_session_token(request)
        if not token:
            return redirect(r("login"))

        metric = (request.GET.get("metric") or "all").strip().lower()
        _, period_days = _parse_period_days(request.GET.get("days"))
        data = _collect_dashboard_data(token, period_days=period_days)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="mercadotracker_{metric}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")

        if metric == "markets":
            writer.writerow(["Mercado", "Ofertas"])
            for row in data["top_markets"]:
                writer.writerow([row["label"], row["count"]])
        elif metric == "categories":
            writer.writerow(["Categoria", "Ofertas"])
            for row in data["top_categories"]:
                writer.writerow([row["label"], row["count"]])
        elif metric == "prices":
            writer.writerow(["Produto", "Preco_Medio_BRL", "Amostras"])
            for row in data["avg_product_rows"]:
                writer.writerow([row["label"], row["avg_fmt"], row["count"]])
        elif metric == "alerts":
            writer.writerow(["Total_Alertas", "Lidos", "Nao_Lidos", "Taxa_Leitura_Pct"])
            writer.writerow([
                data["total_alerts"],
                data["read_alerts"],
                data["unread_alerts"],
                f"{data['alerts_read_pct']}%",
            ])
        else:
            writer.writerow(["Secao", "Indicador", "Valor"])
            writer.writerow(["Resumo", "Total de usuarios", data["total_users"]])
            writer.writerow(["Resumo", "Grupos ativos", data["active_groups"]])
            writer.writerow(["Resumo", "Listas criadas", data["total_lists"]])
            writer.writerow(["Resumo", "Ofertas no periodo", data["offers_period_count"]])
            writer.writerow(["Resumo", "Taxa de leitura alertas RabbitMQ", f"{data['alerts_read_pct']}%"])
            for row in data["top_markets"]:
                writer.writerow(["Ranking Mercados", row["label"], row["count"]])
            for row in data["top_categories"]:
                writer.writerow(["Ranking Categorias", row["label"], row["count"]])
            for row in data["avg_product_rows"]:
                writer.writerow(["Preco Medio", row["label"], row["avg_fmt"]])

        return response
