from pathlib import Path

import pandas as pd

from src.run_stats_engine import run_stats_pipeline


def test_wfc_game_metadata_is_read_from_available_result_row(tmp_path):
    source = Path(__file__).parent / 'fixtures/wfc/partial-metadata.csv'
    frame = pd.read_csv(source)
    frame = frame[frame['game_id'].isin([7194, 7195, 7196])].copy()
    # Database ordering can put event rows with empty metadata before the result row.
    frame = pd.concat([frame[frame.event_type != 'result'], frame[frame.event_type == 'result']])
    frame.loc[frame.event_type != 'result', 'game_date'] = 'NaN'
    frame.loc[frame.event_type != 'result', 'game_start_time'] = 'None'
    result = run_stats_pipeline(input_csv_path=str(source), input_df=frame, output_dir=str(tmp_path), season='wfc-2024', phase='regular-season')
    games = {int(game['game_id']): game for game in result['game_stats']}
    for game_id, date, time, attendance, score in [
        (7194, '2024-12-08', '10:00', 193, '9-3'),
        (7195, '2024-12-08', '13:00', 317, '2-6'),
        (7196, '2024-12-09', '08:30', 1449, '7-7'),
    ]:
        assert (games[game_id]['date'], games[game_id]['start_time'], games[game_id]['attendance'], games[game_id]['result_string']) == (date, time, attendance, score)
