import datetime
from zoneinfo import ZoneInfo

def is_market_open(ticker: str) -> bool:
    """
    Check if the market is open for the given ticker based on the current time.
    - Indian Market (.NS / .BO): 9:30 AM to 3:30 PM IST (Mon-Fri)
    - US Market: 9:30 AM to 4:00 PM EST (Mon-Fri), which is 6:30 AM to 1:00 PM PST.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        # Indian Market
        now_ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
        # Mon-Fri (0-4)
        if now_ist.weekday() > 4:
            return False
            
        market_open = datetime.time(9, 30)
        market_close = datetime.time(15, 30)
        
        current_time = now_ist.time()
        return market_open <= current_time <= market_close
        
    else:
        # US Market
        now_est = now_utc.astimezone(ZoneInfo("America/New_York"))
        # Mon-Fri (0-4)
        if now_est.weekday() > 4:
            return False
            
        market_open = datetime.time(9, 30)
        market_close = datetime.time(16, 0)
        
        current_time = now_est.time()
        return market_open <= current_time <= market_close
