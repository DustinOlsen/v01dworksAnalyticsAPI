import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
from .database import get_db

def get_daily_data(site_id: str) -> pd.DataFrame:
    """
    Fetches daily stats from the database and returns a Pandas DataFrame.
    """
    conn = get_db(site_id)
    query = "SELECT date, total_visits, unique_visitors FROM daily_stats ORDER BY date ASC"
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

def generate_forecast(site_id: str, days: int = 7):
    """
    Predicts future traffic using Linear Regression.
    """
    df = get_daily_data(site_id)
    
    # Need at least 3 data points to make a reasonable trend line
    if len(df) < 3:
        return {
            "can_forecast": False,
            "message": "Not enough data. Need at least 3 days of history."
        }
    
    # Prepare data for Linear Regression
    # We use ordinal dates (integer representation) as the feature
    df['day_ordinal'] = df['date'].map(datetime.toordinal)
    
    X = df[['day_ordinal']]
    y = df['total_visits']
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Predict future dates
    last_date = df['date'].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, days + 1)]
    future_ordinals = [[d.toordinal()] for d in future_dates]
    
    predictions = model.predict(future_ordinals)
    
    forecast = []
    for date, pred in zip(future_dates, predictions):
        forecast.append({
            "date": date.strftime("%Y-%m-%d"),
            "predicted_visits": int(max(0, pred))  # Ensure no negative predictions
        })
        
    # Calculate trend slope (visits per day)
    slope = model.coef_[0]
    trend = "stable"
    if slope > 0.5: trend = "increasing"
    elif slope < -0.5: trend = "decreasing"
        
    return {
        "can_forecast": True,
        "forecast": forecast,
        "trend": trend,
        "slope": round(slope, 2)
    }

def generate_summary(site_id: str):
    """
    Generates statistical summaries and insights.
    """
    df = get_daily_data(site_id)
    
    if df.empty:
        return {"error": "No data available"}
        
    # 1. Basic Averages
    avg_daily_visits = df['total_visits'].mean()
    avg_daily_unique = df['unique_visitors'].mean()
    
    # 2. Busiest Day of Week
    df['day_name'] = df['date'].dt.day_name()
    busiest_day = df.groupby('day_name')['total_visits'].mean().idxmax()
    
    # 3. Weekly Growth (Last 7 days vs Previous 7 days)
    current_week_visits = 0
    previous_week_visits = 0
    growth_rate = 0.0
    
    if len(df) >= 14:
        last_7 = df.tail(7)
        prev_7 = df.iloc[-14:-7]
        
        current_week_visits = last_7['total_visits'].sum()
        previous_week_visits = prev_7['total_visits'].sum()
        
        if previous_week_visits > 0:
            growth_rate = ((current_week_visits - previous_week_visits) / previous_week_visits) * 100
    
    return {
        "average_daily_visits": round(avg_daily_visits, 1),
        "average_daily_unique": round(avg_daily_unique, 1),
        "busiest_day_of_week": busiest_day,
        "weekly_growth": {
            "current_week_visits": int(current_week_visits),
            "previous_week_visits": int(previous_week_visits),
            "growth_rate_percent": round(growth_rate, 1)
        }
    }

def detect_anomalies(site_id: str):
    """
    Detects unusual traffic patterns using Isolation Forest.
    """
    df = get_daily_data(site_id)
    
    # Need reasonable amount of data for anomaly detection
    if len(df) < 5:
        return {
            "has_anomalies": False,
            "message": "Not enough data. Need at least 5 days of history."
        }
        
    # Prepare data
    X = df[['total_visits']]
    
    # Fit Isolation Forest
    # contamination='auto' lets the model decide the threshold
    iso_forest = IsolationForest(contamination='auto', random_state=42)
    df['anomaly'] = iso_forest.fit_predict(X)
    
    # -1 indicates anomaly, 1 indicates normal
    anomalies = df[df['anomaly'] == -1].copy()
    
    results = []
    if not anomalies.empty:
        # Calculate mean to determine if it's a spike (high) or dip (low)
        mean_visits = df['total_visits'].mean()
        
        for _, row in anomalies.iterrows():
            visit_count = row['total_visits']
            type_ = "spike" if visit_count > mean_visits else "dip"
            
            results.append({
                "date": row['date'].strftime("%Y-%m-%d"),
                "visits": int(visit_count),
                "type": type_
            })
            
    return {
        "has_anomalies": len(results) > 0,
        "anomalies": results
    }

def detect_bots(site_id: str):
    """
    Identifies potential bots using Isolation Forest on visitor activity.
    """
    conn = get_db(site_id)
    try:
        # Fetch visitor activity
        query = "SELECT * FROM visitor_activity"
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
        
    if len(df) < 10:
        return {"message": "Not enough data for bot detection (need > 10 visitors)"}
        
    # Features for detection:
    # 1. Request Count (High count = suspicious)
    # 2. Duration (Last Seen - First Seen) in seconds
    # 3. Rate (Requests / Duration)
    
    df['first_seen'] = pd.to_datetime(df['first_seen'])
    df['last_seen'] = pd.to_datetime(df['last_seen'])
    df['duration'] = (df['last_seen'] - df['first_seen']).dt.total_seconds()
    
    # Avoid division by zero
    df['duration'] = df['duration'].replace(0, 1) 
    df['request_rate'] = df['request_count'] / df['duration']
    
    # Prepare features
    features = ['request_count', 'request_rate', 'ua_score']
    X = df[features].fillna(0)
    
    # Detect anomalies
    iso_forest = IsolationForest(contamination=0.05, random_state=42) # Assume top 5% are suspicious
    df['is_bot'] = iso_forest.fit_predict(X)
    
    # Filter bots (-1)
    bots = df[df['is_bot'] == -1].copy()
    
    results = []
    for _, row in bots.iterrows():
        reason = []
        if row['request_count'] > df['request_count'].mean() * 2:
            reason.append("High Request Volume")
        if row['request_rate'] > df['request_rate'].mean() * 2:
            reason.append("Abnormal Request Rate")
        if row['ua_score'] > 0.8:
            reason.append("Suspicious User Agent")

        if not reason:
            reason.append("Unusual Pattern")

        # Determine whether this was flagged at track time or only by ML
        if 'bot_type' in df.columns:
            raw_bt = row['bot_type']
            tracked_bot_type = raw_bt if (isinstance(raw_bt, str) and raw_bt in ('bot', 'crawler')) else 'none'
        else:
            tracked_bot_type = 'none'

        flagged_at_track_time = tracked_bot_type in ('bot', 'crawler')
        detected_type = tracked_bot_type if flagged_at_track_time else "ml_suspected"

        results.append({
            "ip_hash": row['ip_hash'],
            "request_count": int(row['request_count']),
            "reason": ", ".join(reason),
            "flagged_at_track_time": flagged_at_track_time,
            "detected_type": detected_type,
        })

    return {
        "detected_bots_count": len(results),
        "bots": results,
    }
