import datetime

def today_date(request):
    return {'today': datetime.date.today()}
