import autogen

# build gpt_configuration object
# Base Configuration        
base_config = {
    "temperature": 0,
    "config_list": autogen.config_list_from_models(['gpt-4']),
    "timeout": 120,
}

write_file_config = {
    **base_config,
    "functions": [
        {
            "name": "write_file",
            "description": "Write a file to the filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "fname": {
                        "type": "string",
                        "description": "The name of the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content of the file to write"
                    }
                },
                "required": ["fname", "content"]
            }
        }
    ]
}
