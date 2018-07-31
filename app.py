import sys
import logging
import pymysql
import rds_config
import json

#rds settings
rds_host  = "da-cummins-aurora.cxslknoxcxu0.us-east-2.rds.amazonaws.com"
name = rds_config.db_username
password = rds_config.db_password
db_name = rds_config.db_name

# Logger config
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# This function fetches content from Aurora RDS instance
def lambda_handler(event, context):
    
    try:
        conn = pymysql.connect(rds_host, user=name, passwd=password, db=db_name, connect_timeout=5, cursorclass=pymysql.cursors.DictCursor)
    except:
        logger.error("ERROR: Unexpected error: Could not connect to Aurora instance")
        sys.exit()
        
    logger.info("SUCCESS: Connection to RDS aurora instance succeeded")
    
    columns = event['columns']
    tableName = event['table']
    
    # All requests will invoke this DataService with a 'pageNum' key in event
    pageNum = int(event['pageNum'])           # For determining which record to begin retrieval at
    rowsPerPage = int(event['rowsPerPage'])   # Number of records to retrieve
    searchCriteria = event['searchCriteria']  # A single value to search for across all columns (if general search)
    smartSearch_input = event['smartSearch']  # Stringified list of tuples, (column=value), ... (if advanced search)
    
    sortBy = event['sortBy']                  # Column to sort on 
    sortOrder = event['sortOrder']            # Asc or Desc
        
    # TODO : Ensure better protection from SQL injections
    if ("%" in searchCriteria) or ("'" in searchCriteria): return []

    # Paginated request - return results based on user input, page number, and rows per page
    whereClause = ""
    if smartSearch_input == "": whereClause = where(columns, searchCriteria)
    else: whereClause = smartWhere(eval(smartSearch_input))
        
    startRecord = str(pageNum * rowsPerPage)
    query = "SELECT SQL_CALC_FOUND_ROWS " + columns + " FROM " + tableName + " s WHERE " + whereClause + " ORDER BY " + sortBy + " " + sortOrder + " LIMIT " + str(rowsPerPage) + " OFFSET " + startRecord  + ";"
        
    with conn.cursor() as cur:
        cur.execute(query)
        response = cur.fetchall();
        
        # Client needs the total number of results for their current query for pagination
        if response:
            cur.execute("Select Found_rows( ) as totalRows ;")
            numRows = cur.fetchone()
            response.append(numRows)
        else:
            noResult = {
                "totalRows" : 0
            }
            return noResult
    
    return response
    
def where(columns, searchCriteria):
    colNames = columns.split(', ') # Create an array of names
    matchString = ""
    # Build the WHERE clause to match the search criteria to each of the relevant columns
    for col in colNames:
        matchString += "s." + col + " LIKE " + "'%" + searchCriteria + "%'"
        if (colNames.index(col) < (len(colNames) - 1)) : matchString += " OR "
    return matchString
    
# Outputs a combined string of "WHERE <column> LIKE '%<value>%' (AND)" format
def smartWhere(tupleList):
    
    # Each tuple in the list has (column, value)
    # Each must translate to 'COLUMN LIKE %value% [AND] ...'
    where_clause = ""
    for tup in tupleList:
        where_clause += tup[0] + " LIKE '%" + tup[1] + "%' AND " 
                            
    return where_clause[:-5] # Don't include trailing ' AND '