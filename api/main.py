import strawberry
from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session
from strawberry.fastapi import GraphQLRouter

from api import crud, models
from api.database import SessionLocal, engine
from api.graphql_schema import Query


models.Base.metadata.create_all(bind=engine)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


schema = strawberry.Schema(Query)


async def get_context(db=Depends(get_db)):
    return {
        "db": db,
    }

app = FastAPI()


@app.get("/")
def index():
    return {"message": "I'm alive!"}


@app.get("/stats/")
def get_stats(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_stats(db=db, skip=skip, limit=limit)


@app.get("/stats/{stats_id}")
def get_stats_by_id(stats_id: int, db: Session = Depends(get_db)):
    return crud.get_stats_by_id(db=db, stats_id=stats_id)


@app.get("/stats/{name}")
def get_user_by_name(name: str, db: Session = Depends(get_db)):
    return crud.get_stats_by_name(db=db, name=name)

@app.get("/teams/")
def get_teams(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_teams(db=db, skip=skip, limit=limit)

@app.get("/teams/{team_id}")
def get_teams_by_id(team_id: int, db: Session = Depends(get_db)):
    return crud.get_teams_by_id(db=db, team_id=team_id)

@app.get("/leagues/")
def get_leagues(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_leagues(db=db, skip=skip, limit=limit)

@app.get("/leagues/{league_id}")
def get_leagues_by_id(league_id: int, db: Session = Depends(get_db)):
    return crud.get_leagues_by_id(db=db, league_id=league_id)


graphql_app = GraphQLRouter(schema=schema, context_getter=get_context, graphiql=False)

app.include_router(graphql_app, prefix="/graphql")