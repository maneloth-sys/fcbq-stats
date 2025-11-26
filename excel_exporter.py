from io import BytesIO

import pandas as pd

from stats_engine import get_match_dataframes


def build_excel_from_match_url(match_url: str) -> BytesIO:
    """
    Construye un Excel a partir de la misma información que usa la web.
    Devuelve un objeto BytesIO listo para descargar o guardar en disco.
    """
    data = get_match_dataframes(match_url)

    df_global = data["df_global_summary"]
    df_team = data["df_team_stats"]
    df_player = data["df_player_stats"]
    df_timeline = data["df_match_timeline"]
    df_minute = data["df_minute_by_minute"]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        # Hojas de datos principales
        df_global.to_excel(writer, sheet_name="Global Summary", index=False)
        df_team.to_excel(writer, sheet_name="Team Statistics", index=False)
        df_player.to_excel(writer, sheet_name="Player Statistics", index=False)
        df_timeline.to_excel(writer, sheet_name="Match Timeline", index=False)
        df_minute.to_excel(writer, sheet_name="Minute by Minute", index=False)

        workbook = writer.book

        # --- Ejemplo: gráfico sencillo de puntos por jugadora ---
        sheet_charts = workbook.add_worksheet("Charts")
        writer.sheets["Charts"] = sheet_charts

        # Volcamos datos mínimos para un gráfico de ejemplo
        tmp_df = df_player[["Player Name", "Total Points", "Team Name"]].copy()
        tmp_df.to_excel(writer, sheet_name="Charts", startrow=0, startcol=0, index=False)

        # Creamos gráfico de columnas
        chart = workbook.add_chart({"type": "column"})
        # Rango dinámico basado en el número de filas
        n_rows = len(tmp_df)
        chart.add_series(
            {
                "name": "Total Points",
                "categories": ["Charts", 1, 0, n_rows, 0],  # Player Name
                "values": ["Charts", 1, 1, n_rows, 1],      # Total Points
            }
        )
        chart.set_title({"name": "Puntos por jugadora"})
        chart.set_x_axis({"name": "Jugadora"})
        chart.set_y_axis({"name": "Puntos"})

        sheet_charts.insert_chart("G2", chart)

    output.seek(0)
    return output


def build_default_filename(df_global_summary: pd.DataFrame) -> str:
    """
    Genera un nombre de fichero coherente con la lógica anterior.
    """
    match_day = df_global_summary.loc[0, "matchDay"]
    local = df_global_summary.loc[0, "localTeamName"]
    visit = df_global_summary.loc[0, "visitTeamName"]
    return f"match_statistics_summary_{match_day}_{local}_vs_{visit}.xlsx"
