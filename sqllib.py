#!usr/bin/python3

from collections import namedtuple

import psycopg2
import sys

def eprint(*args, **kwargs):
    ''' print to apache error log; use for exception debugging
    '''
    print(*args, file=sys.stderr, **kwargs)

def db_connect_pg():
        ''' make connection to postgres
        '''

        try:
                return psycopg2.connect(dbname="covid") #, user="django_read_write", password="8gPA>+5AsYaH7uh]")
        except Exception as e:
                print('Problem with db connection:', e)

def get_national():
        ''' query state-level data table
                aggregate up to national level

                return: list of tuples that contain - 
                                0: updated on
                                1: total cases
                                2: total deaths
                                3: current cases
                                4: current deaths
                                5: rolling average (cases)
        '''

        conn = db_connect_pg()
        c = conn.cursor()

        sql = '''--First build up a national-level cte
                         WITH cte_us AS
                         (
                                SELECT updated_on, SUM(cases) AS cases, SUM(deaths) AS deaths
                                FROM state_data
                                GROUP BY updated_on
                         )

                         --Now we can query off that like any state-level query
                         SELECT t_1.*,
                                     ROUND(AVG(t_1.new_cases) OVER (ORDER BY t_1.updated_on ROWS BETWEEN 7 PRECEDING AND CURRENT ROW))::integer AS rolling_avg
                         FROM (SELECT a.updated_on, 
                                                  a.cases, 
                                                  a.deaths,
                                                  a.cases  - b.cases  AS new_cases,
                                                  a.deaths - b.deaths AS new_deaths
                                    FROM cte_us a
                                                INNER JOIN cte_us b ON (a.updated_on::date - b.updated_on::date) = 1) t_1
                         WHERE t_1.new_cases > 0                        
                     ORDER BY t_1.updated_on;''' 

        c.execute(sql)
        result = c.fetchall()
        conn.close()

        return result
        
def get_state_rollup(us_state):
        ''' query state-level data table
                takes: verbose state name

                return: list of tuples that contain - 
                                0: updated on
                                1: county (blank for state level table)
                                2: state (verbose)
                                3: fips_code
                                4: total cases
                                5: total deaths
                                6: current cases
                                7: current deaths
                                8: rolling average
        '''

        conn = db_connect_pg()
        c = conn.cursor()

        sql = '''SELECT c.*, ROUND(AVG(c.new_cases) OVER (ORDER BY c.updated_on ROWS BETWEEN 7 PRECEDING AND CURRENT ROW)) AS rolling_avg
                         FROM (SELECT a.*, 
                                                  a.cases  - b.cases  AS new_cases, 
                                                  a.deaths - b.deaths AS new_deaths
                                   FROM state_data a INNER JOIN state_data b ON julianday(a.updated_on) - julianday(b.updated_on) = 1.0 AND a.state = b.state
                                   WHERE a.state = '{}') c
                         ORDER BY c.updated_on;'''.format(us_state)


        sql_pg = '''SELECT t_1.*,
                           ROUND(AVG(t_1.new_cases) OVER (ORDER BY t_1.updated_on ROWS BETWEEN 7 PRECEDING AND CURRENT ROW))::integer AS rolling_avg
                FROM (SELECT a.updated_on, 
                                                         a.cases, 
                                                         a.deaths,
                                         a.cases  - b.cases  AS new_cases,
                             a.deaths - b.deaths AS new_deaths
                                    FROM state_data a
                                      INNER JOIN state_data b ON (a.updated_on::date - b.updated_on::date) = 1 AND a.state = b.state AND a.state = '{}') t_1
                            WHERE t_1.new_cases > 0
                                ORDER BY t_1.updated_on;'''.format(us_state)

        c.execute(sql_pg)
        result = c.fetchall()
        conn.close()

        return result

def get_county_level(us_state):
        ''' get the county-level list for the selected state
                takes: verbose state name

                return: list of tuples that contain - 
                                0: county name
                                1: total cases
                                2: total deaths
                                3: current cases
                                4: current deaths

        '''

        conn = db_connect_pg()
        c = conn.cursor()

        sql_pg = '''WITH cte AS (SELECT *
                                                     FROM county_data AS cd
                                                     WHERE cd.state = '{a_state}' AND updated_on IN (SELECT DISTINCT updated_on
                                                                                                                                                 FROM county_data
                                                                                                                                                 WHERE state = '{a_state}'
                                                                                                                                                 ORDER BY updated_on DESC
                                                                                                                                                 LIMIT 2)
                                                     ORDER BY updated_on DESC, cases DESC) 

                         SELECT a.county, 
                                    a.cases, 
                                    a.deaths, 
                                        a.cases  - b.cases   AS new_cases, 
                                    a.deaths - b.deaths  AS new_deaths
                         FROM cte a INNER JOIN cte b ON a.county = b.county
                                                                                    AND a.updated_on - b.updated_on = 1;'''.format(a_state = us_state)

        c.execute(sql_pg)
        result = c.fetchall()
        conn.close()

        County = namedtuple('County', ['name', 'total_cases', 'total_deaths', 'new_cases', 'new_deaths'])
        result = [County(*county) for county in result]

        return result

def get_hashes():
        conn = db_connect_pg()
        c = conn.cursor()

        sql = '''SELECT hashed FROM county_data'''

        c.execute(sql)
        result = [t[0] for t in c.fetchall()]
        conn.close()

        return result

def update_county(current):
        # takes the full path to the file containing new records
        conn = db_connect_pg()
        c = conn.cursor()

        with open(current, 'r') as f:
                try:
                        c.execute('''CREATE TEMP TABLE tmp_table
                                                 ON COMMIT DROP
                                                 AS
                                                 SELECT *
                                                 FROM county_data
                                                 WITH NO DATA;''')

                        c.copy_expert('''COPY tmp_table FROM STDIN WITH (FORMAT CSV)''', f)
                        c.execute('''INSERT INTO county_data
                                                 SELECT *
                                                 FROM tmp_table
                                                 ON CONFLICT (hashed) DO UPDATE SET cases  = EXCLUDED.cases,
                                                                                                                        deaths = EXCLUDED.deaths''', f)

                        conn.commit()

                except Exception as e:
                        eprint('Problem inserting county-level data: {}'.format(e))

        conn.close()

def update_state(current):
        # takes the full path to the file containing new records
        conn = db_connect_pg()
        c = conn.cursor()

        with open(current, 'r') as f:
                try:
                        c.execute('''CREATE TEMP TABLE tmp_table 
                                                 ON COMMIT DROP
                                                 AS
                                                 SELECT * 
                                                 FROM state_data
                                                 WITH NO DATA;''')

                        c.copy_expert('''COPY tmp_table FROM STDIN WITH (FORMAT CSV)''', f)

                        c.execute('''INSERT INTO state_data
                                                 SELECT *
                                                 FROM tmp_table
                                                 ON CONFLICT (hashed) DO UPDATE SET cases  = EXCLUDED.cases,
                                                                                                                        deaths = EXCLUDED.deaths''', f)

                        conn.commit()

                except Exception as e:
                        eprint('Problem inserting state-level data: {}'.format(e))

        conn.close()

def make_all_states_current():
        # do a rollup for each state for the current (or most recently available) day
         # and put them in a table that the django app can query from; this table should
        # end up with only 55 rows

        # IMPORTANT: this would need to be called after the state level updates in order
        # to be current

        sql = '''DELETE FROM state_rollups_current;

                         INSERT INTO state_rollups_current
                         SELECT state_list.state, state_result.*
                         FROM (SELECT DISTINCT state
                                   FROM state_data) state_list,
                                   LATERAL
                                  (SELECT a.updated_on, a.cases, a.deaths, a.cases  - b.cases  AS new_cases, a.deaths - b.deaths AS new_deaths
                                   FROM state_data a
                                                INNER JOIN state_data b ON (a.updated_on::date - b.updated_on::date) = 1 AND a.state = b.state
                                   WHERE a.state = state_list.state
                                   ORDER BY a.updated_on DESC
                                   LIMIT 1) state_result;'''

        try:
            conn = db_connect_pg()
            c = conn.cursor()

            c.execute(sql)
            conn.commit()

            conn.close()
            
        except Exception as e:
            eprint('Problem doing update of current day state level rollup: {}'.format(e))

def get_all_states_current():
        # find the rollups for each state for today
        # this is just a query of the table built up in the previous function make_all_states_current
        
        # it's more efficient to query this each time the django app needs it instead of doing the
        # query in that function, which takes much longer
        
        sql = '''SELECT * FROM state_rollups_current ORDER BY state;'''

        conn = db_connect_pg()
        c = conn.cursor()

        c.execute(sql)
        result = c.fetchall()
        
        conn.close()

        State = namedtuple('State', ['name', 'updated_on', 'total_cases', 'total_deaths', 'new_cases', 'new_deaths'])
        result = [State(*state) for state in result]
        
        return result                        
