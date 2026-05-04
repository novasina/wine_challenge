import streamlit as st
import sqlite3
import time
from datetime import datetime
from itertools import combinations

DB_PATH = "wine_challenge.db"
ADMIN_PASSWORD = "admin123"

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


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            motto TEXT NOT NULL,
            max_players INTEGER NOT NULL,
            wine_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(game_id, name)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            wine_no INTEGER NOT NULL,
            score REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(game_id, player_id, wine_no)
        )
    """)

    conn.commit()
    conn.close()


def query_all(sql, params=()):
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def create_game(motto, max_players, wine_count):
    execute(
        "INSERT INTO games (motto, max_players, wine_count, status, created_at) VALUES (?, ?, ?, 'open', ?)",
        (motto.strip(), max_players, wine_count, datetime.now().isoformat()),
    )


def get_games():
    return query_all("SELECT * FROM games ORDER BY id DESC")


def join_game(game_id, name):
    existing = query_one("SELECT * FROM players WHERE game_id=? AND lower(name)=lower(?)", (game_id, name.strip()))
    if existing:
        return existing["id"]

    game = query_one("SELECT * FROM games WHERE id=?", (game_id,))
    player_count = query_one("SELECT COUNT(*) AS n FROM players WHERE game_id=?", (game_id,))["n"]

    if game["status"] == "finished":
        st.warning("Diese Challenge ist bereits beendet. Du kannst nur noch die Rangliste ansehen.")
        return None

    if player_count >= game["max_players"]:
        st.error("Dieses Spiel ist bereits voll.")
        return None

    return execute(
        "INSERT INTO players (game_id, name, created_at) VALUES (?, ?, ?)",
        (game_id, name.strip(), datetime.now().isoformat()),
    )


def save_rating(game_id, player_id, wine_no, score, comment):
    execute(
        """
        INSERT INTO ratings (game_id, player_id, wine_no, score, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(game_id, player_id, wine_no)
        DO UPDATE SET score=excluded.score, comment=excluded.comment, created_at=excluded.created_at
        """,
        (game_id, player_id, wine_no, score, comment, datetime.now().isoformat()),
    )


def rating_options():
    values = []
    x = 1.0
    while x <= 6.0001:
        values.append(round(x, 2))
        x += 0.25
    return values


def calculate_stats(game_id):
    game = query_one("SELECT * FROM games WHERE id=?", (game_id,))
    players = query_all("SELECT * FROM players WHERE game_id=? ORDER BY name", (game_id,))
    ratings = query_all(
        """
        SELECT r.*, p.name AS player_name
        FROM ratings r
        JOIN players p ON p.id = r.player_id
        WHERE r.game_id=?
        """,
        (game_id,),
    )

    ranking = []
    for wine_no in range(1, game["wine_count"] + 1):
        wine_scores = [r["score"] for r in ratings if r["wine_no"] == wine_no]
        if wine_scores:
            ranking.append({
                "wine_no": wine_no,
                "avg": sum(wine_scores) / len(wine_scores),
                "count": len(wine_scores),
            })

    ranking.sort(key=lambda x: x["avg"], reverse=True)

    highest = max(ratings, key=lambda r: r["score"], default=None)
    lowest = min(ratings, key=lambda r: r["score"], default=None)

    rating_map = {}
    for p in players:
        rating_map[p["id"]] = {
            r["wine_no"]: r["score"]
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

    return game, players, ratings, ranking, highest, lowest, buddy_by_player


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
            create_game(motto, int(players), int(wines))
            st.success("Spiel erstellt ✅")
            st.rerun()

    st.divider()
    st.markdown("### Spiele verwalten")

    for game in get_games():
        player_count = query_one("SELECT COUNT(*) AS n FROM players WHERE game_id=?", (game["id"],))["n"]
        rating_count = query_one("SELECT COUNT(*) AS n FROM ratings WHERE game_id=?", (game["id"],))["n"]

        with st.expander(f"#{game['id']} · {game['motto']} · Status: {game['status']}"):
            st.write(f"Spieler: {player_count}/{game['max_players']}")
            st.write(f"Bewertungen: {rating_count}")

            col1, col2, col3 = st.columns(3)
            if col1.button("Öffnen", key=f"open_{game['id']}"):
                execute("UPDATE games SET status='open' WHERE id=?", (game["id"],))
                st.rerun()
            if col2.button("Starten", key=f"run_{game['id']}"):
                execute("UPDATE games SET status='running' WHERE id=?", (game["id"],))
                st.rerun()
            if col3.button("Schliessen", key=f"close_{game['id']}"):
                execute("UPDATE games SET status='finished' WHERE id=?", (game["id"],))
                st.rerun()


def dashboard(game_id, player_id=None):
    game, players, ratings, ranking, highest, lowest, buddy_by_player = calculate_stats(game_id)

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
            f"{highest['score']:.2f}",
            f"Wein {highest['wine_no']} · {highest['player_name']}",
        )
    if lowest:
        col2.metric(
            "Tiefste Einzelbewertung",
            f"{lowest['score']:.2f}",
            f"Wein {lowest['wine_no']} · {lowest['player_name']}",
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
        for r in sorted(ratings, key=lambda x: (x["wine_no"], x["player_name"])):
            st.write(f"Wein {r['wine_no']} · {r['player_name']} · {r['score']:.2f} · {r['comment'] or ''}")


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

    existing_player = query_one("SELECT * FROM players WHERE game_id=? AND lower(name)=lower(?)", (game_id, name))
    if existing_player:
        pid = existing_player["id"]
    else:
        pid = join_game(game_id, name)

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

    for w in range(1, game["wine_count"] + 1):
        existing_rating = query_one(
            "SELECT * FROM ratings WHERE game_id=? AND player_id=? AND wine_no=?",
            (game_id, pid, w),
        )
        default_score = existing_rating["score"] if existing_rating else 4.0
        default_comment = existing_rating["comment"] if existing_rating else ""

        with st.expander(f"Wein Nr. {w}", expanded=False):
            all_players = query_all("SELECT * FROM players WHERE game_id=? ORDER BY name", (game_id,))
            wine_ratings = query_all("SELECT player_id FROM ratings WHERE game_id=? AND wine_no=?", (game_id, w))
            rated_player_ids = {r["player_id"] for r in wine_ratings}

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
                value=float(default_score),
                key=f"score_{game_id}_{pid}_{w}",
            )
            comment = st.text_area(
                "Kommentar",
                value=default_comment,
                key=f"comment_{game_id}_{pid}_{w}",
            )

            changed = False
            if existing_rating:
                if float(score) != float(existing_rating["score"]) or comment != (existing_rating["comment"] or ""):
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
    init_db()

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
