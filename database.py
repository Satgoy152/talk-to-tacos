import pandas as pd
from sqlalchemy import create_engine, text
import os
import numpy as np
import re

def create_db_from_excel(excel_path, db_path):
    """
    Reads an Excel file and creates a SQLite database from its sheets.
    Each sheet is converted into a separate table with proper header handling.
    """
    if os.path.exists(db_path):
        os.remove(db_path)  # Remove existing DB to start fresh
        
    xls = pd.ExcelFile(excel_path)
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Process each sheet in the Excel file
    for sheet_idx, sheet_name in enumerate(xls.sheet_names):
        try:
            # First, read the Excel sheet without setting headers
            if sheet_idx == 0:  # First table (summary table)
                # For the first table, use the first row as header
                df = pd.read_excel(xls, sheet_name=sheet_name)
                print(f"Processing summary table '{sheet_name}' with standard headers")

            elif sheet_idx == 2:
                # remove the top two rows and set the third row as header
                df = pd.read_excel(xls, sheet_name=sheet_name, header=2)

                # convert the first two columns to string
                df.iloc[:, 0:2] = df.iloc[:, 0:2].astype(str)

                hyperlink_pattern = r'=HYPERLINK\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)'
            
                # Get the first two column names
                first_two_cols = list(df.columns)[:2] if len(df.columns) >= 2 else list(df.columns)
                
                for col in first_two_cols:
                    # Apply the extraction to each cell in the column
                    df[col] = df[col].apply(lambda x: 
                                        re.search(hyperlink_pattern, str(x)).group(1) 
                                        if isinstance(x, str) and re.search(hyperlink_pattern, str(x)) 
                                        else x)
                print(f"Processing table '{sheet_name}' with standard headers")
                # display(df.head())  # Display the first few rows of the DataFrame

                # parse the first two columns as strings, split by comma

            elif sheet_idx == 5:  # Second table (summary table)
                # For the second table, use the first row as header
                df = pd.read_excel(xls, sheet_name=sheet_name)

                print(f"Processing summary table '{sheet_name}' with standard headers")

            elif sheet_idx == 8:  # Second table (detailed table)
                # For other tables, we need to handle the multi-row headers
                # Read the sheet with header=None to get all rows
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                
                if len(df) >= 3:  # Make sure we have enough rows
                    # Get the header rows
                    top_row = df.iloc[0].replace({np.nan: None, 'NaN': None})  # Row with potential suffixes
                    third_row = df.iloc[2].replace({np.nan: None, 'NaN': None})  # Row with base column names
                    
                    # Create combined headers
                    combined_headers = []
                    current_suffix = None
                    
                    for i in range(len(top_row)):
                        # Update suffix if we encounter a non-None value in the top row
                        if top_row[i] is not None:
                            current_suffix = str(top_row[i])
                        
                        # Get base column name from third row
                        base_name = str(third_row[i]) if third_row[i] is not None else f"col_{i}"
                        
                        # Create combined column name
                        if current_suffix:
                            combined_headers.append(f"{base_name}_{current_suffix}")
                        else:
                            combined_headers.append(base_name)
                    
                    # Set combined headers and drop the first three rows
                    df.columns = combined_headers
                    df = df.iloc[3:]
                    print(f"Processed table '{sheet_name}' with combined headers")
                    
                else:
                    print(f"Sheet '{sheet_name}' doesn't have enough rows for header processing")
            else:  # For other tables, use the first row as header
                continue
            
            # Reset index to ensure proper SQLite import
            df = df.reset_index(drop=True)
            
            # Clean column names for SQL compatibility
            df.columns = [str(col).replace(' ', '_').replace('(', '').replace(')', '').replace('.', '_')
                         .replace('-', '_').replace('/', '_').replace('\\', '_') for col in df.columns]
            
            # Sanitize table name
            table_name = ''.join(e for e in sheet_name if e.isalnum() or e == '_')
            if not table_name:  # if sheet name was all special chars
                table_name = f"table_{sheet_idx}"

            # display(df)  # Display the first few rows of the DataFrame

            df.to_sql(table_name, engine, index=False, if_exists='replace')
            print(f"Sheet '{sheet_name}' imported as table '{table_name}' with {len(df)} rows.")
            
        except Exception as e:
            print(f"Could not import sheet '{sheet_name}': {e}")
    
    return engine

def query_db(db_path, query_string):
    """
    Connects to the SQLite database and executes a given SQL query.
    Returns the query result.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        try:
            result = connection.execute(text(query_string))
            rows = result.fetchall()
            # Get column names for better display if needed
            # column_names = result.keys()
            # return [dict(zip(column_names, row)) for row in rows] # Returns list of dicts
            return rows # Returns list of tuples
        except Exception as e:
            return f"Error executing query: {e}"

def get_db_schema(db_path):
    """
    Returns the schema of the database (table names and their columns).
    """
    engine = create_engine(f"sqlite:///{db_path}")
    schema = {}
    with engine.connect() as connection:
        # Get table names
        table_names_query = text("SELECT name FROM sqlite_master WHERE type='table';")
        tables_result = connection.execute(table_names_query)
        table_names = [row[0] for row in tables_result.fetchall()]

        for table_name in table_names:
            # Get column info for each table
            columns_query = text(f"PRAGMA table_info({table_name});")
            columns_result = connection.execute(columns_query)
            columns = []
            for col_info in columns_result.fetchall():
                # col_info format: (cid, name, type, notnull, dflt_value, pk)
                columns.append(f"{col_info[1]} ({col_info[2]})")
            schema[table_name] = columns
    return schema
