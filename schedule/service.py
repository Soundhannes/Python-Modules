from datetime import datetime, timedelta


def calculate_next_run(schedule: dict, reference_time: datetime = None) -> datetime:
    if reference_time is None:
        reference_time = datetime.now()
    
    schedule_type = schedule['type']
    
    if schedule_type == 'interval':
        interval_minutes = schedule['interval_minutes']
        return reference_time + timedelta(minutes=interval_minutes)
    
    elif schedule_type == 'daily':
        time_str = schedule['time_of_day']
        hour, minute = map(int, time_str.split(':'))
        
        next_run = reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_run <= reference_time:
            next_run += timedelta(days=1)
        
        return next_run
    
    elif schedule_type == 'weekly':
        day_of_week = schedule['day_of_week']
        time_str = schedule['time_of_day']
        hour, minute = map(int, time_str.split(':'))
        
        current_day = reference_time.weekday()
        days_ahead = day_of_week - current_day
        
        if days_ahead <= 0:
            days_ahead += 7
        
        next_run = reference_time + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return next_run
    
    elif schedule_type == 'monthly':
        day_of_month = schedule['day_of_month']
        time_str = schedule['time_of_day']
        hour, minute = map(int, time_str.split(':'))
        
        try:
            next_run = reference_time.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            
            if next_run <= reference_time:
                if reference_time.month == 12:
                    next_run = next_run.replace(year=reference_time.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=reference_time.month + 1)
        except ValueError:
            if reference_time.month == 12:
                next_run = reference_time.replace(year=reference_time.year + 1, month=1, day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
            else:
                next_run = reference_time.replace(month=reference_time.month + 1, day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        
        return next_run
