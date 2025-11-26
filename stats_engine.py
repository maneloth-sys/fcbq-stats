import asyncio
from datetime import datetime

import pandas as pd
from playwright.async_api import async_playwright


# ---------- CAPTURA DE DATOS DESDE LA WEB ----------

async def _capture_api_responses(match_url: str):
    """
    Lanza Playwright, abre la URL del partido y captura todas las respuestas JSON.
    Devuelve una lista con {url, json_data}.
    """
    captured_api_responses = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        async def handle_response(response):
            try:
                content_type = response.headers.get("content-type", "").lower()
            except Exception:
                content_type = ""
            if "json" not in content_type:
                return

            try:
                json_data = await response.json()
            except Exception:
                return

            captured_api_responses.append(
                {
                    "url": response.url,
                    "json_data": json_data,
                }
            )

        page.on("response", handle_response)
        await page.goto(match_url)
        await page.wait_for_timeout(8000)
        await browser.close()

    return captured_api_responses


def _extract_full_match_stats_and_moves(captured_api_responses):
    """
    Localiza en las respuestas:
    - getJsonWithMatchStats (estadísticas globales)
    - getJsonWithMatchMoves (jugada a jugada)
    """
    full_match_stats = None
    full_match_moves = None

    for resp in captured_api_responses:
        url = resp["url"]
        if "getJsonWithMatchStats" in url:
            full_match_stats = resp["json_data"]
        elif "getJsonWithMatchMoves" in url:
            full_match_moves = resp["json_data"]

    if full_match_stats is None:
        raise RuntimeError("No se encontró 'getJsonWithMatchStats' en las respuestas.")
    if full_match_moves is None:
        raise RuntimeError("No se encontró 'getJsonWithMatchMoves' en las respuestas.")

    return full_match_stats, full_match_moves


# ---------- CONSTRUCCIÓN DE DATAFRAMES ----------

def _build_dataframes(full_match_stats, full_match_moves):
    """
    Construye todos los DataFrames a partir de los JSON completos.
    Devuelve un dict con todos los DF + metadatos útiles.
    """
    # --- Resumen global ---
    match_datetime_str = full_match_stats.get("time")
    match_datetime = datetime.strptime(match_datetime_str, "%b %d, %Y %I:%M:%S %p")

    period_duration_list = full_match_stats.get("periodDurationList", [])
    calculated_total_duration = sum(period_duration_list) if period_duration_list else None

    teams_data = full_match_stats.get("teams", [])
    team_local = teams_data[0] if len(teams_data) >= 1 else {}
    team_visit = teams_data[1] if len(teams_data) >= 2 else {}

    global_match_summary = {
        "idMatchIntern": full_match_stats.get("idMatchIntern"),
        "matchDay": match_datetime.strftime("%Y-%m-%d"),
        "matchTime": match_datetime.strftime("%H:%M:%S"),
        "totalDurationMinutes": calculated_total_duration,
        "periodDurationMinutes": full_match_stats.get("periodDuration"),
        "periodTotal": full_match_stats.get("period"),
        "localTeamName": team_local.get("name"),
        "visitTeamName": team_visit.get("name"),
        "finalScoreLocal": team_local.get("data", {}).get("score"),
        "finalScoreVisit": team_visit.get("data", {}).get("score"),
    }
    df_global_summary = pd.DataFrame([global_match_summary])

    # --- Estadísticas por jugadora ---
    player_stats_list = []
    for team in teams_data:
        team_name = team.get("name")
        team_id = team.get("teamIdIntern")

        for player in team.get("players", []):
            player_data = player.get("data", {})
            player_periods = player.get("periods", [])

            total_fouls = sum(p.get("faults", 0) for p in player_periods)

            player_stats_list.append(
                {
                    "Team ID": team_id,
                    "Team Name": team_name,
                    "Player ID": player.get("actorId"),
                    "Player Name": player.get("name"),
                    "Dorsal": player.get("dorsal"),
                    "Total Points": player_data.get("score"),
                    "Minutes Played": player.get("timePlayed"),
                    "Total Fouls": total_fouls,
                    "Shots 1 Attempted": player_data.get("shotsOfOneAttempted"),
                    "Shots 1 Successful": player_data.get("shotsOfOneSuccessful"),
                    "Shots 2 Attempted": player_data.get("shotsOfTwoAttempted"),
                    "Shots 2 Successful": player_data.get("shotsOfTwoSuccessful"),
                    "Shots 3 Attempted": player_data.get("shotsOfThreeAttempted"),
                    "Shots 3 Successful": player_data.get("shotsOfThreeSuccessful"),
                    "Assists": player_data.get("assists"),
                    "Rebounds": player_data.get("rebounds"),
                    "Steals": player_data.get("steals"),
                    "Blocks": player_data.get("block"),
                    "Turnovers": player_data.get("lost"),
                }
            )

    df_player_stats = pd.DataFrame(player_stats_list)

    # % tiros libres
    df_player_stats["% shots 1"] = df_player_stats.apply(
        lambda row: 0
        if not row["Shots 1 Attempted"]
        else row["Shots 1 Successful"] / row["Shots 1 Attempted"],
        axis=1,
    )

    # Métrica Val personalizada
    def calc_val(row):
        pts = row["Total Points"]
        fouls = row["Total Fouls"]
        mins = row["Minutes Played"]
        att = row["Shots 1 Attempted"]
        succ = row["Shots 1 Successful"]
        bonus = 0 if att == 0 else (succ / att) * 2
        return pts - fouls + (mins / 5) + bonus

    df_player_stats["Val"] = df_player_stats.apply(calc_val, axis=1).round(0)

    # --- Estadísticas por equipo (global + periodos) ---
    team_stats_list = []
    for team in teams_data:
        team_id = team.get("teamIdIntern")
        team_name = team.get("name")
        overall_data = team.get("data", {})

        # Global
        overall_stats = {
            "Team ID": team_id,
            "Team Name": team_name,
            "Stat Type": "Overall",
            "Period": "N/A",
            "Score": overall_data.get("score"),
            "Valoration": overall_data.get("valoration"),
            "Shots 1 Attempted": overall_data.get("shotsOfOneAttempted"),
            "Shots 1 Successful": overall_data.get("shotsOfOneSuccessful"),
            "Shots 2 Attempted": overall_data.get("shotsOfTwoAttempted"),
            "Shots 2 Successful": overall_data.get("shotsOfTwoSuccessful"),
            "Shots 3 Attempted": overall_data.get("shotsOfThreeAttempted"),
            "Shots 3 Successful": overall_data.get("shotsOfThreeSuccessful"),
            "Rebounds": overall_data.get("rebounds"),
            "Assists": overall_data.get("assists"),
            "Steals": overall_data.get("steals"),
            "Blocks": overall_data.get("block"),
            "Lost": overall_data.get("lost"),
            "Faults": overall_data.get("faults"),
        }
        att1 = overall_data.get("shotsOfOneAttempted", 0)
        succ1 = overall_data.get("shotsOfOneSuccessful", 0)
        overall_stats["% shots 1"] = (succ1 / att1) if att1 > 0 else 0
        team_stats_list.append(overall_stats)

        # Por periodo
        periods = team.get("periods", [])
        for idx, period in enumerate(periods):
            period_num = idx + 1
            period_data = period
            period_stats = {
                "Team ID": team_id,
                "Team Name": team_name,
                "Stat Type": "Period",
                "Period": period_num,
                "Score": period_data.get("score"),
                "Valoration": period_data.get("valoration"),
                "Shots 1 Attempted": period_data.get("shotsOfOneAttempted"),
                "Shots 1 Successful": period_data.get("shotsOfOneSuccessful"),
                "Shots 2 Attempted": period_data.get("shotsOfTwoAttempted"),
                "Shots 2 Successful": period_data.get("shotsOfTwoSuccessful"),
                "Shots 3 Attempted": period_data.get("shotsOfThreeAttempted"),
                "Shots 3 Successful": period_data.get("shotsOfThreeSuccessful"),
                "Rebounds": period_data.get("rebounds"),
                "Assists": period_data.get("assists"),
                "Steals": period_data.get("steals"),
                "Blocks": period_data.get("block"),
                "Lost": period_data.get("lost"),
                "Faults": period_data.get("faults"),
            }
            att1_p = period_data.get("shotsOfOneAttempted", 0)
            succ1_p = period_data.get("shotsOfOneSuccessful", 0)
            period_stats["% shots 1"] = (succ1_p / att1_p) if att1_p > 0 else 0
            team_stats_list.append(period_stats)

    df_team_stats = pd.DataFrame(team_stats_list)

    # --- Timeline jugada a jugada ---
    match_timeline_list = []
    for move in full_match_moves:
        team_name = next(
            (t["name"] for t in full_match_stats["teams"] if t["teamIdIntern"] == move.get("idTeam")),
            "Unknown Team",
        )
        score_combined = move.get("score")
        if score_combined and isinstance(score_combined, str) and "-" in score_combined:
            score_local, score_visit = [s.strip() for s in score_combined.split("-")]
        else:
            score_local, score_visit = "0", "0"

        match_timeline_list.append(
            {
                "Team Name": team_name,
                "Player Name": move.get("actorName", "N/A"),
                "Action": move.get("move", "N/A"),
                "Minute": move.get("min", 0),
                "Period": move.get("period", "N/A"),
                "Score Local": int(score_local),
                "Score Visit": int(score_visit),
            }
        )

    df_match_timeline = pd.DataFrame(match_timeline_list)
    df_match_timeline["Minute"] = (
        pd.to_numeric(df_match_timeline["Minute"], errors="coerce").fillna(0).astype(int)
    )

    # --- Evolución minuto a minuto ---
    if not df_match_timeline.empty:
        df_minute_by_minute = (
            df_match_timeline.groupby("Minute")[["Score Local", "Score Visit"]].max().reset_index()
        )
        max_minute = df_minute_by_minute["Minute"].max()
        all_minutes = pd.RangeIndex(start=0, stop=max_minute + 1, name="Minute")
        df_minute_by_minute = (
            df_minute_by_minute.set_index("Minute")
            .reindex(all_minutes)
            .ffill()
            .fillna(0)
            .reset_index()
        )
    else:
        df_minute_by_minute = pd.DataFrame(columns=["Minute", "Score Local", "Score Visit"])

    return {
        "df_global_summary": df_global_summary,
        "df_team_stats": df_team_stats,
        "df_player_stats": df_player_stats,
        "df_match_timeline": df_match_timeline,
        "df_minute_by_minute": df_minute_by_minute,
        "full_match_stats": full_match_stats,
    }


# ---------- FUNCIÓN PÚBLICA ----------

def get_match_dataframes(match_url: str):
    """
    Punto de entrada: dada la URL del partido, devuelve
    todos los DataFrames y el JSON de stats completo.
    """
    responses = asyncio.run(_capture_api_responses(match_url))
    full_match_stats, full_match_moves = _extract_full_match_stats_and_moves(responses)
    return _build_dataframes(full_match_stats, full_match_moves)
