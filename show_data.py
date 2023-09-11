import streamlit as st
import pandas as pd

st.write("Here's our first attempt at using data to create a table:")
data = pd.read_csv("data/processed_stats.csv")
st.write(data)

st.line_chart(data['goals'])
st.bar_chart(data[['goals', 'points']])


