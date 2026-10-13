import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    # El bloque 'with' ejecuta el lifespan (connect_to_mongo y create_indexes)
    with TestClient(app) as c:
        yield c


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert data["docs"] == "/docs"


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["database"]["connected"] is True


def test_login_and_auth(client):
    # Probar login con el usuario admin sembrado en Atlas
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@saaml.com", "password": "Admin123*"}
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # Consultar perfil autenticado con el token JWT
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "admin@saaml.com"
    assert me_data["rol"] == "ADMIN"


def test_ml_forecast(client):
    # Probar pronóstico para el SKU sembrado
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@saaml.com", "password": "Admin123*"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    fc_resp = client.get("/api/v1/ml/forecast/SKU-AUR-001?horizon_days=7", headers=headers)
    assert fc_resp.status_code == 200
    fc_data = fc_resp.json()
    assert fc_data["sku_code"] == "SKU-AUR-001"
    assert "demanda_total_proyectada" in fc_data
    assert fc_data["demanda_total_proyectada"] > 0
    assert len(fc_data["proyeccion_diaria"]) == 7


def test_optimization_and_orders_flow(client):
    # 1. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@saaml.com", "password": "Admin123*"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Consultar ciclo presupuestal sembrado
    budget_resp = client.get("/api/v1/budget/", headers=headers)
    assert budget_resp.status_code == 200
    cycles = budget_resp.json()["items"]
    assert len(cycles) > 0
    ciclo = cycles[0]
    ciclo_id = ciclo["_id"]

    # 3. Ejecutar optimización Knapsack (RF04)
    opt_payload = {
        "ciclo_presupuestal_id": ciclo_id,
        "presupuesto_limite": 15000.0,
        "horizon_days": 14,
        "considerar_volumen_almacen": True,
        "factor_seguridad": 1.0
    }
    opt_resp = client.post("/api/v1/optimization/run", json=opt_payload, headers=headers)
    assert opt_resp.status_code == 200
    opt_data = opt_resp.json()
    assert "sesion" in opt_data
    sesion = opt_data["sesion"]
    assert sesion["solver_status"] in ["OPTIMAL", "FEASIBLE"]
    assert sesion["tiempo_ejecucion_ms"] < 30000  # RNF01: < 30s
    assert sesion["presupuesto_total_asignado"] <= opt_payload["presupuesto_limite"]
    assert len(sesion["items_recomendados"]) > 0

    session_id = sesion["_id"]

    # 4. Generar órdenes de compra propuestas a partir de la sesión (RF05)
    gen_resp = client.post(f"/api/v1/orders/generate-from-session/{session_id}", headers=headers)
    assert gen_resp.status_code == 201
    gen_data = gen_resp.json()
    assert gen_data["total_ordenes"] >= 1
    ordenes = gen_data["ordenes"]
    primera_orden = ordenes[0]
    order_id = primera_orden["_id"]
    assert primera_orden["estado"] == "BORRADOR_PROPUESTA"
    assert len(primera_orden["items"]) > 0

    # 5. Consultar orden por ID
    get_order_resp = client.get(f"/api/v1/orders/{order_id}", headers=headers)
    assert get_order_resp.status_code == 200
    order_detail = get_order_resp.json()
    assert order_detail["codigo_orden"] == primera_orden["codigo_orden"]
    assert "proveedor_info" in order_detail

    # 6. Ajustar cantidades de items en borrador
    first_item = order_detail["items"][0]
    sku_to_adjust = first_item["sku_code"]
    nueva_cantidad = first_item["cantidad_sugerida_ml"] + 5
    adjust_payload = {
        "items": [
            {"sku_code": sku_to_adjust, "cantidad_final_aprobada": nueva_cantidad}
        ]
    }
    adj_resp = client.patch(f"/api/v1/orders/{order_id}/items", json=adjust_payload, headers=headers)
    assert adj_resp.status_code == 200
    adj_data = adj_resp.json()
    assert adj_data["nuevo_costo_total"] > 0

    # 7. Aprobar orden de compra
    approve_resp = client.patch(f"/api/v1/orders/{order_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    app_data = approve_resp.json()
    assert app_data["estado"] == "APROBADA"
    assert app_data["fecha_aprobacion"] is not None


