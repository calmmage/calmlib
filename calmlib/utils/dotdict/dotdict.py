class RecursiveDotDict(dict):
    """A recursive dot-accessible dictionary."""

    def __getattr__(self, attr):
        value = self[attr]
        if isinstance(value, dict):
            return RecursiveDotDict(value)
        elif isinstance(value, list):
            return [
                RecursiveDotDict(item) if isinstance(item, dict) else item
                for item in value
            ]
        return value

    def __setattr__(self, key, value):
        self[key] = value


# # Example usage
# import json
#
# json_data = '{"name": "John", "age": 30, "city": "New York", "education": {"degree": "MSc", "university": "XYZ"}, "hobbies": [{"name": "reading", "type": "relaxing"}, {"name": "cycling", "type": "sport"}]}'
# data = json.loads(json_data)
# dotdict_data = RecursiveDotDict(data)
#
# # Accessing attributes
# print(dotdict_data.name)
# print(dotdict_data.education.degree)
# for hobby in dotdict_data.hobbies:
#     print(hobby.name, hobby.type)

# transcript = RecursiveDotDict(data)
