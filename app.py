import streamlit as st
import plotly.express as px
import pandas as pd

from stats_engine import get_match_dataframes
from excel_exporter import build_excel_from_match_url, build_default_filename


st.set_page_config(
    page_title="Estadísticas FCBQ",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def _cached_match_data(match_url: str):
    return get_match_dataframes(match_url)


def main():
    st.title("📊 Dashboard de Estadísticas de Partidos FCBQ")

    # --------- SIDEBAR ---------
    with st.sidebar:
        st.header("⚙️ Configuración")

        default_url = "https://www.basquetcatala.cat/estadistiques/2025/6921b55d71982d0001d99025"
        match_url = st.text_input("URL del partido", value=default_url)

        analyze = st.button("Analizar partido", type="primary")

        st.markdown("---")
        st.caption("La misma información se utiliza para el Excel y para este dashboard.")

    if not analyze:
        st.info("Introduce la URL del partido y pulsa **Analizar partido**.")
        return

    # --------- CARGA Y CÁLCULO ---------
    with st.spinner("Descargando datos y calculando estadísticas..."):
        data = _cached_match_data(match_url)

    df_global = data["df_global_summary"]
    df_team = data["df_team_stats"]
    df_player = data["df_player_stats"]
    df_timeline = data["df_match_timeline"]
    df_minute = data["df_minute_by_minute"]

    local_name = df_global.loc[0, "localTeamName"]
    visit_name = df_global.loc[0, "visitTeamName"]

    # --------- BOTÓN DE DESCARGA DE EXCEL ---------
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 Exportar a Excel")
    excel_bytes = build_excel_from_match_url(match_url)
    filename = build_default_filename(df_global)
    st.sidebar.download_button(
        label="Descargar Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # --------- MÉTRICAS PRINCIPALES ---------
    st.subheader("📌 Resumen del partido")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Fecha", df_global.loc[0, "matchDay"])
    col2.metric("Hora", df_global.loc[0, "matchTime"])
    col3.metric("Local", f"{local_name} ({df_global.loc[0, 'finalScoreLocal']})")
    col4.metric("Visitante", f"{visit_name} ({df_global.loc[0, 'finalScoreVisit']})")
    col5.metric("Duración total (min)", df_global.loc[0, "totalDurationMinutes"])

    # --------- TABS PRINCIPALES ---------
    tab_overview, tab_teams, tab_players, tab_timeline, tab_data = st.tabs(
        ["Resumen", "Equipos", "Jugadoras", "Timeline", "Datos en bruto"]
    )

    # ============ TAB RESUMEN ============
    with tab_overview:
        st.markdown("### 🔍 Vista rápida")

        # KPIs por equipo
        df_team_overall = df_team[df_team["Stat Type"] == "Overall"].copy()

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f"#### {local_name}")
            local_row = df_team_overall[df_team_overall["Team Name"] == local_name]
            if not local_row.empty:
                row = local_row.iloc[0]
                c1, c2, c3 = st.columns(3)
                c1.metric("Puntos", int(row["Score"]))
                c2.metric("Valoración", int(row["Valoration"] or 0))
                c3.metric("Rebotes", int(row["Rebounds"] or 0))

                c4, c5, c6 = st.columns(3)
                c4.metric("Asistencias", int(row["Assists"] or 0))
                c5.metric("Robos", int(row["Steals"] or 0))
                c6.metric("Pérdidas", int(row["Lost"] or 0))

        with col_b:
            st.markdown(f"#### {visit_name}")
            visit_row = df_team_overall[df_team_overall["Team Name"] == visit_name]
            if not visit_row.empty:
                row = visit_row.iloc[0]
                c1, c2, c3 = st.columns(3)
                c1.metric("Puntos", int(row["Score"]))
                c2.metric("Valoración", int(row["Valoration"] or 0))
                c3.metric("Rebotes", int(row["Rebounds"] or 0))

                c4, c5, c6 = st.columns(3)
                c4.metric("Asistencias", int(row["Assists"] or 0))
                c5.metric("Robos", int(row["Steals"] or 0))
                c6.metric("Pérdidas", int(row["Lost"] or 0))

        st.markdown("### 📈 Evolución del marcador minuto a minuto")
        if not df_minute.empty:
            fig_minute = px.line(
                df_minute,
                x="Minute",
                y=["Score Local", "Score Visit"],
                labels={"Minute": "Minuto"},
            )
            st.plotly_chart(fig_minute, use_container_width=True)
        else:
            st.warning("No se ha podido construir la evolución minuto a minuto.")

    # ============ TAB EQUIPOS ============
    with tab_teams:
        st.markdown("### 🏀 Estadísticas de equipo por periodo")

        team_selected = st.selectbox(
            "Selecciona equipo",
            options=df_team["Team Name"].unique().tolist(),
            index=0,
        )

        df_team_periods = df_team[
            (df_team["Team Name"] == team_selected) & (df_team["Stat Type"] == "Period")
        ].copy()

        col_left, col_right = st.columns([2, 1])
        with col_left:
            if not df_team_periods.empty:
                fig_period = px.bar(
                    df_team_periods,
                    x="Period",
                    y="Score",
                    text_auto=True,
                    labels={"Period": "Periodo", "Score": "Puntos"},
                    title=f"Puntos por periodo – {team_selected}",
                )
                st.plotly_chart(fig_period, use_container_width=True)
            else:
                st.info("No hay datos de periodos para este equipo.")

        with col_right:
            st.markdown("#### Tabla de periodos")
            st.dataframe(
                df_team_periods[
                    [
                        "Period",
                        "Score",
                        "Rebounds",
                        "Assists",
                        "Steals",
                        "Blocks",
                        "Lost",
                        "Faults",
                    ]
                ].set_index("Period")
            )

        st.markdown("### 🔬 Distribución de tiros")
        df_team_overall = df_team[df_team["Stat Type"] == "Overall"].copy()
        df_overall_team = df_team_overall[
            df_team_overall["Team Name"] == team_selected
        ].copy()
        if not df_overall_team.empty:
            row = df_overall_team.iloc[0]
            df_shots = (
                pd.DataFrame(
                    {
                        "Tipo": ["T1", "T2", "T3"],
                        "Intentos": [
                            row["Shots 1 Attempted"],
                            row["Shots 2 Attempted"],
                            row["Shots 3 Attempted"],
                        ],
                        "Encestados": [
                            row["Shots 1 Successful"],
                            row["Shots 2 Successful"],
                            row["Shots 3 Successful"],
                        ],
                    }
                )
                .fillna(0)
            )

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                fig_att = px.bar(
                    df_shots,
                    x="Tipo",
                    y="Intentos",
                    text_auto=True,
                    title="Intentos por tipo de tiro",
                )
                st.plotly_chart(fig_att, use_container_width=True)
            with col_s2:
                fig_succ = px.bar(
                    df_shots,
                    x="Tipo",
                    y="Encestados",
                    text_auto=True,
                    title="Encestados por tipo de tiro",
                )
                st.plotly_chart(fig_succ, use_container_width=True)

    # ============ TAB JUGADORAS ============
    with tab_players:
        st.markdown("### 👥 Estadísticas por jugadora")

        col_filters, col_table = st.columns([1, 3])

        with col_filters:
            team_filter = st.selectbox(
                "Filtrar por equipo",
                options=["Todos"] + df_player["Team Name"].unique().tolist(),
                index=0,
            )
            order_metric = st.selectbox(
                "Ordenar por",
                options=["Total Points", "Val", "Minutes Played"],
                index=0,
            )
            top_n = st.slider("Número de jugadoras a mostrar", 5, 20, 10)

        df_players_filtered = df_player.copy()
        if team_filter != "Todos":
            df_players_filtered = df_players_filtered[
                df_players_filtered["Team Name"] == team_filter
            ]

        df_players_filtered = df_players_filtered.sort_values(
            by=order_metric, ascending=False
        ).head(top_n)

        with col_table:
            st.dataframe(
                df_players_filtered[
                    [
                        "Team Name",
                        "Player Name",
                        "Dorsal",
                        "Total Points",
                        "Val",
                        "Minutes Played",
                        "Total Fouls",
                        "Assists",
                        "Rebounds",
                        "Steals",
                        "Blocks",
                        "Turnovers",
                    ]
                ]
            )

        st.markdown("### 📊 Gráfico de jugadoras")
        fig_players = px.bar(
            df_players_filtered,
            x="Player Name",
            y=order_metric,
            color="Team Name",
            text_auto=True,
            title=f"Top {top_n} jugadoras por {order_metric}",
        )
        st.plotly_chart(fig_players, use_container_width=True)

    # ============ TAB TIMELINE ============
    with tab_timeline:
        st.markdown("### 🕒 Timeline de acciones")

        st.dataframe(
            df_timeline.sort_values(["Period", "Minute", "Team Name", "Player Name"]),
            use_container_width=True,
        )

        st.markdown("### 📈 Evolución del marcador por minuto")
        if not df_minute.empty:
            fig_minute2 = px.line(
                df_minute,
                x="Minute",
                y=["Score Local", "Score Visit"],
                labels={"Minute": "Minuto"},
            )
            st.plotly_chart(fig_minute2, use_container_width=True)
        else:
            st.info("No hay datos suficientes para mostrar la evolución minuto a minuto.")

    # ============ TAB DATOS EN BRUTO ============
    with tab_data:
        st.markdown("### 📄 Global Summary")
        st.dataframe(df_global)

        st.markdown("### 📄 Team Statistics")
        st.dataframe(df_team)

        st.markdown("### 📄 Player Statistics")
        st.dataframe(df_player)

        st.markdown("### 📄 Match Timeline")
        st.dataframe(df_timeline)

        st.markdown("### 📄 Minute by Minute")
        st.dataframe(df_minute)


if __name__ == "__main__":
    main()
