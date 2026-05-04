import streamlit as st
import requests
import time
from itertools import combinations

SUPABASE_URL = "https://mynyuizinwafjmapakwi.supabase.co"
SUPABASE_KEY = "sb_publishable_6MOov8BMcqkHNxko-GskYw_jol3e0x2"
ADMIN_PASSWORD = "admin123"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

st.set_page_config(page_title="Wine Challenge", page_icon="🍷", layout="centered")

st.markdown(
    """
    <style>
    .block-container {
        max-width: 640px;
        padding-top: 1.2rem;
        padding-bottom: 4rem;
    }
    .hero {
        padding: 18px 16px;
        border-radius: 22px;
        background: linear-gradient(135deg, #fff7f7, #f7f3ff);
        border: 1px solid #eee;
        margin-bottom: 16px;
    }
    .hero-title {
        font-size: 2.0rem;
        font-weight: 800;
        line-height: 1.05;
        margin-bottom: 4px;
    }
    .muted {
        color: #666;
        font-size: 0.95rem;
    }
    .wine-big {
        text-align: center;
        padding: 24px 16px;
        border-radius: 24px;
        border: 1px solid #eee;
        background: #ffffff;
        margin: 12px 0 18px 0;
    }
    .wine-number {
        font-size: 3.3rem;
        font-weight: 900;
        line-height: 1;
    }
    .result-card {
        padding: 14px;
        border: 1px solid #eee;
        border-radius: 16px;
        margin-bottom: 10px;
        background: #fff;
    }
    .winner-card {
        padding: 18px;
        border-radius: 22px;
        border: 1px solid #ffe0a3;
        background: #fff7df;
        margin-bottom: 16px;
    }
    .status-row {
        padding: 8px 10px;
        border-radius: 12px;
        margin-bottom: 6px;
        background: #fafafa;
        border: 1px solid #eee;
    }
    div.stButton > button {
        min-height: 44px;
        border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_url(table):
    return f"{SUPABASE_URL}/rest/v1/{table}"


def supabase_get(table, params=None):
    response = requests.get(api_url(table), headers=HEADERS, params=params or {})
    response.raise_for_status()
    return response.json()


def supabase_post(table, data):
    response = requests.post(api_url(table), headers=HEADERS, json=data)
    response.raise_for_status()
    return response.json()


def supabase_patch(table, data, params):
    response = requests.patch(api_url(table), headers=HEADERS, json=data, params=params)
    response.raise_for_status()
    return response.json()


def get_games():
    return supabase_get("games", {"select": "*", "order": "id.desc"})


def get_game(game_id):
    rows = supabase_get("games", {"select": "*", "id": f"eq.{game_id}"})
    return rows[0] if rows else None


def create_game(motto, max_players, wine_count):
    return supabase_post("games", {
        "motto": motto.strip(),
        "max_players": int(max_players),
        "wine_count": int(wine_count),
        "status": "open",
        "current_wine": 1,
    })


def update_game(game_id, data):
    return supabase_patch("games", data, {"id": f"eq.{game_id}"})


def get_players(game_id):
    return supabase_get("players", {
        "select": "*",
        "game_id": f"eq.{game_id}",
        "order": "name.asc",
    })


def get_player(game_id, name):
    rows = supabase_get("players", {
        "select": "*",
        "game_id": f"eq.{game_id}",
        "name": f"eq.{name.strip()}",
    })
    return rows[0] if rows else None


def join_game(game, name):
    existing = get_player(game["id"], name)
    if existing:
        return existing["id"]

    if game["status"] == "finished":
        st.warning("Diese Challenge ist bereits beendet. Du kannst nur noch die Rangliste ansehen.")
        return None

    players = get_players(game["id"])
    if len(players) >= game["max_players"]:
        st.error("Dieses Spiel ist bereits voll.")
        return None

    result = supabase_post("players", {
        "game_id": game["id"],
        "name": name.strip(),
    })
    return result[0]["id"]


def get_ratings(game_id):
    return supabase_get("ratings", {
        "select": "*",
        "game_id": f"eq.{game_id}",
    })


def get_rating(game_id, player_id, wine_no):
    rows = supabase_get("ratings", {
        "select": "*",
        "game_id": f"eq.{game_id}",
        "player_id": f"eq.{player_id}",
        "wine_no": f"eq.{wine_no}",
    })
    return rows[0] if rows else None


def save_rating(game_id, player_id, wine_no, score, comment):
    existing = get_rating(game_id, player_id, wine_no)
    if existing:
        return supabase_patch(
            "ratings",
            {"score": float(score), "comment": comment},
            {"id": f"eq.{existing['id']}"},
        )

    return supabase_post("ratings", {
        "game_id": game_id,
        "player_id": player_id,
        "wine_no": wine_no,
        "score": float(score),
        "comment": comment,
    })


def rating_options():
    values = []
    x = 1.0
    while x <= 6.0001:
        values.append(round(x, 2))
        x += 0.25
    return values


def rating_label(value):
    labels = {
        6.0: "6.00 · Exzellent",
        5.5: "5.50 · Sehr gut",
        5.0: "5.00 · Gut",
        4.0: "4.00 · Genügend",
        3.0: "3.00 · Ungenügend",
        2.0: "2.00 · Miserabel",
        1.0: "1.00 · Unterirdisch",
    }
    return labels.get(float(value), f"{value:.2f}")


def calculate_buddies(players, ratings):
    rating_map = {}
    for p in players:
        rating_map[p["id"]] = {
            r["wine_no"]: float(r["score"])
            for r in ratings
            if r["player_id"] == p["id"]
        }

    buddy_by_player = {}
    for p in players:
        best_buddy = None
        best_diff = 999
        best_common = 0

        for other in players:
            if p["id"] == other["id"]:
                continue

            common_wines = set(rating_map[p["id"]]) & set(rating_map[other["id"]])
            if not common_wines:
                continue

            diff = sum(abs(rating_map[p["id"]][w] - rating_map[other["id"]][w]) for w in common_wines) / len(common_wines)
            if diff < best_diff or (diff == best_diff and len(common_wines) > best_common):
                best_diff = diff
                best_buddy = other
                best_common = len(common_wines)

        if best_buddy:
            buddy_by_player[p["id"]] = {
                "name": best_buddy["name"],
                "diff": best_diff,
                "common": best_common,
            }

    return buddy_by_player


def calculate_stats(game_id):
    game = get_game(game_id)
    players = get_players(game_id)
    ratings = get_ratings(game_id)
    player_names = {p["id"]: p["name"] for p in players}

    ranking = []
    for wine_no in range(1, game["wine_count"] + 1):
        wine_scores = [float(r["score"]) for r in ratings if r["wine_no"] == wine_no]
        if wine_scores:
            ranking.append({
                "wine_no": wine_no,
                "avg": sum(wine_scores) / len(wine_scores),
                "count": len(wine_scores),
            })

    ranking.sort(key=lambda x: x["avg"], reverse=True)
    highest = max(ratings, key=lambda r: float(r["score"]), default=None)
    lowest = min(ratings, key=lambda r: float(r["score"]), default=None)
    buddy_by_player = calculate_buddies(players, ratings)

    return game, players, ratings, ranking, highest, lowest, buddy_by_player, player_names


def render_hero(title, subtitle=None):
    st.markdown(
        f"""
        <div class='hero'>
            <div class='hero-title'>{title}</div>
            <div class='muted'>{subtitle or ''}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def login():
    render_hero("🍷 Wine Challenge", "Degustieren. Bewerten. Trink-Buddy finden.")
    name = st.text_input("Dein Name", placeholder="z.B. Ced")
    if st.button("Einloggen", use_container_width=True, type="primary"):
        if len(name.strip()) < 2:
            st.error("Bitte gib einen Namen ein.")
        else:
            st.session_state.name = name.strip()
            st.rerun()


def admin():
    st.subheader("Admin Bereich")
    pw = st.text_input("Passwort", type="password")
    if pw != ADMIN_PASSWORD:
        st.info("Admin Passwort eingeben.")
        return

    st.markdown("### Neues Spiel erstellen")
    motto = st.text_input("Motto", placeholder="z.B. Italien - Toskana")
    players = st.number_input("Max. Spieler", 1, 12, 6)
    wines = st.number_input("Anzahl Weine", 1, 12, 5)

    if st.button("Spiel erstellen", use_container_width=True, type="primary"):
        if not motto.strip():
            st.error("Bitte Motto eingeben.")
        else:
            create_game(motto, players, wines)
            st.success("Spiel erstellt ✅")
            st.rerun()

    st.divider()
    st.markdown("### Spiele steuern")

    for game in get_games():
        current_wine = int(game.get("current_wine") or 1)
        player_count = len(get_players(game["id"]))
        rating_count = len(get_ratings(game["id"]))

        with st.expander(f"#{game['id']} · {game['motto']} · {game['status']}", expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.metric("Spieler", f"{player_count}/{game['max_players']}")
            c2.metric("Wein", f"{current_wine}/{game['wine_count']}")
            c3.metric("Bewertungen", rating_count)

            if game["status"] == "running":
                st.progress(current_wine / game["wine_count"])

            col1, col2, col3 = st.columns(3)
            if col1.button("Lobby öffnen", key=f"open_{game['id']}", use_container_width=True):
                update_game(game["id"], {"status": "open", "current_wine": 1})
                st.rerun()
            if col2.button("Starten", key=f"run_{game['id']}", use_container_width=True):
                update_game(game["id"], {"status": "running", "current_wine": current_wine})
                st.rerun()
            if col3.button("Beenden", key=f"close_{game['id']}", use_container_width=True):
                update_game(game["id"], {"status": "finished"})
                st.rerun()

            st.markdown("#### Wein steuern")
            nav1, nav2 = st.columns(2)
            if nav1.button("← Vorheriger Wein", key=f"prev_{game['id']}", use_container_width=True, disabled=current_wine <= 1):
                update_game(game["id"], {"current_wine": max(1, current_wine - 1)})
                st.rerun()
            if nav2.button("Nächster Wein →", key=f"next_{game['id']}", use_container_width=True, disabled=current_wine >= game["wine_count"]):
                update_game(game["id"], {"current_wine": min(game["wine_count"], current_wine + 1)})
                st.rerun()

            manual_wine = st.number_input(
                "Aktueller Wein manuell setzen",
                min_value=1,
                max_value=int(game["wine_count"]),
                value=current_wine,
                key=f"manual_wine_{game['id']}",
            )
            if st.button("Wein setzen", key=f"set_wine_{game['id']}", use_container_width=True):
                update_game(game["id"], {"current_wine": int(manual_wine)})
                st.rerun()


def lobby(game, players):
    render_hero(f"🍷 {game['motto']}", "Lobby · Warten auf Start")
    st.info("Du bist beigetreten. Der Admin startet die Challenge, sobald alle bereit sind.")
    st.metric("Spieler", f"{len(players)}/{game['max_players']}")

    st.markdown("### Teilnehmende")
    if not players:
        st.write("Noch niemand beigetreten.")
    for p in players:
        st.markdown(f"<div class='status-row'>✅ {p['name']}</div>", unsafe_allow_html=True)

    if st.button("Status aktualisieren", use_container_width=True):
        st.rerun()


def current_buddy_box(pid, players, ratings):
    buddy_by_player = calculate_buddies(players, ratings)
    buddy = buddy_by_player.get(pid)
    if buddy:
        st.success(f"Aktueller Trink-Buddy: {buddy['name']} 🍷 · Ø Differenz {buddy['diff']:.2f} · gemeinsame Weine {buddy['common']}")
    else:
        st.info("Aktueller Trink-Buddy: noch nicht berechenbar. Dafür braucht es mindestens einen gemeinsamen bewerteten Wein.")


def wait_for_next_wine(game, pid, waiting_for_wine):
    latest_game = get_game(game["id"])
    latest_wine = int(latest_game.get("current_wine") or 1)

    render_hero(
        f"🍷 {latest_game['motto']}",
        f"Warten auf Freigabe · Wein {waiting_for_wine} bewertet",
    )

    if latest_game["status"] == "finished":
        st.session_state.pop("waiting_for_wine", None)
        dashboard(latest_game["id"], pid)
        return

    if latest_wine > waiting_for_wine:
        st.session_state.pop("waiting_for_wine", None)
        st.success(f"Wein Nr. {latest_wine} ist freigeschaltet ✅")
        time.sleep(1)
        st.rerun()

    st.markdown(
        f"""
        <div class='wine-big'>
            <div class='muted'>Deine Bewertung ist gespeichert</div>
            <div class='wine-number'>#{waiting_for_wine}</div>
            <div class='muted'>Bitte warten, bis der Admin den nächsten Wein freischaltet.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Warte auf den nächsten Wein..."):
        time.sleep(3)
        st.rerun()


def player_running(game, pid):
    current_wine = int(game.get("current_wine") or 1)

    waiting_for_wine = st.session_state.get("waiting_for_wine")
    if waiting_for_wine is not None and int(waiting_for_wine) >= current_wine:
        wait_for_next_wine(game, pid, int(waiting_for_wine))
        return

    players = get_players(game["id"])
    ratings = get_ratings(game["id"])
    existing_rating = get_rating(game["id"], pid, current_wine)

    render_hero(f"🍷 {game['motto']}", f"Bewertung läuft · Wein {current_wine} von {game['wine_count']}")

    st.progress(current_wine / game["wine_count"])

    st.markdown(
        f"""
        <div class='wine-big'>
            <div class='muted'>Aktueller Wein</div>
            <div class='wine-number'>#{current_wine}</div>
            <div class='muted'>Bewerte diesen Wein. Danach kannst du auf den nächsten Wein warten.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rated_player_ids = {r["player_id"] for r in ratings if r["wine_no"] == current_wine}
    st.markdown("### Status für diesen Wein")
    st.caption(f"{len(rated_player_ids)}/{len(players)} haben Wein Nr. {current_wine} bewertet")

    with st.expander("Spielerstatus anzeigen", expanded=True):
        for p in players:
            if p["id"] in rated_player_ids:
                st.markdown(f"<div class='status-row'>✅ {p['name']} hat bewertet</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='status-row'>⏳ {p['name']} noch offen</div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Deine Bewertung")

    default_score = float(existing_rating["score"]) if existing_rating else 4.0
    default_comment = existing_rating.get("comment") if existing_rating else ""
    default_comment = default_comment or ""

    score = st.select_slider(
        "Note",
        options=rating_options(),
        value=default_score,
        format_func=rating_label,
        key=f"score_{game['id']}_{pid}_{current_wine}",
    )
    comment = st.text_area(
        "Kommentar",
        value=default_comment,
        placeholder="Aroma, Geschmack, Eindruck...",
        key=f"comment_{game['id']}_{pid}_{current_wine}",
    )

    changed = False
    if existing_rating:
        if float(score) != float(existing_rating["score"]) or comment != (existing_rating.get("comment") or ""):
            changed = True
    else:
        if float(score) != 4.0 or comment.strip() != "":
            changed = True

    if "saved_until" not in st.session_state:
        st.session_state.saved_until = {}

    message_key = f"{game['id']}_{pid}_{current_wine}"
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Speichern", use_container_width=True, type="primary"):
            save_rating(game["id"], pid, current_wine, score, comment)
            st.session_state.saved_until[message_key] = time.time() + 5
            st.rerun()
    with col2:
        saved_until = st.session_state.saved_until.get(message_key, 0)
        if time.time() < saved_until:
            st.success("Wert gespeichert ✅")
        elif changed:
            st.warning("Achtung: Neuer Wert noch nicht gespeichert ⚠️")
        elif existing_rating:
            st.info("Dein Wert ist gespeichert.")

    latest_rating = get_rating(game["id"], pid, current_wine)
    if latest_rating and not changed:
        if current_wine < int(game["wine_count"]):
            if st.button("Weiter · Auf nächsten Wein warten", use_container_width=True):
                st.session_state.waiting_for_wine = current_wine
                st.rerun()
        else:
            if st.button("Fertig · Auf Resultate warten", use_container_width=True):
                st.session_state.waiting_for_wine = current_wine
                st.rerun()

    st.divider()
    st.markdown("### Trink-Buddy live")
    current_buddy_box(pid, players, ratings)

    if st.button("Aktualisieren", use_container_width=True):
        st.rerun()


def dashboard(game_id, player_id=None):
    game, players, ratings, ranking, highest, lowest, buddy_by_player, player_names = calculate_stats(game_id)

    render_hero(f"🏁 Challenge beendet", game["motto"])

    if not ranking:
        st.info("Noch keine Bewertungen vorhanden.")
        return

    top_wine = ranking[0]
    st.markdown(
        f"""
        <div class='winner-card'>
            <div class='muted'>Gewinner</div>
            <div style='font-size: 2rem; font-weight: 900;'>🥇 Wein Nr. {top_wine['wine_no']}</div>
            <div>Durchschnitt: {top_wine['avg']:.2f} Punkte · {top_wine['count']} Bewertungen</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Rangliste der Weine")
    for index, row in enumerate(ranking, start=1):
        medal = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else "🍷"
        st.markdown(
            f"""
            <div class='result-card'>
                <b>{medal} {index}. Platz · Wein Nr. {row['wine_no']}</b><br>
                Durchschnitt: {row['avg']:.2f} Punkte<br>
                Anzahl Bewertungen: {row['count']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    if highest:
        col1.metric(
            "Höchste Einzelbewertung",
            f"{float(highest['score']):.2f}",
            f"Wein {highest['wine_no']} · {player_names.get(highest['player_id'], 'Unbekannt')}",
        )
    if lowest:
        col2.metric(
            "Tiefste Einzelbewertung",
            f"{float(lowest['score']):.2f}",
            f"Wein {lowest['wine_no']} · {player_names.get(lowest['player_id'], 'Unbekannt')}",
        )

    st.subheader("Trink-Buddy")
    if player_id and player_id in buddy_by_player:
        buddy = buddy_by_player[player_id]
        st.success(f"Dein Trink-Buddy ist {buddy['name']} 🍷 · Ø Differenz {buddy['diff']:.2f} · gemeinsame Weine {buddy['common']}")
    else:
        for p in players:
            buddy = buddy_by_player.get(p["id"])
            if buddy:
                st.write(f"{p['name']} → {buddy['name']} · Ø Differenz {buddy['diff']:.2f}")

    with st.expander("Einzelbewertungen anzeigen"):
        for r in sorted(ratings, key=lambda x: (x["wine_no"], player_names.get(x["player_id"], ""))):
            st.write(f"Wein {r['wine_no']} · {player_names.get(r['player_id'], 'Unbekannt')} · {float(r['score']):.2f} · {r.get('comment') or ''}")


def player():
    name = st.session_state.name

    games = get_games()
    if not games:
        render_hero("🍷 Wine Challenge", f"Eingeloggt als {name}")
        st.info("Kein Spiel vorhanden")
        return

    game = st.selectbox("Spiel wählen", games, format_func=lambda x: f"{x['motto']} · {x['status']}")
    game = get_game(game["id"])
    game_id = game["id"]

    existing_player = get_player(game_id, name)
    if existing_player:
        pid = existing_player["id"]
    else:
        pid = join_game(game, name)

    if game["status"] == "finished":
        dashboard(game_id, pid)
        return

    if pid is None:
        return

    players = get_players(game_id)

    if game["status"] == "open":
        lobby(game, players)
        return

    player_running(game, pid)


def main():
    if SUPABASE_KEY == "DEIN_NEUER_PUBLISHABLE_KEY":
        st.error("Bitte zuerst SUPABASE_KEY im Code ersetzen.")
        return

    if "name" not in st.session_state:
        login()
        return

    menu = st.radio("Menü", ["Spieler", "Admin"], horizontal=True)

    if menu == "Spieler":
        player()
    else:
        admin()

    st.divider()
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()


if __name__ == "__main__":
    main()
