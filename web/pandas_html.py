import xml.etree.ElementTree as etree

def dataframe_to_html(df, row_attrs=[], row_cols=None):
    """
    Converts dataframe to an html <table> as an ElementTree class.  
        * df (pandas.DataFrame): table
        * row_attrs (list, optional): List of columns to write as attributes in <tr> row element. Defaults to [] none.
        * row_cols (list, optional): List of columns to write as children in row <td> element. Defaults to all columns.               
    - returns: ElementTree class containing a html <table>      
    Note: generate a string with `etree.tostring(dataframe_to_html(...), encoding='unicode', method='xml')`
    """
    if not row_cols: # default to use all columns as <td> sub-elements of row
        row_cols = df.columns.to_list()   
    table = df.astype(str) # turns everything to str
    table_dict = table.to_dict('split')
    col2index = { v:i for i, v in enumerate(table_dict['columns']) }    
    def add_rows(root, table_dict, row_attrs_, row_cols_, tag_row='tr', tag_col='td'):            
        for row in table_dict:
            # row attrs names and values in lower-case (key:value)
            row_attrs = { key.lower(): row[col2index[key]].lower() for key in row_attrs_ } 
            erow = etree.SubElement(root, tag_row, attrib=row_attrs) 
            for col in row_cols_:
                ecol = etree.SubElement(erow, tag_col)
                ecol.text = str(row[col2index[col]])
    etable = etree.Element('table')
    thead = etree.SubElement(etable, 'thead') 
    add_rows(thead, [table_dict['columns']], [], row_cols, 'tr', 'th')
    tbody = etree.SubElement(etable, 'tbody')     
    add_rows(tbody, table_dict['data'], row_attrs, row_cols)
    return etable     