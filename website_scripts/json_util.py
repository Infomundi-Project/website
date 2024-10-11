import json

def read_json(filepath: str) -> dict:
    """Takes only one argument, the path to the .json file on the system. Opens the requested file in a pythonic format (dictionary)"""
    try:
        with open(f"{filepath}.json", encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: {filepath}.json does not exist.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: {filepath}.json is not a valid JSON file.")
        return {}
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return {}

def write_json(data: dict, filepath: str):
    """It takes 'data' as the first argument, and then 'filename' as the second argument. 'data' is saved in a 'filepath' file in json format."""
    try:
        with open(f"{filepath}.json", "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"An error occurred while writing to the file: {e}")

def append_json(data: dict, filepath: str):
    """It takes 'data' as the first argument, and then 'filename' as the second argument. 'data' is added to 'filepath' in json format."""
    try:
        with open(f"{filepath}.json", "a", encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"An error occurred while appending to the file: {e}")

def loads_json(data: str) -> dict:
    """Returns a dictionary made from a json string"""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        print("Error: The provided string is not valid JSON.")
        return {}
    except Exception as e:
        print(f"An error occurred while loading JSON data: {e}")
        return {}

def dumps_json(data: dict) -> str:
    """Returns a json string made from a dict"""
    try:
        return json.dumps(data)
    except TypeError:
        print("Error: Provided data cannot be serialized to JSON.")
        return ""
    except Exception as e:
        print(f"An error occurred while dumping JSON data: {e}")
        return ""
