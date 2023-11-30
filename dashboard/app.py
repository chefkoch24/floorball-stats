# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.
import json
from dash import Dash, html, dcc, Output, Input, dash_table
import plotly.express as px
import pandas as pd
import requests
from dotenv import load_dotenv
import os
import dash_bootstrap_components as dbc
from plotly.subplots import make_subplots
from supabase import create_client, Client
import plotly.graph_objects as go


load_dotenv()

app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])

# Instantiate the client with an endpoint.
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# data = requests.get(f"{url}/rest/v1/stats?select=*,teams(team_name)", headers={'apikey': key}).json()
# flatten the json
# data = [dict(**d, **d.pop('teams')) for d in data]

# df = pd.DataFrame(data)
df = pd.read_csv('../data/processed_stats.csv')
df = df.rename(columns={'team': 'team_name'})

fig_goals = px.bar(df, x="team_name", y=["goals", 'goals_against'], barmode="group",
                   labels={'goals': 'Goals', 'goals_against': 'Goals Against'})

fig_penalties = px.bar(df, x="team_name", y=['powerplay', 'boxplay'], barmode="group",
                       labels={'powerplay': 'Powerplay', 'boxplay': 'Boxplay'})
fig_efficeny = px.scatter(df, x="boxplay_efficiency", y='powerplay_efficiency', text='team_name',
                          hover_name='team_name', hover_data=['rank', 'points', 'points_per_game'],
                          labels={'powerplay_efficiency': 'Powerplay Effizienz',
                                  'boxplay_efficiency': 'Boxplay Effizienz'})
fig_efficeny.update_traces(textposition='top center')

teams = df['team_name'].to_list()
points_against = df['points_against'].to_list()

heatmap = pd.DataFrame(columns=['team_name'] + teams)

heatmap_data = []
for points, team in zip(points_against, teams):
    points = json.loads(points.replace("'", '"'))
    d = {'team_name': team}
    d.update(points)
    heatmap_data.append(d)
heatmap = pd.DataFrame(heatmap_data, columns=['team_name'] + teams, index=teams)

fig_points_against = px.imshow(heatmap[teams], y=teams, text_auto=True)
fig_points_against = fig_points_against.update_layout(showlegend=False)

fig_goals_per_game = px.scatter(df, x="goals_per_game", text='team_name', hover_name='team_name',
                                hover_data=['points', 'points_per_game', 'scoring_ratio'], y='goals_against_per_game',
                                labels={'goals_per_game': 'Goals per Game',
                                        'goals_against_per_game': 'Goals Against per Game'})
fig_goals_per_game.update_traces(textposition='top center')

special_goals_fig = px.bar(df, x="team_name",
                           y=['leading_goals', 'equalizer_goals', 'first_goal_of_match', 'penalty_shot_goals'],
                           labels={'leading_goals': 'Leading Goals', 'equalizer_goals': 'Equalizer Goals',
                                   'first_goal_of_match': 'First Goal of Match',
                                   'penalty_shot_goals': 'Penalty Shot Goals',
                                   })

special_goals_against_fig = px.bar(df, x="team_name",
                           y=['leading_goals_against', 'equalizer_goals_against', 'first_goal_of_match_against', 'penalty_shot_goals_against'],
                           labels={'leading_goals_against': 'Leading Goals', 'equalizer_goals_against': 'Equalizer Goals',
                                   'first_goal_of_match_against': 'First Goal of Match',
                                   'penalty_shot_goals_against': 'Penalty Shot Goals',
                                   })
special_goals_fig.update_xaxes(tickangle=25)
special_goals_fig.update_yaxes(range=[0,60])
special_goals_against_fig.update_xaxes(tickangle=25)
# set the same max values
special_goals_against_fig.update_yaxes(range=[0, 60])

columns = [c for c, t in zip(df.columns, df.iloc[0]) if type(t) not in [dict, list]]

app.layout = dbc.Container(html.Div(children=[
    html.H1(children='Floorball Bundesliga Dashboard'),

    dbc.Row(children=[dcc.Dropdown(
        id='period-filter',
        options=[
            {'label': period, 'value': period} for period in
            ['full_game', 'first_period', 'second_period', 'third_period', 'overtime']
        ],
        value='full_game'  # Default selection
    )]),
    dbc.Row(children=[
        dbc.Col(dcc.Graph(id='goals-graph', figure=fig_goals, )),  # config={'edits': {'legendPosition': False, }})),
        dbc.Col(dcc.Graph(id='penalty-graph', figure=fig_penalties,  )),#config={'edits': {'legendPosition': False, }}))
    ]),
    dbc.Row(children=[
        dbc.Col(
            dcc.Graph(id='efficiency-graph', figure=fig_efficeny),
        ),
        dbc.Col(dcc.Graph(id='fig_goals_per_game', figure=fig_goals_per_game)),

    ]),
    dbc.Row(
        children=[
            dbc.Col(children=[dcc.Graph(id='fig_points_against', figure=fig_points_against)])
        ]
    ),
    dbc.Row(
        children=[
            dbc.Col(children=[dcc.Graph(id='special_goals_fig', figure=special_goals_fig),]),
            dbc.Col(children=[dcc.Graph(id='special_goals_against_fig', figure=special_goals_against_fig),])
        ]
    ),
    dcc.Checklist(id='table-columns',
                  options=[{'label': col, 'value': col} for col in [
                      'points_per_game',
                      'home_points',
                      'away_points',
                  ]],
                  inline=True
                  ),
    dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i} for i in columns],
        data=df[columns].to_dict('records'),
        sort_action='native',
        style_cell={'text-align': 'left'}
    )
]), fluid=False)


@app.callback(
    Output('goals-graph', 'figure'),
    [Input('period-filter', 'value')]
)
def update_goals_graph(selected_period):
    goals, goals_against = 'goals', 'goals_against'
    if selected_period == 'first_period':
        goals += '_in_first_period'
        goals_against = 'goals_in_first_period_against'
    elif selected_period == 'second_period':
        goals += '_in_second_period'
        goals_against = 'goals_in_second_period_against'
    elif selected_period == 'third_period':
        goals += '_in_third_period'
        goals_against = 'goals_in_third_period_against'
    elif selected_period == 'overtime':
        goals += '_in_overtime'
        goals_against = 'goals_in_overtime_against'

    fig = px.bar(df, x="team_name", y=[goals, goals_against], barmode="group", labels={'goals': 'Goals', 'goals_against': 'Goals Against'})
    fig.update_xaxes(title_text='Teams')
    fig.update_yaxes(title_text='Goals')
    #fig.update_layout(showlegend=False)
    return fig


@app.callback(
    Output('table', 'columns'),
    [Input('table-columns', 'value')])
def update_table(selected_columns):
    default_columns = ['rank', 'team_name', 'points', 'goals', 'goals_against']
    if selected_columns is not None:
        columns = default_columns + selected_columns
    else:
        columns = default_columns
    return [{"name": col, "id": col} for col in columns]


@app.callback(
    Output('penalty-graph', 'figure'),
    [Input('period-filter', 'value')]
)
def update_penalties_graph(selected_period):
    powerplay, boxplay = 'powerplay', 'boxplay'
    if selected_period == 'first_period':
        powerplay += '_first_period'
        boxplay += '_first_period'
    elif selected_period == 'second_period':
        powerplay += '_second_period'
        boxplay += '_second_period'
    elif selected_period == 'third_period':
        powerplay += '_third_period'
        boxplay += '_third_period'
    elif selected_period == 'overtime':
        powerplay += '_overtime'
        boxplay += '_overtime'
    fig = px.bar(df, x="team_name", y=[powerplay, boxplay], barmode="group")
    return fig


if __name__ == '__main__':
    app.run(debug=True)
