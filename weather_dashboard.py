"""Interactive Weather Dashboard - a Streamlit app.

Run with:
    pip install -r requirements.txt
    streamlit run weather_dashboard.py
"""

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10            # seconds
TEN_MINUTES = 600
KOREA_CENTER = (36.5, 127.5)
DEFAULT_ZOOM = 6


class ServiceUnavailable(Exception):
    """Raised when the Open-Meteo service cannot be reached or misbehaves."""


@st.cache_data(ttl=TEN_MINUTES, show_spinner=False)
def load_hourly_temperature(lat: float, lng: float) -> pd.DataFrame:
    """Return a DataFrame of hourly temperatures (°C) indexed by time."""
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lng,
                "hourly": "temperature_2m",
                "forecast_days": 2,
                "timezone": "auto",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        hourly = response.json()["hourly"]
        df = pd.DataFrame(
            {
                "time": pd.to_datetime(hourly["time"]),
                "Temperature (°C)": hourly["temperature_2m"],
            }
        ).set_index("time")
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise ServiceUnavailable(str(exc)) from exc

    if df.empty:
        raise ServiceUnavailable("No hourly data returned.")
    return df


def main() -> None:
    st.set_page_config(page_title="Interactive Weather Dashboard", page_icon="🌡️", layout="wide")
    st.title("🌡️ Interactive Weather Dashboard")
    st.write("Click anywhere on the map to see the hourly temperature forecast for that spot.")

    # Map centered on Korea
    fmap = folium.Map(location=KOREA_CENTER, zoom_start=DEFAULT_ZOOM)
    map_state = st_folium(fmap, height=450, use_container_width=True, returned_objects=["last_clicked"])

    clicked = (map_state or {}).get("last_clicked")
    if not clicked:
        st.info("👆 Click a location on the map to load its weather forecast.")
        st.stop()

    lat = round(clicked["lat"], 3)
    lng = round(clicked["lng"], 3)
    st.subheader(f"Forecast for {lat}, {lng}")

    try:
        with st.spinner("Loading forecast..."):
            df = load_hourly_temperature(lat, lng)
    except ServiceUnavailable:
        st.error(
            "Sorry, we couldn't reach the weather service right now. "
            "Please try again in a moment or click a different spot."
        )
        st.stop()

    temps = df["Temperature (°C)"]
    col1, col2, col3 = st.columns(3)
    col1.metric("First hour", f"{temps.iloc[0]:.1f} °C", help=str(df.index[0]))
    col2.metric("Highest", f"{temps.max():.1f} °C", help=str(temps.idxmax()))
    col3.metric("Lowest", f"{temps.min():.1f} °C", help=str(temps.idxmin()))

    st.line_chart(df)
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.caption(
        "Weather data by [Open-Meteo.com](https://open-meteo.com/) "
        "(licensed under CC BY 4.0)."
    )


if __name__ == "__main__":
    main()
