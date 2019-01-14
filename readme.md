# Conquest API Python Wrapper

Conquest API Python Wrapper is a Python module for working the the Conquest API. This module uses Python 3.x

The code is well documented so for comprehensive information regarding use of this module refer to [\conquest_api\conquest_api.py](https://github.com/nwduncan/conquest_api/blob/master/conquest_api/conquest_api.py)

### Installation

```
pip install git+https://github.com/nwduncan/conquest_api.git
```
*Consider installing in to a virtual environment*

---
### Usage Examples
Begin by importing the module
```python
>>> import conquest_api
```

##### Setting the output directory
The output directory is where any error CSVs are saved to. The default directory is the user's temp directory. To set a custom path redefine the `conquest_api.output_path` variable
```python
>>> conquest_api.output_path = r"\\eng_drive\Conquest\Conquest API\errors"
```


##### Creating a token
To interact with the API you need a token. The `Token` class object, once initialised, is passed to all other conquest_api classes.
```python
>>> token = conquest_api.Token(api_url='https://localhost/ConquestApi/api/',
...                            username='user',
...                            password='passkey123',
...                            connection='Conquest Live')
```

Get basic asset details
```python
>>> # initialise the Asset class object using a token
>>> asset = conquest_api.Asset(token)
>>> # return data for a single asset
>>> asset_basic = asset.get_basic(116983)
>>> asset_basic
{116983: {'AssetID': 116983, 'AssetDescription': 'Alaska Court - 150mm PVC Sewer Gravity Main - AssetID 116983', 'DepartmentID': None, 'FamilyCode': '005.004.055.161', 'Location': None, 'ParentID': 113670}}
>>> # return data for multiple assets
>>> asset_basic_multiple = asset.get_basic([116983, 116984, 116985])
>>> for assetid in asset_basic_multiple:
...     print(f'{assetid}: {asset_basic_multiple[assetid]}')
116983: {'AssetID': 116983, 'AssetDescription': 'Alaska Court - 150mm PVC Sewer Gravity Main - AssetID 116983', 'DepartmentID': None, 'FamilyCode': '005.004.055.161','Location': None, 'ParentID': 113670}
116984: {'AssetID': 116984, 'AssetDescription': 'Alaska Court - 150mm PVC Sewer Gravity Main - AssetID 116984', 'DepartmentID': None, 'FamilyCode': '005.004.055.162','Location': None, 'ParentID': 113670}
116985: {'AssetID': 116985, 'AssetDescription': 'Utah Court - 150mm PVC Sewer Gravity Main - AssetID 116985', 'DepartmentID': None, 'FamilyCode': '005.004.055.163', 'Location': None, 'ParentID': 113670}
```

Find action by field (this will only work if result is unique, otherwise an empty `dict` is returned)
```python
>>> action = conquest_api.Action(token)
>>> action_details = action.find_by_field(field='UserText30', value='2f55a41e-7892-4c5c-a4a9-d06f3a474cae')
>>> action_details['ActionID']
70138
>>> action_details['ActionDescription']
'Basement car park - water leak'
>>> action_details['UserText30']
'2f55a41e-7892-4c5c-a4a9-d06f3a474cae'
```
---
### Basic Scripts
Create a simple CSV and import it in to Conquest.
```python
import conquest_api
import csv

# create the csv headers and asset attributes
headers = ['ParentCode', 'AssetDescription', 'TypeID', 'Status']
rows = [['001.003.020.005', 'SEAL 2019 Carstens Street (Ch.00373 - Ch.00406)', 1147, 'Proposed'],
        ['001.003.020.006', 'SEAL 2019 Carstens Street (Ch.00406 - Ch.00468)', 1147, 'Proposed']]
filename = r'C:\imports\import_file.csv'

# write the headers and each row in the above list to the csv file
with open(filename, 'w', newline='') as open_file:
    writer = csv.writer(open_file)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

# create a token and initialise an import object
token = conquest_api.Token(api_url='https://localhost/ConquestApi/api/', username='user', password='passkey123', connection='Conquest Live')
import_object = conquest_api.Import(token)
# use the add method on the import object to import the newly created csv file
import_file = import_object.add(filename=filename, import_type='Asset')
```
All returns from the 'add' method include the batch id, boolean representing import success, and error messages/files (if any). Printing the return object shows what data it contains.
```python
>>> import_file
{'batch': 'e477baaf-4d0a-4668-9c79-7b4f42f7a11a', 'success': True, 'error_msg': None, 'error_file': None}
```

*Note: 'success' will show as `False` if **any** errors are found during file validation. Some items from the file may still have imported correctly. View the 'Output to CSV' file listed in the 'error_file' for clarification.</br></br>*

Batch import all files within a folder.
```python
import conquest_api
import os

# specify the directory where the files are stored
batch_dir = r'C:\imports\batch'

# build list of files for import
batch_files = []
for file in os.listdir(batch_dir):
    if file.lower().endswith('.csv'):
        batch_files.append(file)

# create token and import object
token = conquest_api.Token(api_url='https://localhost/ConquestApi/api/', username='user', password='passkey123', connection='Conquest Live')
import_object = conquest_api.Import(token)

# dict to store any errors
import_errors = {}
# list to record all successful imports
import_success = []

# iterate over list of files and attempt to import them
for file in batch_files:
    filename = os.path.join(batch_dir, file)
    add_file = import_object.add(filename=filename, import_type='Asset')
    if add_file['success']:
        import_success.append(file)
    else:
        import_errors[file] = add_file

# print out any errors for review
for file in import_errors:
    error_msg = import_errors[file]['error_msg']
    error_file = import_errors[file]['error_file']
    print(f"{file}: {error_msg} - {error_file}")
```
