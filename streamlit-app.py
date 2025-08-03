# -*- coding: utf-8 -*-
"""
Author: Dennie

"""
import io, hashlib
import streamlit as st
import pandas as pd
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.ioff()
#from openai import OpenAI as OpenAIClient 
from pandasai import SmartDataframe as sdf
from pandasai.llm.openai import OpenAI
import html


enable_key = st.sidebar.text_input("OpenAI API Key", type="password")
your_model = st.sidebar.text_input("LLM", type="password")
if not enable_key or not your_model:
    st.warning("Enter your OpenAI API key and Model name")
    st.stop()



# Define functions
def build_chart_from_spec(spec, df):
    chart_type = spec.get("chart_type", "").lower()
    fig, ax = plt.subplots()
    if chart_type == "scatter":
        x = spec["x"]
        y = spec["y"]
        color = spec.get("color")
        if color and color in df.columns:
            for name, group in df.groupby(color):
                ax.scatter(group[x], group[y], label=name)
            ax.legend(title=color)
        else:
            ax.scatter(df[x], df[y])
        ax.set_xlabel(x)
        ax.set_ylabel(y)
    elif chart_type == "bar":
        x = spec["x"]
        y = spec["y"]
        ax.bar(df[x], df[y])
        ax.set_xlabel(x)
        ax.set_ylabel(y)
    elif chart_type == "line":
        x = spec["x"]
        y = spec["y"]
        ax.plot(df[x], df[y])
        ax.set_xlabel(x)
        ax.set_ylabel(y)
    elif chart_type == "histogram":
        col = spec.get("column") or spec.get("x")
        bins = spec.get("bins", 30)
        ax.hist(df[col].dropna(), bins=bins)
        ax.set_xlabel(col)
    # extend with pie, area, etc., as needed
    if spec.get("title"):
        ax.set_title(spec["title"])
    fig.tight_layout()
    return fig


def clear_query():
    st.session_state["query"] = ""
    # if you also store last result in session_state, clear it too:
    st.session_state.pop("last_result", None)
    st.session_state.pop("last_spec", None)



# Streamlit page configuration
st.set_page_config(page_title="Intelligent Dashboard", layout="wide")
st.title("Intelligent Dashboard")
st.markdown(
    "<div style='font-family:Georgia, serif; font-size:14px; font-style:italic; font-weight:500; color:#444;'>"
    "Author: Dennie &nbsp;&nbsp; July 2025"
    "</div>",
    unsafe_allow_html=True
)

# Load data
df = pd.read_excel("FruitData.xls")
df['Sales'] = round(df['Sales'],0)
df["Profit"] = round(df["Profit"], 2)
# df.head()

left_col, _, right_col = st.columns([1, 0.1, 2]) 



with left_col: 
    # Compute aggregates
    total_sales = df["Sales"].sum()
    total_profit = df["Profit"].sum()
    
    # Optional: inject CSS to make the boxes and numbers bigger / dashboard-like
    st.markdown("""
    <style>
    .kpi-container { display: flex; gap: 1rem; margin-bottom: 0.5rem; }
    .kpi-box {
        flex: 1;
        background: #f0f4f8;
        padding: 12px 16px;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .kpi-label { font-size: 0.9rem; color: #555; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 2.2rem; font-weight: 700; margin: 0; }
    .kpi-sub { font-size: 0.85rem; color: #777; }
    </style>
    """, unsafe_allow_html=True)
    
    # Render the KPIs side by side
    
    st.markdown(
        f"""
    <div class="kpi-container">
      <div class="kpi-box">
        <div class="kpi-label" style="font-weight: bold;">Total Sales</div>
        <div class="kpi-value">{total_sales:,.0f}</div>
        <div class="kpi-sub"></div>
      </div>
      <div class="kpi-box">
        <div class="kpi-label" style="font-weight: bold;">Total Profit</div>
        <div class="kpi-value">${total_profit:,.0f}</div>
        <div class="kpi-sub"></div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    


    
    st.markdown("             ")
    st.markdown("<h6 style='text-align: center;'>-------------------------- Raw Data Preview ---------------------------</h6>", unsafe_allow_html=True)
    all_markets = df["Market"].unique()
    selected_mrkt = st.multiselect('Select Market(s):', options=all_markets, default=list(all_markets))
    df_mrkt = df[df['Market'].isin(selected_mrkt)]
    df_s = df_mrkt.style.background_gradient(subset = ["Sales", "Profit"], cmap = 'YlGnBu')
    st.dataframe(df_s, width=600, height=750, hide_index=True,
                 column_config={
                        "Sales": st.column_config.NumberColumn(
                            "Sales",
                            format="%.0f"  # Numeric with no decimals
                        ),
                        "Profit": st.column_config.NumberColumn(
                            "Profit",
                            format="$ %.2f"  # Float with 2 decimals and dollar sign
                        )
                    }
                 )

with right_col:
    
    st.subheader(":blue[Ask any question in plain English to query the data]")
    st.markdown(
    """
    Examples:
    - "Which market has the most sales?"
    - "Show me total sales per product type sorted descending."
    - "What is the average sales across all markets?"
    - "Create a chart for sales by market"
    """
    )
    query = st.text_input("Enter your question about the data:", key = "query")
    
    # clear button uses callback
    st.button("Clear query", on_click = clear_query)
    
    if query:
        prompt = query + ". Do not save charts to disk and do not execute any commands that open external viewers."
        
        with st.spinner("Processing your query..."):
            try:
                llm = OpenAI(api_token=enable_key, model=your_model)
                smart_df = sdf(
                    df,
                    config={"llm": llm, "verbose": False, "save_logs": False}
                )
    
                # snapshot existing figures so we can detect new ones the agent creates
                before_figs = set(plt.get_fignums())
    
                result = None
                try:
                    result = smart_df.chat(prompt)
                except Exception as e:
                    st.warning(f"Agent summary failed: {e}")

    
                # 1. Display any new matplotlib figures the agent created directly.
                new_figs = set(plt.get_fignums()) - before_figs
                if new_figs:
                    st.markdown("#### :blue[Chart]")
                    seen_hashes = set()
                    for num in sorted(new_figs):
                        fig = plt.figure(num)
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        h = hashlib.sha256(buf.getvalue()).hexdigest()
                        if h in seen_hashes:
                            plt.close(fig)
                            continue  # skip duplicate
                        seen_hashes.add(h)
                        st.image(buf)  # display unique chart inline
                        plt.close(fig)
                        
                # 2. If the result looks like a JSON spec, try to parse and draw it.
                spec = None
                if isinstance(result, str):
                    try:
                        spec = json.loads(result)
                    except json.JSONDecodeError:
                        spec = None
                elif isinstance(result, dict):
                    spec = result
    
                if spec and isinstance(spec, dict) and "chart_type" in spec:
                    try:
                        fig = build_chart_from_spec(spec, df)
                        st.subheader("Chart (from parsed specification)")
                        st.pyplot(fig)
                        plt.close(fig)
                    except Exception as e:
                        st.warning(f"Failed to render chart from spec: {e}")
    
                # 3. DataFrame result
                if isinstance(result, pd.DataFrame):
                    st.subheader("Query Result (Table)")
                    st.dataframe(result)
    
                # 4. Fallback: show text answer if nothing else rendered
                if not isinstance(result, pd.DataFrame) and not (spec and "chart_type" in spec) and not new_figs:
                    st.markdown("#### :blue[Answer:]")
                    st.markdown("""
                    <style>
                    .big-bold-result {
                      font-size: 18px;
                      font-weight: 500;
                      line-height:1.1;
                      margin: 4px 0;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<div class='big-bold-result'>{html.escape(str(result))}</div>", unsafe_allow_html=True)
    
            except Exception as e:
                st.error(f"Unexpected error: {e}")
        
