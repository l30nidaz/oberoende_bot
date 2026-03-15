# oberoende_bot/app/routers/admin_router.py
"""
Panel de administración por negocio.
Rutas:
  GET  /admin/{business_id}          → formulario de login
  POST /admin/{business_id}          → procesa login, redirige al dashboard
  GET  /admin/{business_id}/dashboard?token=xxx  → dashboard con métricas
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from oberoende_bot.app.services.admin_service import (
    get_dashboard_data,
    verify_admin_credentials,
)

router = APIRouter()

# ── Sesiones en memoria (simple, sin BD extra) ───────────────────────────────
# token → {business_id, expires_at}
_sessions: Dict[str, dict] = {}
SESSION_HOURS = 8


def _create_session(business_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "business_id": business_id,
        "expires_at": datetime.utcnow() + timedelta(hours=SESSION_HOURS),
    }
    return token


def _validate_session(token: str, business_id: str) -> bool:
    session = _sessions.get(token)
    if not session:
        return False
    if session["business_id"] != business_id:
        return False
    if datetime.utcnow() > session["expires_at"]:
        _sessions.pop(token, None)
        return False
    return True


# ── Templates HTML ────────────────────────────────────────────────────────────

def _login_page(business_id: str, error: str = "") -> str:
    error_html = f'<p class="error">{error}</p>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oberoende · Admin</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --border: #1e1e2e;
    --accent: #7c6af7;
    --accent-dim: rgba(124,106,247,0.15);
    --text: #e2e2f0;
    --muted: #6b6b80;
    --error: #f87171;
    --mono: 'DM Mono', monospace;
    --display: 'Syne', sans-serif;
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background-image:
      radial-gradient(ellipse 60% 40% at 50% 0%, rgba(124,106,247,0.08) 0%, transparent 70%);
  }}

  .card {{
    width: 100%;
    max-width: 400px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2.5rem;
    box-shadow: 0 0 60px rgba(124,106,247,0.06);
  }}

  .logo {{
    font-family: var(--display);
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: var(--text);
    margin-bottom: 0.25rem;
  }}

  .subtitle {{
    color: var(--muted);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 2rem;
  }}

  label {{
    display: block;
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.4rem;
  }}

  input {{
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-family: var(--mono);
    font-size: 0.9rem;
    padding: 0.65rem 0.85rem;
    outline: none;
    transition: border-color 0.2s;
    margin-bottom: 1.2rem;
  }}

  input:focus {{ border-color: var(--accent); }}

  button {{
    width: 100%;
    background: var(--accent);
    color: #fff;
    font-family: var(--display);
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    border: none;
    border-radius: 8px;
    padding: 0.75rem;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
    margin-top: 0.4rem;
  }}

  button:hover {{ opacity: 0.88; transform: translateY(-1px); }}
  button:active {{ transform: translateY(0); }}

  .error {{
    color: var(--error);
    font-size: 0.8rem;
    margin-bottom: 1rem;
    padding: 0.5rem 0.75rem;
    background: rgba(248,113,113,0.1);
    border-radius: 6px;
    border: 1px solid rgba(248,113,113,0.2);
  }}

  .bid {{
    display: inline-block;
    background: var(--accent-dim);
    color: var(--accent);
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    border: 1px solid rgba(124,106,247,0.3);
    margin-bottom: 1.8rem;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">Oberoende</div>
  <div class="subtitle">Panel de administración</div>
  <div class="bid">{business_id}</div>
  {error_html}
  <form method="POST" action="/admin/{business_id}">
    <label for="username">Usuario</label>
    <input type="text" id="username" name="username" autocomplete="username" required>
    <label for="password">Contraseña</label>
    <input type="password" id="password" name="password" autocomplete="current-password" required>
    <button type="submit">Ingresar →</button>
  </form>
</div>
</body>
</html>"""


def _dashboard_page(data: dict, token: str) -> str:
    business_id   = data["business_id"]
    business_name = data["business_name"]
    emoji         = data["business_emoji"]
    msgs          = data["messages"]
    users         = data["users"]
    activity      = data["activity"]
    leads_count   = data["leads_count"]
    generated_at  = data["generated_at"]

    # ── Gráfica de barras CSS ─────────────────────────────────────────────────
    max_count = max((d["count"] for d in activity), default=1) or 1
    bars_html = ""
    for d in activity:
        pct = round((d["count"] / max_count) * 100)
        bars_html += f"""
        <div class="bar-col">
          <div class="bar-wrap">
            <div class="bar" style="height:{pct}%" title="{d['count']} mensajes">
              <span class="bar-val">{d['count'] if d['count'] > 0 else ''}</span>
            </div>
          </div>
          <div class="bar-label">{d['label']}</div>
        </div>"""

    # ── Tabla de usuarios ─────────────────────────────────────────────────────
    if users:
        rows_html = ""
        for u in users:
            rows_html += f"""
            <tr>
              <td class="phone">{u['phone']}</td>
              <td class="center">{u['total_msgs']}</td>
              <td class="muted">{u['last_seen']}</td>
            </tr>"""
        table_html = f"""
        <table>
          <thead>
            <tr>
              <th>Número</th>
              <th class="center">Mensajes</th>
              <th>Último contacto</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>"""
    else:
        table_html = '<p class="empty">Sin interacciones registradas aún.</p>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{business_name} · Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface2: #17171f;
    --border: #1e1e2e;
    --accent: #7c6af7;
    --accent-dim: rgba(124,106,247,0.12);
    --green: #34d399;
    --green-dim: rgba(52,211,153,0.12);
    --yellow: #fbbf24;
    --yellow-dim: rgba(251,191,36,0.12);
    --blue: #60a5fa;
    --blue-dim: rgba(96,165,250,0.12);
    --text: #e2e2f0;
    --muted: #6b6b80;
    --mono: 'DM Mono', monospace;
    --display: 'Syne', sans-serif;
  }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse 80% 30% at 50% 0%, rgba(124,106,247,0.05) 0%, transparent 60%);
  }}

  /* ── Header ── */
  header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 2rem;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: rgba(10,10,15,0.92);
    backdrop-filter: blur(12px);
    z-index: 10;
  }}

  .header-left {{ display: flex; align-items: center; gap: 0.75rem; }}

  .logo {{
    font-family: var(--display);
    font-size: 1.15rem;
    font-weight: 800;
    letter-spacing: -0.02em;
  }}

  .divider {{ color: var(--border); font-size: 1.2rem; }}

  .biz-name {{
    font-size: 0.85rem;
    color: var(--muted);
    letter-spacing: 0.04em;
  }}

  .logout {{
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    text-decoration: none;
    padding: 0.35rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    transition: color 0.2s, border-color 0.2s;
  }}

  .logout:hover {{ color: var(--text); border-color: var(--muted); }}

  /* ── Layout ── */
  main {{
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem;
  }}

  .page-title {{
    font-family: var(--display);
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin-bottom: 0.35rem;
  }}

  .page-sub {{
    color: var(--muted);
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    margin-bottom: 2rem;
  }}

  /* ── KPI Cards ── */
  .kpis {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}

  .kpi {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    position: relative;
    overflow: hidden;
  }}

  .kpi::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--kpi-color, var(--accent));
  }}

  .kpi-label {{
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }}

  .kpi-value {{
    font-family: var(--display);
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    line-height: 1;
    color: var(--kpi-color, var(--text));
  }}

  .kpi-sub {{
    font-size: 0.72rem;
    color: var(--muted);
    margin-top: 0.35rem;
  }}

  /* ── Section ── */
  .section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }}

  .section-title {{
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 1.25rem;
  }}

  /* ── Gráfica de barras ── */
  .chart {{
    display: flex;
    align-items: flex-end;
    gap: 6px;
    height: 140px;
  }}

  .bar-col {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
  }}

  .bar-wrap {{
    flex: 1;
    width: 100%;
    display: flex;
    align-items: flex-end;
  }}

  .bar {{
    width: 100%;
    background: var(--accent);
    border-radius: 4px 4px 0 0;
    min-height: 2px;
    position: relative;
    transition: opacity 0.2s;
    opacity: 0.75;
  }}

  .bar:hover {{ opacity: 1; }}

  .bar-val {{
    position: absolute;
    top: -18px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 0.6rem;
    color: var(--accent);
    white-space: nowrap;
  }}

  .bar-label {{
    font-size: 0.58rem;
    color: var(--muted);
    margin-top: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    text-align: center;
  }}

  /* ── Tabla ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }}

  thead tr {{
    border-bottom: 1px solid var(--border);
  }}

  th {{
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0 0 0.75rem;
    text-align: left;
    font-weight: 500;
  }}

  th.center, td.center {{ text-align: center; }}

  tbody tr {{
    border-bottom: 1px solid rgba(30,30,46,0.5);
    transition: background 0.15s;
  }}

  tbody tr:hover {{ background: var(--surface2); }}
  tbody tr:last-child {{ border-bottom: none; }}

  td {{
    padding: 0.65rem 0;
    color: var(--text);
  }}

  td.phone {{ font-size: 0.88rem; letter-spacing: 0.04em; }}
  td.muted {{ color: var(--muted); font-size: 0.78rem; }}
  td.center {{ color: var(--accent); font-weight: 500; }}

  .empty {{
    color: var(--muted);
    font-size: 0.82rem;
    text-align: center;
    padding: 2rem 0;
  }}

  .footer {{
    text-align: center;
    color: var(--muted);
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    padding: 2rem 0 1rem;
  }}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <span class="logo">Oberoende</span>
    <span class="divider">|</span>
    <span class="biz-name">{emoji} {business_name}</span>
  </div>
  <a href="/admin/{business_id}" class="logout">Cerrar sesión</a>
</header>

<main>
  <div class="page-title">{emoji} Dashboard</div>
  <div class="page-sub">Generado el {generated_at} · últimos 14 días en gráfica</div>

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi" style="--kpi-color: var(--accent)">
      <div class="kpi-label">Mensajes totales</div>
      <div class="kpi-value">{msgs['total']}</div>
      <div class="kpi-sub">{msgs['user']} de usuarios · {msgs['bot']} del bot</div>
    </div>
    <div class="kpi" style="--kpi-color: var(--green)">
      <div class="kpi-label">Usuarios únicos</div>
      <div class="kpi-value" style="color: var(--green)">{len(users)}</div>
      <div class="kpi-sub">números distintos</div>
    </div>
    <div class="kpi" style="--kpi-color: var(--yellow)">
      <div class="kpi-label">Leads capturados</div>
      <div class="kpi-value" style="color: var(--yellow)">{leads_count}</div>
      <div class="kpi-sub">completaron el flujo</div>
    </div>
    <div class="kpi" style="--kpi-color: var(--blue)">
      <div class="kpi-label">Actividad hoy</div>
      <div class="kpi-value" style="color: var(--blue)">{activity[-1]['count'] if activity else 0}</div>
      <div class="kpi-sub">mensajes hoy</div>
    </div>
  </div>

  <!-- Gráfica -->
  <div class="section">
    <div class="section-title">Actividad — últimos 14 días</div>
    <div class="chart">
      {bars_html}
    </div>
  </div>

  <!-- Tabla de usuarios -->
  <div class="section">
    <div class="section-title">Números que han interactuado</div>
    {table_html}
  </div>

</main>

<div class="footer">Oberoende · {business_id} · {generated_at}</div>

</body>
</html>"""


# ── Rutas ─────────────────────────────────────────────────────────────────────

@router.get("/admin/{business_id}", response_class=HTMLResponse)
async def admin_login_page(business_id: str):
    return _login_page(business_id)


@router.post("/admin/{business_id}")
async def admin_login_submit(
    business_id: str,
    username: str = Form(...),
    password: str = Form(...),
):
    if not verify_admin_credentials(business_id, username, password):
        return HTMLResponse(
            _login_page(business_id, error="Usuario o contraseña incorrectos"),
            status_code=401,
        )
    token = _create_session(business_id)
    return RedirectResponse(
        url=f"/admin/{business_id}/dashboard?token={token}",
        status_code=303,
    )


@router.get("/admin/{business_id}/dashboard", response_class=HTMLResponse)
async def admin_dashboard(business_id: str, token: str = ""):
    if not _validate_session(token, business_id):
        return RedirectResponse(url=f"/admin/{business_id}", status_code=303)
    data = get_dashboard_data(business_id)
    return _dashboard_page(data, token)