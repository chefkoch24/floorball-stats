from src import player_insights as pi


def _goal(minute, period, side, score, scorer, assist=None, tag="regular", team=None):
    team = team or ("Home FC" if side == "home" else "Away IBK")
    return {
        "minute": minute,
        "period": period,
        "team": team,
        "side": side,
        "score": score,
        "event_kind": "goal",
        "title": scorer,
        "title_uid": f"player-{scorer.lower()}",
        "assist": assist,
        "assist_uid": f"player-{assist.lower()}" if assist else None,
        "tag": tag,
    }


def _flags(events):
    return [sorted(moment.flags) for moment in pi.goal_moments(events)]


def test_game_winner_is_the_goal_one_past_the_losers_total():
    events = [
        _goal("05:00", 1, "home", "1:0", "Anna"),
        _goal("08:00", 1, "away", "1:1", "Bea"),
        _goal("02:00", 2, "home", "2:1", "Cara", assist="Anna"),
        _goal("15:00", 3, "home", "3:1", "Anna"),
        _goal("19:00", 3, "away", "3:2", "Bea"),
    ]
    # Final 3:2, so the home team's third goal decided it, not the go-ahead goal before.
    assert _flags(events) == [
        [pi.GO_AHEAD],
        [pi.EQUALIZER],
        [pi.GO_AHEAD],
        [pi.GWG],
        [],
    ]


def test_late_tie_breakers_and_equalizers_are_clutch_and_overtime_goals_win():
    events = [
        _goal("12:00", 3, "away", "0:1", "Bea"),
        _goal("15:30", 3, "home", "1:1", "Anna", assist="Cara"),
        {"minute": "60:00", "period": 3, "side": "break", "event_kind": "break", "title": "End of regulation"},
        _goal("OT 04:47", 4, "home", "2:1", "Cara", assist="Anna"),
    ]
    flags = _flags(events)
    assert flags[0] == [pi.CLUTCH, pi.GO_AHEAD]
    assert flags[1] == [pi.CLUTCH, pi.EQUALIZER]
    assert flags[2] == [pi.CLUTCH, pi.GO_AHEAD, pi.GWG, pi.OVERTIME]


def test_absolute_game_clock_is_read_per_period():
    # Czech feeds count the clock across periods: 52:00 in the third period is late, 45:00 is not.
    assert pi.minute_in_period("52:00", 3) == 12
    assert pi.minute_in_period("45:00", 3) == 5
    assert pi.minute_in_period("12:00", 3) == 12
    assert pi.minute_in_period("OT 04:30", 4) == 4.5
    events = [_goal("45:00", 3, "home", "1:0", "Anna"), _goal("52:00", 3, "away", "1:1", "Bea")]
    assert _flags(events) == [[pi.GO_AHEAD], [pi.CLUTCH, pi.EQUALIZER]]


def test_shootout_goals_and_own_goals_get_no_player_credit():
    events = [
        _goal("10:00", 1, "home", "1:0", "Own goal", tag="own_goal"),
        _goal("11:00", 1, "away", "1:1", "Bea"),
        _goal("PS", 5, "home", "2:1", "Anna", tag="penalty_shot"),
    ]
    moments = pi.goal_moments(events)
    assert len(moments) == 2
    assert moments[0].scorer is None
    # Tied after overtime: decided by penalty shots, so there is no game-winning goal.
    assert not any(pi.GWG in moment.flags for moment in moments)


def test_build_insights_aggregates_scopes_duos_and_partners():
    game = [
        _goal("05:00", 1, "home", "1:0", "Anna", assist="Cara"),
        _goal("06:00", 1, "home", "2:0", "Cara", assist="Anna"),
        _goal("07:00", 1, "home", "3:0", "Anna", assist="Cara"),
        _goal("15:00", 3, "away", "3:1", "Bea"),
    ]
    insights = pi.build_insights(
        [
            pi.GameEvents(category="se-26-27-regular-season", season="se-26-27", game_id="1", events=game),
            pi.GameEvents(category="se-25-26-regular-season", season="se-25-26", game_id="2", events=game),
        ]
    )
    anna = insights.clutch["se-26-27"]["player-anna"]
    assert (anna.goals, anna.assists, anna.gwg) == (2, 1, 0)
    # Anna's first goal broke the 0:0 tie, her second was a third goal: one of two goals changed the game.
    assert anna.as_dict()["game_changing"] == 1
    assert anna.as_dict()["game_changing_share"] == 50
    assert insights.clutch["all"]["player-anna"].goals == 4
    assert insights.clutch["se-26-27"]["player-cara"].gwg == 1

    [duo] = insights.top_duos("se-26-27-regular-season", team="Home FC")
    assert {duo.first.name, duo.second.name} == {"Anna", "Cara"}
    assert duo.goals == 3
    assert sorted([duo.first_to_second, duo.second_to_first]) == [1, 2]

    [(partner, goals_from, assists_to)] = insights.partners("se-26-27", "player-anna")
    assert (partner.name, goals_from, assists_to) == ("Cara", 2, 1)

    assert insights.moments[("se-26-27-regular-season", "1")] == {1: {pi.GWG}}


def test_women_leagues_without_player_ids_still_form_duos_by_name():
    events = [_goal("05:00", 1, "home", "1:0", "Anna", assist="Cara")]
    for event in events:
        event["title_uid"] = event["assist_uid"] = None
    insights = pi.build_insights([pi.GameEvents(category="sew-26-27-regular-season", season="sew-26-27", game_id="1", events=events)])
    [duo] = insights.top_duos("sew-26-27-regular-season")
    assert {duo.first.key, duo.second.key} == {"Home FC|Anna", "Home FC|Cara"}
    assert duo.first.uid == duo.second.uid == ""


def test_moment_labels_round_trip_through_the_payload():
    events = [_goal("OT 01:00", 4, "away", "0:1", "Bea")]
    flagged = {moment.index: moment.flags for moment in pi.goal_moments(events)}
    decoded = pi.decode_events(pi.encode_events(pi.label_moments(events, flagged)))
    assert decoded[0]["moment"] == "Game winner · Overtime"
    assert pi.season_of("26-27-playoffs") == "26-27"
    assert pi.season_of("se-26-27-regular-season") == "se-26-27"
