"""
ESPN NBA Adapter
Fetches live NBA data from ESPN's public API.
"""
import httpx
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from .interface import NBADataProvider
from models.game import Game, GameStatus, Team

logger = logging.getLogger(__name__)

class ESPNAdapter(NBADataProvider):
    """
    ESPN NBA Data Adapter.
    Uses ESPN's public scoreboard API for live game data.
    """
    
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def get_live_games(self) -> List[Game]:
        """Get all currently live NBA games"""
        games = await self.get_todays_games()
        return [g for g in games if g.status == GameStatus.LIVE]
    
    async def get_game_by_id(self, game_id: str) -> Optional[Game]:
        """Get a specific game by ESPN ID"""
        try:
            url = f"{self.BASE_URL}/summary?event={game_id}"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return self._parse_game_detail(data)
        except Exception as e:
            logger.error(f"Error fetching game {game_id}: {e}")
            return None
    
    async def get_todays_games(self) -> List[Game]:
        """Get all NBA games for today"""
        try:
            url = f"{self.BASE_URL}/scoreboard"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            return self._parse_scoreboard(data)
        except Exception as e:
            logger.error(f"Error fetching today's games: {e}")
            return []
    
    async def get_upcoming_games(self, days: int = 7) -> List[Game]:
        """Get upcoming NBA games"""
        games = []
        for i in range(days):
            date = datetime.utcnow() + timedelta(days=i)
            date_str = date.strftime("%Y%m%d")
            try:
                url = f"{self.BASE_URL}/scoreboard?dates={date_str}"
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json()
                games.extend(self._parse_scoreboard(data))
            except Exception as e:
                logger.error(f"Error fetching games for {date_str}: {e}")
        return games
    
    async def refresh_game(self, game_id: str) -> Optional[Game]:
        """Refresh live data for a specific game"""
        return await self.get_game_by_id(game_id)
    
    def _parse_scoreboard(self, data: dict) -> List[Game]:
        """Parse ESPN scoreboard response into Game objects"""
        games = []
        events = data.get('events', [])
        
        for event in events:
            try:
                game = self._parse_event(event)
                if game:
                    games.append(game)
            except Exception as e:
                logger.error(f"Error parsing event: {e}")
        
        return games
    
    def _parse_event(self, event: dict) -> Optional[Game]:
        """Parse a single ESPN event into a Game object"""
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            # Find home and away teams
            home_data = next((c for c in competitors if c['homeAway'] == 'home'), None)
            away_data = next((c for c in competitors if c['homeAway'] == 'away'), None)
            
            if not home_data or not away_data:
                return None
            
            # Parse teams
            home_team = Team(
                id=home_data['team']['id'],
                name=home_data['team']['displayName'],
                abbreviation=home_data['team']['abbreviation'],
                logo_url=home_data['team'].get('logo')
            )
            
            away_team = Team(
                id=away_data['team']['id'],
                name=away_data['team']['displayName'],
                abbreviation=away_data['team']['abbreviation'],
                logo_url=away_data['team'].get('logo')
            )
            
            # Parse status
            status_data = competition.get('status', {})
            status_type = status_data.get('type', {}).get('name', '')
            
            if status_type == 'STATUS_SCHEDULED':
                status = GameStatus.SCHEDULED
            elif status_type == 'STATUS_IN_PROGRESS':
                status = GameStatus.LIVE
            elif status_type == 'STATUS_HALFTIME':
                status = GameStatus.HALFTIME
            elif status_type == 'STATUS_FINAL':
                status = GameStatus.FINAL
            elif status_type == 'STATUS_POSTPONED':
                status = GameStatus.POSTPONED
            else:
                status = GameStatus.SCHEDULED
            
            # Parse scores
            home_score = int(home_data.get('score', 0))
            away_score = int(away_data.get('score', 0))
            
            # Parse time
            period = status_data.get('period', 0)
            clock = status_data.get('displayClock', '12:00')
            
            # Parse time remaining to seconds
            time_seconds = self._parse_clock_to_seconds(clock)
            
            # Parse start time
            start_time_str = event.get('date', '')
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except:
                start_time = datetime.utcnow()
            
            return Game(
                id=f"nba_{event['id']}",
                espn_id=event['id'],
                home_team=home_team,
                away_team=away_team,
                start_time=start_time,
                status=status,
                home_score=home_score,
                away_score=away_score,
                quarter=period,
                time_remaining=clock,
                time_remaining_seconds=time_seconds,
                last_updated=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    def _parse_game_detail(self, data: dict) -> Optional[Game]:
        """Parse ESPN game detail response"""
        # Similar to _parse_event but with more detail
        # For now, just use the event parser on the boxscore data
        try:
            event = {
                'id': data.get('header', {}).get('id'),
                'date': data.get('header', {}).get('competitions', [{}])[0].get('date'),
                'competitions': data.get('header', {}).get('competitions', [])
            }
            return self._parse_event(event)
        except Exception as e:
            logger.error(f"Error parsing game detail: {e}")
            return None
    
    def _parse_clock_to_seconds(self, clock: str) -> int:
        """Convert MM:SS clock string to seconds"""
        try:
            parts = clock.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(float(parts[1]))
            return 0
        except:
            return 0
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
