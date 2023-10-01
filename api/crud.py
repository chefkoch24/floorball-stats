from sqlalchemy.orm import Session
from api import models


def get_stats_by_id(db: Session, stats_id: int):
    return db.query(models.Stats).filter(models.Stats.id == stats_id).first()

def get_stats_by_name(db: Session, name: str):
    return db.query(models.Stats).filter(models.Stats.name == name).first()


def get_stats(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Stats).offset(skip).limit(limit).all()

def get_teams(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Team).offset(skip).limit(limit).all()

def get_teams_by_id(db: Session, team_id: int):
    return db.query(models.Team).filter(models.Team.id == team_id).first()

def get_leagues(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.League).offset(skip).limit(limit).all()

def get_leagues_by_id(db: Session, league_id: int):
    return db.query(models.League).filter(models.League.id == league_id).first()

