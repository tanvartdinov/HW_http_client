"""Один источник данных для HTML и JSON. Запуск: python -m uvicorn app.main:app --reload."""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
Category = Literal['concert', 'theatre', 'exhibition']
LABELS = {'concert': 'Концерты', 'theatre': 'Театр', 'exhibition': 'Выставки'}

class Event(BaseModel):
    id: int
    title: str
    category: Category
    theme: str
    poster_title: str
    poster_subtitle: str
    starts_at: datetime
    venue: str
    address: str
    price: int
    currency: str
    organizer: str
    description: str
    age_limit: str
    url: str

class EventList(BaseModel):
    items: list[Event]
    total: int

EVENTS = [Event.model_validate(row) for row in json.loads((ROOT / 'data/events.json').read_text(encoding='utf-8'))]
app = FastAPI(title='Афиша — учебный API', version='1.0.0', description='Вымышленные мероприятия. HTML и API используют один набор данных. Поиск q — подстрока названия без учёта регистра.')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
templates = Jinja2Templates(directory=ROOT / 'templates')
templates.env.globals['labels'] = LABELS
MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря')
templates.env.filters['date_ru'] = lambda value: f'{value.day} {MONTHS[value.month - 1]} · {value:%H:%M}'
templates.env.filters['money'] = lambda value: 'Бесплатно' if value == 0 else f'{value:,} ₽'.replace(',', ' ')

def select_events(q: str, category: str | None) -> list[Event]:
    needle = q.strip().casefold()
    return [event for event in EVENTS if needle in event.title.casefold() and (category is None or event.category == category)]

def get_event(event_id: int) -> Event:
    for event in EVENTS:
        if event.id == event_id:
            return event
    raise HTTPException(404, 'Мероприятие не найдено')

@app.get('/', response_class=HTMLResponse, include_in_schema=False)
def index(request: Request, q: str = Query('', max_length=100), category: Category | None = None):
    events = select_events(q, category)
    return templates.TemplateResponse(request=request, name='index.html', context={'events': events, 'q': q, 'category': category})

@app.get('/events/{event_id}', response_class=HTMLResponse, include_in_schema=False)
def detail(request: Request, event_id: int):
    event = next((item for item in EVENTS if item.id == event_id), None)
    return templates.TemplateResponse(request=request, name='detail.html', context={'event': event}, status_code=200 if event else 404)

@app.get('/api/v1/events', response_model=EventList, tags=['Мероприятия'])
def api_events(q: str = Query('', max_length=100, description='Поиск по подстроке названия'), category: Category | None = None):
    items = select_events(q, category)
    return EventList(items=items, total=len(items))

@app.get('/api/v1/events/{event_id}', response_model=Event, tags=['Мероприятия'])
def api_event(event_id: int):
    return get_event(event_id)

@app.get('/health', tags=['Сервис'])
def health():
    return {'status': 'ok'}

@app.get('/robots.txt', include_in_schema=False)
def robots():
    return Response('User-agent: *\nAllow: /\n', media_type='text/plain')

@app.get('/demo/500', tags=['Учебные сбои'], status_code=500)
def server_error():
    return JSONResponse({'detail': 'Учебная ошибка сервера'}, status_code=500)

@app.get('/demo/timeout', tags=['Учебные сбои'])
async def timeout(seconds: float = Query(5, ge=0, le=30)):
    await asyncio.sleep(seconds)
    return {'status': 'ok'}

@app.get('/demo/broken-json', tags=['Учебные сбои'])
def broken_json():
    return Response('{"items": [', media_type='application/json')

@app.get('/demo/bad-schema', tags=['Учебные сбои'])
def bad_schema():
    return {'items': [{'name': 'Концерт без обязательных полей'}], 'count': 1}

@app.get('/demo/rate-limited', tags=['Учебные сбои'], status_code=429)
def rate_limited():
    return JSONResponse({'detail': 'Учебное ограничение: этот маршрут всегда возвращает 429'}, status_code=429, headers={'Retry-After': '2'})
