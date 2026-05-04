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
    .block-container {max-width: 620px; padding-top: 1.5rem;}
    .result-card {padding: 14px; border: 1px solid #eee; border-radius: 14px; margin-bottom: 10px; background: #fff;}
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


def create_game(motto, max_players, wine_count):
    return supabase_post("games", {
        "motto": motto.strip(),
        "max_players": int(max_players),
        "wine_count": int(wine_count),
        "status": "open",
    })


def update_game_status(game_id, status):
    return supabase_patch("games", {"status": status}, {"id": f"eq.{game_id}"})


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

    data = {
        "game_id": game_id,
        "player_id": player_id,
        "wine_no": wine_no,
        "score": float(score),
        "comment": comment,
    }

    if existing:
        return supabase_patch(
            "ratings",
            {"score": float(score), "comment": comment},
            {"id": f"eq.{existing['id']}"},
        )
    return supabase_post("ratings", data)


def rating_options():
    values = []
    x = 1.0
    while x <= 6.0001:
        values.append(round(x, 2))
        x += 0.25
    return values


def calculate_stats(game_id):
    games = supabase_get("games", {"select": "*", "id": f"eq.{game_id}"})
    game = games[0]
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
        for other in players:
            if p["id"] == other["id"]:
                continue
            common_wines = set(rating_map[p["id"]]) & set(rating_map[other["id"]])
            if not common_wines:
                continue
            diff = sum(abs(rating_map[p["id"]][w] - rating_map[other["id"]][w]) for w in common_wines) / len(common_wines)
            if diff < best_diff:
                best_diff = diff
                best_buddy = other

        if best_buddy:
            buddy_by_player[p["id"]] = {
                "name": best_buddy["name"],
                "diff": best_diff,
            }

    return game, players, ratings, ranking, highest, lowest, buddy_by_player, player_names


def login():
    st.title("🍷 Wine Challenge")
    st.caption("Degustieren. Bewerten. Trink-Buddy finden.")
    name = st.text_input("Dein Name", placeholder="z.B. Ced")
    if st.button("Einloggen", use_container_width=True):
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

    if st.button("Spiel erstellen", use_container_width=True):
        if not motto.strip():
            st.error("Bitte Motto eingeben.")
        else:
            create_game(motto, players, wines)
            st.success("Spiel erstellt ✅")
            st.rerun()

    st.divider()
    st.markdown("### Spiele verwalten")

    for game in get_games():
        player_count = len(get_players(game["id"]))
        rating_count = len(get_ratings(game["id"]))

        with st.expander(f"#{game['id']} · {game['motto']} · Status: {game['status']}"):
            st.write(f"Spieler: {player_count}/{game['max_players']}")
            st.write(f"Bewertungen: {rating_count}")

            col1, col2, col3 = st.columns(3)
            if col1.button("Öffnen", key=f"open_{game['id']}"):
                update_game_status(game["id"], "open")
                st.rerun()
            if col2.button("Starten", key=f"run_{game['id']}"):
                update_game_status(game["id"], "running")
                st.rerun()
            if col3.button("Schliessen", key=f"close_{game['id']}"):
                update_game_status(game["id"], "finished")
                st.rerun()


def dashboard(game_id, player_id=None):
    game, players, ratings, ranking, highest, lowest, buddy_by_player, player_names = calculate_stats(game_id)

    st.success("Challenge beendet ✅")
    st.title(f"🍷 {game['motto']}")
    st.subheader("Rangliste der Weine")

    if not ranking:
        st.info("Noch keine Bewertungen vorhanden.")
        return

    for index, row in enumerate(ranking, start=1):
        st.markdown(
            f"""
            <div class='result-card'>
                <b>{index}. Platz · Wein Nr. {row['wine_no']}</b><br>
                Durchschnitt: {row['avg']:.2f} Punkte<br>
                Anzahl Bewertungen: {row['count']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    top_wine = ranking[0]
    st.metric("Top bewerteter Wein", f"Wein Nr. {top_wine['wine_no']}", f"Ø {top_wine['avg']:.2f}")

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
        st.success(f"Dein Trink-Buddy ist {buddy['name']} 🍷 Eure durchschnittliche Bewertungsdifferenz: {buddy['diff']:.2f}")
    else:
        for p in players:
            buddy = buddy_by_player.get(p["id"])
            if buddy:
                st.write(f"{p['name']} → {buddy['name']} · Ø Differenz {buddy['diff']:.2f}")

    with st.expander("Einzelbewertungen anzeigen"):
        for r in sorted(ratings, key=lambda x: (x["wine_no"], player_names.get(x["player_id"], ""))):
            st.write(f"Wein {r['wine_no']} · {player_names.get(r['player_id'], 'Unbekannt')} · {float(r['score']):.2f} · {r.get('comment') or ''}")


def player():
    st.title("Wine Challenge")
    name = st.session_state.name
    st.caption(f"Eingeloggt als {name}")

    games = get_games()
    if not games:
        st.info("Kein Spiel vorhanden")
        return

    game = st.selectbox("Spiel wählen", games, format_func=lambda x: f"{x['motto']} · {x['status']}")
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

    if game["status"] == "open":
        st.info("Du bist beigetreten. Der Admin muss die Challenge noch starten.")
        return

    if "saved_until" not in st.session_state:
        st.session_state.saved_until = {}

    st.subheader(f"Motto: {game['motto']}")
    st.write("Bewerte jeden Wein von 1 bis 6 in 0.25er-Schritten.")

    all_players = get_players(game_id)
    all_ratings = get_ratings(game_id)

    for w in range(1, game["wine_count"] + 1):
        existing_rating = get_rating(game_id, pid, w)
        default_score = float(existing_rating["score"]) if existing_rating else 4.0
        default_comment = existing_rating.get("comment") if existing_rating else ""
        default_comment = default_comment or ""

        with st.expander(f"Wein Nr. {w}", expanded=False):
            rated_player_ids = {r["player_id"] for r in all_ratings if r["wine_no"] == w}

            st.markdown("**Status Spieler**")
            for p in all_players:
                if p["id"] in rated_player_ids:
                    st.success(f"✅ {p['name']} hat bewertet")
                else:
                    st.warning(f"⏳ {p['name']} noch offen")

            st.divider()

            score = st.select_slider(
                "Note",
                options=rating_options(),
                value=default_score,
                key=f"score_{game_id}_{pid}_{w}",
            )
            comment = st.text_area(
                "Kommentar",
                value=default_comment,
                key=f"comment_{game_id}_{pid}_{w}",
            )

            changed = False
            if existing_rating:
                if float(score) != float(existing_rating["score"]) or comment != (existing_rating.get("comment") or ""):
                    changed = True
            else:
                if float(score) != 4.0 or comment.strip() != "":
                    changed = True

            message_key = f"{game_id}_{pid}_{w}"

            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("Speichern", key=f"save_{game_id}_{pid}_{w}"):
                    save_rating(game_id, pid, w, score, comment)
                    st.session_state.saved_until[message_key] = time.time() + 5
                    st.rerun()
            with col2:
                saved_until = st.session_state.saved_until.get(message_key, 0)
                if time.time() < saved_until:
                    st.success("Wert gespeichert ✅")
                elif changed:
                    st.warning("Achtung: Neuer Wert noch nicht gespeichert ⚠️")


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

