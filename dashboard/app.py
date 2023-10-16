# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.


from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
import requests
from dotenv import load_dotenv
import os

from supabase import create_client, Client

load_dotenv()

app = Dash(__name__)

from python_graphql_client import GraphqlClient

# Instantiate the client with an endpoint.
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

data = requests.get(f"{url}/rest/v1/stats?select=*,teams(team_name)", headers={'apikey': key}).json()
# flatten the json
data = [dict(**d, **d.pop('teams')) for d in data]

df = pd.DataFrame(data)


fig = px.bar(df, x="team_name", y="goals", barmode="group")

app.layout = html.Div(children=[
    html.H1(children='Hello Dash'),

    html.Div(children='''
        Dash: A web application framework for your data.
    '''),

    dcc.Graph(
        id='example-graph',
        figure=fig
    )
])

if __name__ == '__main__':
    app.run(debug=True)
