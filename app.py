import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ---------- Configuration ----------
st.set_page_config(page_title="UAC System Capacity Dashboard", layout="wide")
st.title("🏥 Unaccompanied Children Program – Capacity & Care Load Analytics")
st.markdown("**Data source:** HHS UAC Daily Report (Dec 2023 – Dec 2025)")

@st.cache_data
def load_data():
    df = pd.read_csv("HHS_Unaccompanied_Alien_Children_Program.csv")
    # Drop completely empty rows
    df = df.dropna(how='all')
    # Convert Date
    df['Date'] = pd.to_datetime(df['Date'], format='%B %d, %Y', errors='coerce')
    df = df.dropna(subset=['Date'])
    df = df.sort_values('Date')
    # Rename columns for easier access
    df.columns = ['Date', 'apprehended', 'cbp_custody', 'transferred_out', 'hhs_care', 'discharged']
    # Convert numeric columns (remove commas)
    for col in ['apprehended', 'cbp_custody', 'transferred_out', 'hhs_care', 'discharged']:
        df[col] = df[col].astype(str).str.replace(',', '').astype(float).astype(int)
    # Derived metrics
    df['total_load'] = df['cbp_custody'] + df['hhs_care']
    df['net_intake'] = df['transferred_out'] - df['discharged']
    df['load_growth_pct'] = df['total_load'].pct_change() * 100
    df['discharge_offset_ratio'] = df['discharged'] / df['transferred_out'].replace(0, np.nan)
    df['backlog_flag'] = (df['net_intake'].rolling(7, min_periods=1).mean() > 0).astype(int)
    # Rolling averages
    df['net_intake_7d'] = df['net_intake'].rolling(7, min_periods=1).mean()
    df['total_load_7d'] = df['total_load'].rolling(7, min_periods=1).mean()
    return df

df = load_data()

# ---------- Sidebar Filters ----------
st.sidebar.header("🔍 Filter Controls")
date_range = st.sidebar.date_input(
    "Date Range",
    value=(df['Date'].min(), df['Date'].max()),
    min_value=df['Date'].min(),
    max_value=df['Date'].max()
)
if len(date_range) == 2:
    start, end = date_range
    mask = (df['Date'] >= pd.to_datetime(start)) & (df['Date'] <= pd.to_datetime(end))
    df_filtered = df.loc[mask].copy()
else:
    df_filtered = df.copy()

time_granularity = st.sidebar.selectbox("Time Granularity", ["Daily", "Weekly", "Monthly"])
if time_granularity == "Weekly":
    df_filtered = df_filtered.set_index('Date').resample('W-MON').mean(numeric_only=True).reset_index()
elif time_granularity == "Monthly":
    df_filtered = df_filtered.set_index('Date').resample('ME').mean(numeric_only=True).reset_index()

metrics_to_show = st.sidebar.multiselect(
    "Display Metrics",
    ["Total Load", "Net Intake", "CBP vs HHS", "Load Growth %", "Discharge Offset Ratio"],
    default=["Total Load", "Net Intake", "CBP vs HHS"]
)

# ---------- KPI Cards ----------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📊 Current Total Load", f"{df_filtered['total_load'].iloc[-1]:,.0f}" if len(df_filtered)>0 else "N/A",
              delta=f"{df_filtered['total_load'].iloc[-1] - df_filtered['total_load'].iloc[-2]:,.0f}" if len(df_filtered)>1 else None)
with col2:
    st.metric("⚖️ Avg Net Intake (7d)", f"{df_filtered['net_intake_7d'].iloc[-1]:+.0f}" if len(df_filtered)>0 else "N/A")
with col3:
    st.metric("🔄 Discharge Offset Ratio", f"{df_filtered['discharge_offset_ratio'].iloc[-1]:.2f}" if len(df_filtered)>0 else "N/A")
with col4:
    st.metric("📈 Peak Total Load (period)", f"{df_filtered['total_load'].max():,.0f}")

st.divider()

# ---------- Main Charts ----------
if "Total Load" in metrics_to_show:
    fig1 = px.area(df_filtered, x='Date', y='total_load', title="📦 Total System Load (CBP + HHS Custody)",
                   labels={'total_load': 'Number of Children', 'Date': ''}, color_discrete_sequence=['#2c3e66'])
    fig1.add_scatter(x=df_filtered['Date'], y=df_filtered['total_load_7d'], mode='lines', name='7‑day avg', line=dict(dash='dot', color='orange'))
    st.plotly_chart(fig1, use_container_width=True)

if "Net Intake" in metrics_to_show:
    fig2 = go.Figure()
    fig2.add_bar(x=df_filtered['Date'], y=df_filtered['net_intake'], name='Daily Net Intake', marker_color='steelblue')
    fig2.add_scatter(x=df_filtered['Date'], y=df_filtered['net_intake_7d'], mode='lines', name='7‑day avg', line=dict(color='red', width=2))
    fig2.add_hline(y=0, line_dash="dash", line_color="grey")
    fig2.update_layout(title="🌊 Net Intake Pressure (Transfers − Discharges)", xaxis_title="", yaxis_title="Children")
    st.plotly_chart(fig2, use_container_width=True)

if "CBP vs HHS" in metrics_to_show:
    fig3 = px.line(df_filtered, x='Date', y=['cbp_custody', 'hhs_care'], 
                   title="🏢 CBP Custody vs HHS Care Load", labels={'value': 'Children', 'Date': '', 'variable': 'Custody Type'})
    st.plotly_chart(fig3, use_container_width=True)

if "Load Growth %" in metrics_to_show:
    fig4 = px.bar(df_filtered, x='Date', y='load_growth_pct', title="📈 Day‑over‑Day Load Growth (%)",
                  labels={'load_growth_pct': '% Change', 'Date': ''}, color_discrete_sequence=['teal'])
    st.plotly_chart(fig4, use_container_width=True)

if "Discharge Offset Ratio" in metrics_to_show:
    fig5 = px.line(df_filtered, x='Date', y='discharge_offset_ratio', 
                   title="🔄 Discharge Offset Ratio (Discharges / Transfers)", 
                   labels={'discharge_offset_ratio': 'Ratio', 'Date': ''})
    fig5.add_hline(y=1, line_dash="dash", line_color="green", annotation_text="Balanced")
    fig5.add_hline(y=0.8, line_dash="dot", line_color="orange", annotation_text="Warning (0.8)")
    st.plotly_chart(fig5, use_container_width=True)

# ---------- Strain Identification ----------
st.subheader("⚠️ Capacity Strain Windows")
strain_df = df_filtered.copy()
strain_df['high_strain'] = (strain_df['net_intake_7d'] > 50) & (strain_df['total_load_7d'] > 8000)
strain_periods = strain_df[strain_df['high_strain']]
if not strain_periods.empty:
    st.warning(f"Detected {len(strain_periods)} days with high strain (net intake >50 & load >8,000). Most recent: {strain_periods['Date'].iloc[-1].date()}")
    st.dataframe(strain_periods[['Date', 'total_load', 'net_intake', 'discharge_offset_ratio']].tail(10))
else:
    st.success("No high‑strain windows in the selected period.")

# ---------- Data Download ----------
st.download_button("📥 Download Filtered Data (CSV)", df_filtered.to_csv(index=False), "uac_filtered.csv", "text/csv")

st.caption("Dashboard shows derived KPIs: Net Intake = Transfers − Discharges. Discharge Offset Ratio = Discharges/Transfers. Load growth % is day‑over‑day.")
