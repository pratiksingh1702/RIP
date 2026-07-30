"""FastAPI Admin Dashboard Router and Telemetry API."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

from core.storage.database import get_db_session
from server.config import get_settings

logger = logging.getLogger("AdminRouter")
router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_SECRET_KEY = "admin123"

def verify_admin_key(x_admin_key: str | None = Header(default=None), key: str | None = None) -> bool:
    provided = x_admin_key or key
    if provided != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized Admin Access Key")
    return True

@router.get("/api/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: str | None = Header(default=None),
    key: str | None = None,
) -> dict[str, Any]:
    """Get aggregated telemetry across PostgreSQL, Neo4j, and Qdrant."""
    verify_admin_key(x_admin_key, key)
    settings = get_settings()

    # 1. PostgreSQL User & Project Stats
    user_count = 0
    session_count = 0
    project_count = 0
    try:
        res_u = await db.execute(text("SELECT COUNT(*) FROM users;"))
        user_count = res_u.scalar() or 0
        res_s = await db.execute(text("SELECT COUNT(*) FROM user_sessions WHERE revoked_at IS NULL;"))
        session_count = res_s.scalar() or 0
        res_p = await db.execute(text("SELECT COUNT(*) FROM projects;"))
        project_count = res_p.scalar() or 0
    except Exception as e:
        logger.warning(f"[Admin] DB stats query error: {e}")

    # 2. Neo4j Graph Stats
    neo4j_nodes = 0
    neo4j_edges = 0
    neo4j_status = "Online"
    try:
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        with driver.session() as s:
            r_n = s.run("MATCH (n) RETURN count(n) as c;").single()
            neo4j_nodes = r_n["c"] if r_n else 0
            r_e = s.run("MATCH ()-[r]->() RETURN count(r) as c;").single()
            neo4j_edges = r_e["c"] if r_e else 0
        driver.close()
    except Exception as e:
        neo4j_status = f"Offline ({e})"

    # 3. Qdrant Vector Stats
    qdrant_points = 0
    qdrant_collections_count = 0
    qdrant_status = "Online"
    try:
        q_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        cols = q_client.get_collections().collections
        qdrant_collections_count = len(cols)
        for c in cols:
            info = q_client.get_collection(collection_name=c.name)
            qdrant_points += info.points_count or 0
    except Exception as e:
        qdrant_status = f"Offline ({e})"

    return {
        "status": "online",
        "users": {"total": user_count, "active_sessions": session_count},
        "projects": {"total": project_count},
        "neo4j": {"status": neo4j_status, "nodes": neo4j_nodes, "edges": neo4j_edges},
        "qdrant": {"status": qdrant_status, "collections": qdrant_collections_count, "total_vectors": qdrant_points},
        "server": {
            "host": settings.rip_server_host,
            "port": settings.rip_server_port,
            "primary_model": settings.llm_primary_model,
        },
    }

@router.get("/api/users")
async def get_admin_users(
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: str | None = Header(default=None),
    key: str | None = None,
) -> dict[str, Any]:
    """List all registered users, OAuth connections, and active sessions."""
    verify_admin_key(x_admin_key, key)
    try:
        res = await db.execute(text("""
            SELECT u.id, u.email, u.display_name, u.avatar_url, u.created_at, u.last_login_at,
                   oa.provider, oa.provider_username,
                   s.token_prefix, s.created_at as session_created
            FROM users u
            LEFT JOIN user_oauth_accounts oa ON u.id = oa.user_id
            LEFT JOIN user_sessions s ON u.id = s.user_id AND s.revoked_at IS NULL
            ORDER BY u.created_at DESC;
        """))
        rows = res.fetchall()
        users_list = []
        for r in rows:
            users_list.append({
                "id": r[0],
                "email": r[1] or "N/A",
                "display_name": r[2],
                "avatar_url": r[3],
                "created_at": str(r[4]) if r[4] else None,
                "last_login_at": str(r[5]) if r[5] else None,
                "oauth_provider": r[6] or "direct",
                "github_username": r[7] or "N/A",
                "active_token_prefix": r[8] or "No Active Session",
                "session_created": str(r[9]) if r[9] else None,
            })
        return {"status": "success", "count": len(users_list), "users": users_list}
    except Exception as e:
        return {"status": "error", "message": str(e), "users": []}

@router.get("/api/db/{table_name}")
async def get_db_table_data(
    table_name: str,
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: str | None = Header(default=None),
    key: str | None = None,
) -> dict[str, Any]:
    """Inspect raw rows of any database table."""
    verify_admin_key(x_admin_key, key)
    allowed_tables = {"users", "user_sessions", "user_oauth_accounts", "projects", "chat_sessions", "chat_messages", "index_jobs"}
    if table_name not in allowed_tables:
        raise HTTPException(status_code=400, detail=f"Access denied to table '{table_name}'")

    try:
        res = await db.execute(text(f"SELECT * FROM {table_name} LIMIT 100;"))
        keys = res.keys()
        rows = [dict(zip(keys, row)) for row in res.fetchall()]
        return {"status": "success", "table": table_name, "count": len(rows), "rows": rows}
    except Exception as e:
        return {"status": "error", "message": str(e), "table": table_name, "rows": []}

@router.post("/api/purge")
async def purge_all_databases(
    db: AsyncSession = Depends(get_db_session),
    x_admin_key: str | None = Header(default=None),
    key: str | None = None,
) -> dict[str, Any]:
    """Purge all databases to 0."""
    verify_admin_key(x_admin_key, key)
    settings = get_settings()

    # 1. Clear PostgreSQL
    tables = ["chat_messages", "chat_sessions", "index_jobs", "user_sessions", "user_oauth_accounts", "projects", "users"]
    cleared = []
    for t in tables:
        try:
            await db.execute(text(f"DELETE FROM {t};"))
            await db.commit()
            cleared.append(t)
        except Exception:
            await db.rollback()

    # 2. Clear Neo4j
    try:
        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n;")
        driver.close()
    except Exception:
        pass

    # 3. Clear Qdrant
    try:
        q_client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        cols = q_client.get_collections().collections
        for c in cols:
            q_client.delete_collection(collection_name=c.name)
    except Exception:
        pass

    return {"status": "success", "message": "All databases purged to 0", "cleared_tables": cleared}

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard_ui():
    """Single-page Admin Dashboard HTML, CSS, JS Web Interface."""
    return HTMLResponse(content=HTML_ADMIN_PANEL)

HTML_ADMIN_PANEL = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RIP Platform — Admin Telemetry & Database Control</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0B0F17;
            --surface: #131B2E;
            --surface-card: #1E293B;
            --surface-border: rgba(255, 255, 255, 0.08);
            --primary: #38BDF8;
            --primary-glow: rgba(56, 189, 248, 0.25);
            --accent: #818CF8;
            --success: #34D399;
            --danger: #F87171;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }
        body { background-color: var(--bg); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; }

        /* Lock Screen Modal */
        #lock-screen {
            position: fixed; inset: 0; background: rgba(11, 15, 23, 0.95); backdrop-filter: blur(16px);
            display: flex; align-items: center; justify-content: center; z-index: 1000;
        }
        .login-card {
            background: var(--surface); border: 1px solid var(--surface-border); border-radius: 24px;
            padding: 40px; width: 100%; max-width: 420px; text-align: center; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
        }
        .login-card h2 { font-size: 24px; margin-bottom: 8px; color: var(--primary); font-weight: 700; }
        .login-card p { font-size: 13px; color: var(--text-muted); margin-bottom: 24px; }
        .input-group { margin-bottom: 20px; text-align: left; }
        .input-group label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 6px; font-weight: 600; }
        .input-field {
            width: 100%; padding: 12px 16px; background: rgba(255,255,255,0.04); border: 1px solid var(--surface-border);
            border-radius: 12px; color: var(--text-main); font-size: 14px; font-family: 'JetBrains Mono', monospace; outline: none; transition: all 0.2s;
        }
        .input-field:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
        .btn-primary {
            width: 100%; padding: 12px; background: linear-gradient(135deg, #0EA5E9, #2563EB); border: none; border-radius: 12px;
            color: white; font-weight: 700; font-size: 14px; cursor: pointer; transition: transform 0.1s, opacity 0.2s;
        }
        .btn-primary:hover { opacity: 0.92; }
        .btn-primary:active { transform: scale(0.98); }

        /* Top Nav Bar */
        header {
            background: rgba(19, 27, 46, 0.8); backdrop-filter: blur(12px); border-bottom: 1px solid var(--surface-border);
            padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; sticky: top: 0; z-index: 100;
        }
        .logo-group { display: flex; align-items: center; gap: 12px; }
        .logo-badge { background: linear-gradient(135deg, #38BDF8, #818CF8); width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; }
        .logo-text { font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }
        .nav-status { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-muted); }
        .status-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; box-shadow: 0 0 8px var(--success); }

        /* Main Dashboard Grid */
        main { padding: 32px; max-width: 1400px; margin: 0 auto; width: 100%; display: flex; flex-direction: column; gap: 28px; }

        /* KPI Metric Cards */
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
        .kpi-card {
            background: var(--surface); border: 1px solid var(--surface-border); border-radius: 18px; padding: 20px;
            display: flex; flex-direction: column; gap: 8px; position: relative; overflow: hidden; transition: transform 0.2s;
        }
        .kpi-card:hover { transform: translateY(-2px); }
        .kpi-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text-muted); font-weight: 600; }
        .kpi-value { font-size: 32px; font-weight: 800; color: var(--text-main); letter-spacing: -0.5px; }
        .kpi-sub { font-size: 11.5px; color: var(--text-muted); }

        /* Section Layout */
        .section-card {
            background: var(--surface); border: 1px solid var(--surface-border); border-radius: 20px; padding: 24px;
            display: flex; flex-direction: column; gap: 18px;
        }
        .section-header { display: flex; justify-content: space-between; align-items: center; }
        .section-title { font-size: 16px; font-weight: 700; color: var(--text-main); }

        /* Data Tables */
        .table-container { width: 100%; overflow-x: auto; border-radius: 12px; border: 1px solid var(--surface-border); }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
        th { background: rgba(255,255,255,0.03); padding: 12px 16px; color: var(--text-muted); font-weight: 600; border-bottom: 1px solid var(--surface-border); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
        td { padding: 14px 16px; border-bottom: 1px solid var(--surface-border); color: var(--text-main); }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(255,255,255,0.02); }

        .pill-badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: 600; }
        .badge-github { background: rgba(56, 189, 248, 0.15); color: #38BDF8; }
        .badge-active { background: rgba(52, 211, 153, 0.15); color: #34D399; }
        .code-text { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #E2E8F0; }

        /* Controls Row */
        .controls-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .select-field {
            padding: 10px 14px; background: rgba(255,255,255,0.04); border: 1px solid var(--surface-border);
            border-radius: 10px; color: var(--text-main); font-size: 13px; outline: none; cursor: pointer;
        }

        .btn-danger {
            background: rgba(248, 113, 113, 0.15); border: 1px solid rgba(248, 113, 113, 0.3); color: var(--danger);
            padding: 10px 18px; border-radius: 10px; font-weight: 600; font-size: 13px; cursor: pointer; transition: all 0.2s;
        }
        .btn-danger:hover { background: rgba(248, 113, 113, 0.25); }

        /* Pre/JSON Viewer */
        .json-box {
            background: #090D16; border: 1px solid var(--surface-border); border-radius: 12px; padding: 16px;
            font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #38BDF8; overflow-x: auto; max-height: 320px;
        }
    </style>
</head>
<body>

    <!-- LOCK SCREEN -->
    <div id="lock-screen">
        <div class="login-card">
            <h2>RIP Admin Gateway</h2>
            <p>Enter secret access key to view telemetry & data</p>
            <div class="input-group">
                <label>Admin Secret Key</label>
                <input type="password" id="admin-key-input" class="input-field" value="admin123" placeholder="Enter Admin Secret">
            </div>
            <button class="btn-primary" onclick="unlockAdmin()">Unlock Dashboard</button>
        </div>
    </div>

    <!-- MAIN APP INTERFACE -->
    <header>
        <div class="logo-group">
            <div class="logo-badge">R</div>
            <div class="logo-text">RIP Admin Control Center</div>
        </div>
        <div class="nav-status">
            <div class="status-dot"></div>
            <span>Connected to Server (Port 8000)</span>
        </div>
    </header>

    <main>
        <!-- KPI METRICS ROW -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Registered Users</div>
                <div class="kpi-value" id="kpi-users">0</div>
                <div class="kpi-sub" id="kpi-sessions">0 Active Sessions</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Active Workspaces</div>
                <div class="kpi-value" id="kpi-projects">0</div>
                <div class="kpi-sub">Indexed Repositories</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Neo4j Graph Nodes</div>
                <div class="kpi-value" id="kpi-neo4j-nodes">0</div>
                <div class="kpi-sub" id="kpi-neo4j-edges">0 Graph Edges</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Qdrant Vectors</div>
                <div class="kpi-value" id="kpi-qdrant-points">0</div>
                <div class="kpi-sub" id="kpi-qdrant-cols">0 Collections</div>
            </div>
        </div>

        <!-- USER ACCOUNTS & OAUTH SESSIONS -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">User Accounts & Active OAuth Sessions</div>
                <button class="btn-primary" style="width: auto; padding: 8px 16px; font-size: 12px;" onclick="loadUsers()">Refresh Users</button>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>User ID</th>
                            <th>Display Name</th>
                            <th>Email</th>
                            <th>Auth Provider</th>
                            <th>GitHub Username</th>
                            <th>Active API Key Prefix</th>
                            <th>Created At</th>
                        </tr>
                    </thead>
                    <tbody id="users-table-body">
                        <tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading users...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- DATABASE TABLE EXPLORER -->
        <div class="section-card">
            <div class="section-header">
                <div class="section-title">Database Table Inspector</div>
                <div class="controls-row">
                    <select id="table-select" class="select-field" onchange="inspectTable()">
                        <option value="users">Table: users</option>
                        <option value="user_sessions">Table: user_sessions</option>
                        <option value="user_oauth_accounts">Table: user_oauth_accounts</option>
                        <option value="projects">Table: projects</option>
                    </select>
                    <button class="btn-primary" style="width: auto; padding: 8px 16px; font-size: 12px;" onclick="inspectTable()">Load Table</button>
                </div>
            </div>
            <div class="json-box" id="json-inspector">Select a table above to inspect raw database rows...</div>
        </div>

        <!-- SYSTEM MAINTENANCE & PURGE -->
        <div class="section-card" style="border-color: rgba(248, 113, 113, 0.3);">
            <div class="section-header">
                <div>
                    <div class="section-title" style="color: var(--danger);">System Maintenance & Purge</div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Reset all system databases back to 0 for fresh testing</div>
                </div>
                <button class="btn-danger" onclick="purgeAllData()">Purge System DBs to 0</button>
            </div>
        </div>
    </main>

    <script>
        let adminKey = "admin123";

        function unlockAdmin() {
            const input = document.getElementById("admin-key-input").value.trim();
            if (!input) return alert("Please enter secret key");
            adminKey = input;
            document.getElementById("lock-screen").style.display = "none";
            refreshAll();
        }

        async function fetchApi(endpoint, options = {}) {
            options.headers = options.headers || {};
            options.headers["x-admin-key"] = adminKey;
            const res = await fetch(endpoint, options);
            if (res.status === 401) {
                alert("Unauthorized key");
                document.getElementById("lock-screen").style.display = "flex";
                throw new Error("Unauthorized");
            }
            return res.json();
        }

        async function loadStats() {
            try {
                const data = await fetchApi("/admin/api/stats");
                document.getElementById("kpi-users").innerText = data.users.total;
                document.getElementById("kpi-sessions").innerText = `${data.users.active_sessions} Active Sessions`;
                document.getElementById("kpi-projects").innerText = data.projects.total;
                document.getElementById("kpi-neo4j-nodes").innerText = data.neo4j.nodes;
                document.getElementById("kpi-neo4j-edges").innerText = `${data.neo4j.edges} Graph Edges`;
                document.getElementById("kpi-qdrant-points").innerText = data.qdrant.total_vectors;
                document.getElementById("kpi-qdrant-cols").innerText = `${data.qdrant.collections} Collections`;
            } catch (e) {
                console.error("Failed to load stats:", e);
            }
        }

        async function loadUsers() {
            try {
                const data = await fetchApi("/admin/api/users");
                const tbody = document.getElementById("users-table-body");
                if (!data.users || data.users.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">No registered users found in DB (0 users).</td></tr>`;
                    return;
                }
                tbody.innerHTML = data.users.map(u => `
                    <tr>
                        <td class="code-text">${u.id.substring(0, 8)}...</td>
                        <td><strong>${u.display_name}</strong></td>
                        <td>${u.email}</td>
                        <td><span class="pill-badge badge-github">${u.oauth_provider.toUpperCase()}</span></td>
                        <td>@${u.github_username}</td>
                        <td><span class="pill-badge badge-active">${u.active_token_prefix}</span></td>
                        <td style="color: var(--text-muted);">${u.created_at ? u.created_at.split('T')[0] : 'N/A'}</td>
                    </tr>
                `).join("");
            } catch (e) {
                console.error("Failed to load users:", e);
            }
        }

        async function inspectTable() {
            const table = document.getElementById("table-select").value;
            try {
                const data = await fetchApi(`/admin/api/db/${table}`);
                document.getElementById("json-inspector").innerText = JSON.stringify(data.rows, null, 2);
            } catch (e) {
                document.getElementById("json-inspector").innerText = `Error: ${e.message}`;
            }
        }

        async function purgeAllData() {
            if (!confirm("Are you sure you want to PURGE all system databases (PostgreSQL, Neo4j, Qdrant) back to 0?")) return;
            try {
                const data = await fetchApi("/admin/api/purge", { method: "POST" });
                alert(data.message || "Databases purged!");
                refreshAll();
            } catch (e) {
                alert("Purge failed: " + e.message);
            }
        }

        function refreshAll() {
            loadStats();
            loadUsers();
            inspectTable();
        }
    </script>
</body>
</html>
"""
