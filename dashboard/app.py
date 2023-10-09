# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.


from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
import requests

app = Dash(__name__)

from python_graphql_client import GraphqlClient

# Instantiate the client with an endpoint.
client = GraphqlClient(endpoint="http://127.0.0.1:8000/graphql/")

# Create the query string and variables required for the request.
query = """
    query {
        stats {
            team{
                teamName
            }
            goals
        }
    }
"""
#variables = {"countryCode": "CA"}
data = client.execute(query=query)# variables=variables)
def flatten(data):
    for key, value in data.items():


print(data)

# assume you have a "long-form" data frame
# see https://plotly.com/python/px-arguments/ for more options

#data = requests.get("http://127.0.0.1:8000/stats/").json()
df = pd.DataFrame(data)


fig = px.bar(df, x="teamName", y="goals", barmode="group")

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
