import xml.etree.ElementTree as etree

def dataframe_to_html(df, row_attr_cols=[], row_cols=None):
    """_summary_

        * df (pandas.DataFrame): table
        * row_attr_cols (list, optional): List of columns to write as attributes in row element. Defaults to [].
        * row_cols (list, optional): List of columns to write as children in row element. Defaults all columns
    """
    if not row_cols: # default to use all columns as sub-elements of row
        row_cols = df.columns.to_list()   
    table = df.astype(str) # turns everything on str
    table_dict = table.to_dict('split')
    columns = table_dict['columns']
    col2index = { v:i for i, v in enumerate(table_dict['columns']) }    
    def add_rows(root, table_dict, row_attrs_cols, row_cols, tag_row='tr', tag_col='td'):            
        for row in table_dict:
            # row attrs names and values in lower-case (key:value)
            row_attrs = { key.lower(): row[col2index[key]].lower() for key in row_attrs_cols } 
            erow = etree.SubElement(root, tag_row, attrib=row_attrs) 
            for col in row_cols:
                ecol = etree.SubElement(erow, tag_col)
                ecol.text = str(row[col2index[col]])
    root = etree.Element('table')
    thead = etree.SubElement(root, 'thead') 
    add_rows(thead, [table_dict['columns']], [], row_cols, 'tr', 'th')
    tbody = etree.SubElement(root, 'tbody')     
    add_rows(tbody, table_dict['data'], row_attr_cols, row_cols)
    return root 