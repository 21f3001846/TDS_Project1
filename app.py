# /// script
# requires-python = ">= 3.12"
# dependencies = [
#   "uvicorn",
#   "fastapi",
#   "requests"
# ]
# ///

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import json
from subprocess import run

app = FastAPI()

AIPROXY_TOKEN = os.getenv('AIPROXY_TOKEN')

app.add_middleware(
    CORSMiddleware, 
    allow_origins = ['*'],
    allow_credentials = True,
    allow_methods = ["GET", "POST"],
    allow_headers = ['*']
)

headers = {
    "Content-type" : "application/json",
    "Authorization" : f"Bearer {AIPROXY_TOKEN}"
}

response_format = {
    "type" : "json_schema",
    "json_schema" : {
        "name" : "task_runner",
        "schema" : {
            "type" : "object",
            "required" : ["code", "dependencies"],
            "properties" : {
                "code" : {
                    "type" : "string",
                    "description" : "The code to perfrom the task"
                },
                "dependencies" : {
                    "type" : "array",
                    "items" : { 
                        "type" : "object",
                        "properties" : {
                            "module" : {
                                "type" : "string",
                                "description" : "Name of the module required for the code to run successfully"
                            }
                        },
                        "required" : ["module"],
                        "additionalProperties" : False
                    }
                }
            }
        }
    }
}

system_prompt = """
You are an automation agent that accepts plain-English tasks. Your job is to generate a python or bash code depending on the task.
You are capable of performing a variety of tasks which include opening and processing files, writing into files, fetching api data, accessing git, etc.
Whenever you receive a task, you have to analyse it, separate the parameters provided, understand if the task expects a python or bash code and generate the respective code.
While generating the code, assume that the code will be run on a docker container and that uv and python3 are alreay installed along with their built-in modules. 
You are to generate the code along with all the modules it requires to run successfully. Stricty include only those modules which are not already built-in with python3. 
If your task involves running a url and comes with an email as parameter, it is for generating the dataset required for the future tasks.
Make sure you generate a python code for that, which uses requests module to run the url along with the email as parameter, which should run in the current working directory. 
Once you have that file, make sure your code is able to run that file using the command \"uv run {filename} {email}\", to create the required data for the other tasks.
Ensure all steps are completed correctly while handling potential failures gracefully. 
Your objective is to install necessary dependencies, fetch and execute scripts with required arguments, format files according to specified standards, 
parse and process structured and unstructured data, perform computations on datasets, and extract meaningful information from various file formats,
ensuring all results are written to appropriate output files. You must sort, filter, transform, and analyze data based on defined criteria, 
leveraging external tools or APIs where necessary. You should also integrate with large language models to extract key details from text
and images, apply machine learning techniques such as embeddings to determine similarities,
and interact with databases to perform structured queries and computations. 
Additionally, you must automate tasks related to data retrieval from online sources, version control operations, 
database queries, web scraping, media processing, format conversion, and API development. You must guarantee that all operations respect 
strict constraints: data must never be accessed or modified outside the designated working directory, 
and no files should be deleted under any circumstances. 
Potential failure points such as missing dependencies, incorrect paths, malformed inputs, network issues, permission restrictions, and unexpected 
data structures must be anticipated and mitigated by verifying prerequisites, validating and sanitizing inputs, handling errors 
gracefully, implementing retries for network-dependent operations, ensuring correct permissions, and maintaining detailed execution logs.
"""


@app.post("/run")
def task_runner(task : str):
    url = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    
    data = {
        "model" : "gpt-4o-mini",
        "messages" : [
            {
                "role" : "user",
                "content" : task
            },
            {
                "role" : "system",
                "content" : f"""{system_prompt}"""
            }    
        ], 
        "response_format" : response_format
    }
    response = requests.post(url= url, headers = headers, json = data)
    result = json.loads(response.json()['choices'][0]['message']['content'])
    code = result['code']
    deps = result['dependencies']
    inline_script = f"""
# /// script
# requires-python = ">= 3.12"
# dependencies = [
{''.join(f"# \"{dep['module']}\",\n" for dep in deps)}# ]
# ///
"""

    with open("task_code.py", 'w') as f:
        f.write(inline_script)
        f.write(code)

    output = run(["uv", "run", "task_code.py"], capture_output=True, text=True, cwd=os.getcwd())
    std_err = output.stderr.split('\n')
    std_out = output.stdout

    return "Success"


@app.get("/read")
def read_file(path : str):
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=404, details="File not found!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
