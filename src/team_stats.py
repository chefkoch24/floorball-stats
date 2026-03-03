import json
from typing import Dict, Any


class TeamStats:
    def __init__(self, team: str, stats: Dict[str, Any] | None = None):
        self.team = team
        self.stats: Dict[str, Any] = {} if stats is None else stats

    def to_dict(self) -> Dict[str, Any]:
        """convert to dictionary"""
        return {
            'team': self.team,
            'stats': self.stats
        }

    def to_json(self) -> str:
        """Serializining TeamStats to JSON string"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeamStats':
        """Creates TeamStats from dictionary"""
        return cls(team=data['team'], stats=data.get('stats', {}))

    @classmethod
    def from_json(cls, json_str: str) -> 'TeamStats':
        """Creates TeamStats from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
