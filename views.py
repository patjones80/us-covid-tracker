
from datetime import *
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.template.defaulttags import register

import sqllib
import sys

SQL_FILE_DIR = "/home/pi/sqlite_3"
STATES = {
        'AK': 'Alaska',
        'AL': 'Alabama',
        'AR': 'Arkansas',
        'AS': 'American Samoa',
        'AZ': 'Arizona',
        'CA': 'California',
        'CO': 'Colorado',
        'CT': 'Connecticut',
        'DC': 'District of Columbia',
        'DE': 'Delaware',
        'FL': 'Florida',
        'GA': 'Georgia',
        'GU': 'Guam',
        'HI': 'Hawaii',
        'IA': 'Iowa',
        'ID': 'Idaho',
        'IL': 'Illinois',
        'IN': 'Indiana',
        'KS': 'Kansas',
        'KY': 'Kentucky',
        'LA': 'Louisiana',
        'MA': 'Massachusetts',
        'MD': 'Maryland',
        'ME': 'Maine',
        'MI': 'Michigan',
        'MN': 'Minnesota',
        'MO': 'Missouri',
        'MP': 'Northern Mariana Islands',
        'MS': 'Mississippi',
        'MT': 'Montana',
        'NC': 'North Carolina',
        'ND': 'North Dakota',
        'NE': 'Nebraska',
        'NH': 'New Hampshire',
        'NJ': 'New Jersey',
        'NM': 'New Mexico',
        'NV': 'Nevada',
        'NY': 'New York',
        'OH': 'Ohio',
        'OK': 'Oklahoma',
        'OR': 'Oregon',
        'PA': 'Pennsylvania',
        'PR': 'Puerto Rico',
        'RI': 'Rhode Island',
        'SC': 'South Carolina',
        'SD': 'South Dakota',
        'TN': 'Tennessee',
        'TX': 'Texas',
        'UT': 'Utah',
        'VA': 'Virginia',
        'VI': 'Virgin Islands',
        'VT': 'Vermont',
        'WA': 'Washington',
        'WI': 'Wisconsin',
        'WV': 'West Virginia',
        'WY': 'Wyoming'
}

base_context  = {'state_list': {k.lower():v for k, v in STATES.items()}, 'today': date.today()}

def eprint(*args, **kwargs):
    ''' print to apache error log; use for exception debugging
    '''
    print(*args, file=sys.stderr, **kwargs)

@register.filter
def get_state_abbr(dictionary, value):
    for k, v in dictionary.items():
        if v == value: 
            return k.lower()
    return None

# def index(request):
    # return HttpResponse('The US Covid Tracker is currently undergoing maintenance. Check back later.')

def index(request):
    return national(request)

def source_info(request):
    template = loader.get_template('covid_nyt/source.html')
    return HttpResponse(template.render(base_context, request))

def statistics(request):
    template = loader.get_template('covid_nyt/statistics.html')
    return HttpResponse(template.render(base_context, request))

def national(request):
#    try:
        data = sqllib.get_national()
        days = len(data)

        # current point in time
        as_of_date, total_cases, total_deaths, new_cases, new_deaths,  = (data[days-1][i] for i in range(0, 5))

        # time series
        ts_dates = [datetime.strftime(data[j][0], '%Y-%m-%d') for j in range(0, days)]
        ts_new_cases = [data[j][3] for j in range(0, days)]
        ts_rolling_avg = [data[j][5] for j in range(0, days)]

        eprint(type(ts_new_cases[0]))
                
        # current state rollups
        states = sqllib.get_all_states_current()

        context = {**base_context, **{'as_of_date'     : as_of_date,
                                      'total_cases'    : total_cases,
                                      'total_deaths'   : total_deaths,
                                      'new_cases'      : new_cases,
                                      'new_deaths'     : new_deaths,
                                      'ts_new_cases'   : ts_new_cases,
                                      'ts_dates'       : ts_dates,
                                      'ts_rolling_avg' : ts_rolling_avg,
                                      'states'         : states }}

        template = loader.get_template('covid_nyt/view_national.html')

#    except Exception as e:
        # eprint('Problem returning HTTP request: {}'.format(e))
        
        # context = base_context
        # template = loader.get_template('page_not_found.html')

        return HttpResponse(template.render(context, request))
        
def state(request, state_id):
    try:
        us_state = STATES[state_id.upper()]

        data = sqllib.get_state_rollup(us_state)
        days = len(data)
        
        # current point in time
        as_of_date, total_cases, total_deaths, new_cases, new_deaths,  = (data[days-1][i] for i in range(0, 5))
       
        # time series
        ts_dates = [datetime.strftime(data[j][0], '%Y-%m-%d') for j in range(0, days)]
        ts_new_cases = [data[j][3] for j in range(0, days)]
        ts_rolling_avg = [data[j][5] for j in range(0, days)]
        
        # county-level
        counties = sqllib.get_county_level(us_state)

        context = {**base_context, **{'state_name'     : us_state,
                                      'as_of_date'     : as_of_date,
                                      'total_cases'    : total_cases,
                                      'total_deaths'   : total_deaths,
                                      'new_cases'      : new_cases,
                                      'new_deaths'     : new_deaths,
                                      'ts_new_cases'   : ts_new_cases,
                                      'ts_dates'       : ts_dates,
                                      'ts_rolling_avg' : ts_rolling_avg,
                                      'counties'       : counties }}

        template = loader.get_template('covid_nyt/view_state.html')
        
    except Exception as e:
        eprint('Problem returning HTTP request: {}'.format(e))
        
        context = base_context
        template = loader.get_template('covid_nyt/page_not_found.html')
        
    return HttpResponse(template.render(context, request))
