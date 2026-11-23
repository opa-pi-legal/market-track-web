from django.urls import path
from .views.login_view import login_view
from .views.logout_view import logout_view
from .views.google_login_view import google_login_view
from .views.cadastro_view import cadastro_view
from .views.dashboard_view import dashboard_view, dashboard_export_csv_view
from .views.lists_view import (
    list_delete_view,
    list_detail_view,
    list_item_delete_view,
    list_member_delete_view,
    lists_view,
)
from .views.products_view import (
    product_create_view,
    product_delete_view,
    product_detail_view,
    product_edit_view,
    product_promote_view,
    products_view,
)
from .views.moderation_view import (
    moderation_market_create_view,
    moderation_market_delete_view,
    moderation_market_geo_view,
    moderation_offer_action_view,
    moderation_product_action_view,
    moderation_product_bulk_promote_view,
    moderation_view,
)
from .views.maintenance_view import (
    maintenance_health_json_view,
    maintenance_simulate_offer_view,
    maintenance_view,
)
from .views.staff_view import (
    staff_create_view,
    staff_manage_view,
)

urlpatterns = [
    path("", login_view.as_view(), name="login"),
    path("login/", login_view.as_view(), name="login_alias"),
    path("auth/google/", google_login_view.as_view(), name="google_login"),
    path("sair/", logout_view.as_view(), name="logout"),
    path("cadastro/", cadastro_view.as_view(), name="cadastro"),

    path("dashboard/", dashboard_view.as_view(), name="dashboard"),
    path("dashboard/exportar-csv/", dashboard_export_csv_view.as_view(), name="dashboard_export_csv"),

    path("listas/", lists_view.as_view(), name="lists"),
    path("listas/<int:list_id>/", list_detail_view.as_view(), name="list_detail"),
    path("listas/<int:list_id>/apagar/", list_delete_view.as_view(), name="list_delete"),
    path("listas/<int:list_id>/item/<int:item_id>/apagar/", list_item_delete_view.as_view(), name="list_item_delete"),
    path("listas/<int:list_id>/membro/<int:membership_id>/remover/", list_member_delete_view.as_view(), name="list_member_delete"),

    path("produtos/", products_view.as_view(), name="products"),
    path("produtos/novo/", product_create_view.as_view(), name="product_create"),
    path("produtos/<int:product_id>/", product_detail_view.as_view(), name="product_detail"),
    path("produtos/<int:product_id>/editar/", product_edit_view.as_view(), name="product_edit"),
    path("produtos/<int:product_id>/promover/", product_promote_view.as_view(), name="product_promote"),
    path("produtos/<int:product_id>/apagar/", product_delete_view.as_view(), name="product_delete"),

    path("moderacao/", moderation_view.as_view(), name="moderation"),
    path("moderacao/oferta/<int:offer_id>/", moderation_offer_action_view.as_view(), name="moderation_offer_action"),
    path("moderacao/produto/<int:product_id>/", moderation_product_action_view.as_view(), name="moderation_product_action"),
    path("moderacao/produtos/promover-lote/", moderation_product_bulk_promote_view.as_view(), name="moderation_product_bulk_promote"),
    path("moderacao/mercado/novo/", moderation_market_create_view.as_view(), name="moderation_market_create"),
    path("moderacao/mercado/<int:market_id>/geo/", moderation_market_geo_view.as_view(), name="moderation_market_geo"),
    path("moderacao/mercado/<int:market_id>/apagar/", moderation_market_delete_view.as_view(), name="moderation_market_delete"),

    path("manutencao/", maintenance_view.as_view(), name="maintenance"),
    path("manutencao/health-json/", maintenance_health_json_view.as_view(), name="maintenance_health_json"),
    path("manutencao/simular-oferta/", maintenance_simulate_offer_view.as_view(), name="maintenance_simulate_offer"),

    path("equipe/staff/", staff_manage_view.as_view(), name="staff_manage"),
    path("equipe/staff/criar/", staff_create_view.as_view(), name="staff_create"),
]
