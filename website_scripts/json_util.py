import json

def read_json(filepath: str) -> dict:
    """Takes only one argument, the path to the .json file on the system. Opens the requested file in a pythonic format (dictionary)"""
    with open(f"{filepath}.json", encoding='utf-8') as f:
        data = json.load(f)
    
    return data


def write_json(data: dict, filepath: str):
    """It takes 'data' as the first argument, and then 'filename' as the second argument. 'data' is saved in a 'filepah' file in json format."""
    with open(f"{filepath}.json", "w", encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def append_json(data: dict, filepath: str):
    """It takes 'data' as the first argument, and then 'filename' as the second argument. 'data' is added to 'filepath' in json format."""
    with open(f"{filepath}.json", "a", encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def loads_json(data: str) -> dict:
    """Returns a dictionary made from a json string"""
    return json.loads(data)


def dumps_json(data: dict) -> str:
    """Returns a json string made from a dict"""
    return json.dumps(str)
